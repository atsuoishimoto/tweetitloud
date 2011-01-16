import os
import _winreg
import winKernel

from ctypes import *
from comtypes import BSTR
import winUser
import speech
import eventHandler
import queueHandler
import api
import globalVars
from logHandler import log
import time
import globalVars

EVENT_TYPEDCHARACTER=0X1000

_remoteLib=None
_remoteLoader64=None
localLib=None
generateBeep=None
VBuf_getTextInRange=None
lastInputLangChangeTime=0

winEventHookID=None

#utility function to point an exported function pointer in a dll  to a ctypes wrapped python function
def _setDllFuncPointer(dll,name,cfunc):
	cast(getattr(dll,name),POINTER(c_void_p)).contents.value=cast(cfunc,c_void_p).value

#Implementation of nvdaController methods
@WINFUNCTYPE(c_long,c_wchar_p)
def nvdaController_speakText(text):
	import queueHandler
	import speech
	queueHandler.queueFunction(queueHandler.eventQueue,speech.speakText,text)
	return 0

@WINFUNCTYPE(c_long)
def nvdaController_cancelSpeech():
	import queueHandler
	import speech
	queueHandler.queueFunction(queueHandler.eventQueue,speech.cancelSpeech)
	return 0

@WINFUNCTYPE(c_long,c_wchar_p)
def nvdaController_brailleMessage(text):
	import queueHandler
	import braille
	queueHandler.queueFunction(queueHandler.eventQueue,braille.handler.message,text)
	return 0

def _lookupKeyboardLayoutNameWithHexString(layoutString):
	try:
		key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Control\\Keyboard Layouts\\"+ layoutString)
	except WindowsError:
		log.debugWarning("Could not find reg key %s"%layoutString)
		return None
	try:
		s = _winreg.QueryValueEx(key, "Layout Display Name")[0]
	except:
		log.debugWarning("Could not find reg value 'Layout Display Name' for reg key %s"%layoutString)
		s=None
	if s:
		buf=create_unicode_buffer(256)
		windll.shlwapi.SHLoadIndirectString(s,buf,256,None)
		return buf.value
	try:
		return _winreg.QueryValueEx(key, "Layout Text")[0]
	except:
		log.debugWarning("Could not find reg value 'Layout Text' for reg key %s"%layoutString)
		return None

@WINFUNCTYPE(c_long,c_long,c_long,c_long,c_long,c_long)
def nvdaControllerInternal_displayModelTextChangeNotify(hwnd, left, top, right, bottom):
	import displayModel
	displayModel.textChangeNotify(hwnd, left, top, right, bottom)
	return 0

@WINFUNCTYPE(c_long,c_long,c_long,c_long,c_wchar_p,c_wchar_p,c_long,c_wchar_p)
def nvdaControllerInternal_logMessage(pid,tid,level,fileName,funcName,lineNo,message):
	if not log.isEnabledFor(level):
		return 0
	from appModuleHandler import getAppNameFromProcessID
	codepath="RPC: %s, %s, %s, line %d"%(getAppNameFromProcessID(pid,includeExt=True),fileName,funcName, lineNo)
	log._log(level,message,[],codepath=codepath)
	return 0

@WINFUNCTYPE(c_long,c_long,c_ulong,c_wchar_p)
def nvdaControllerInternal_inputLangChangeNotify(threadID,hkl,layoutString):
	global lastInputLangChangeTime
	import queueHandler
	import ui
	curTime=time.time()
	if (curTime-lastInputLangChangeTime)<0.2:
		return 0
	lastInputLangChangeTime=curTime
	#layoutString can sometimes be None, yet a registry entry still exists for a string representation of hkl
	if not layoutString:
		layoutString=hex(hkl)[2:].rstrip('L').upper().rjust(8,'0')
		log.debugWarning("layoutString was None, generated new one from hkl as %s"%layoutString)
	layoutName=_lookupKeyboardLayoutNameWithHexString(layoutString)
	if not layoutName and hkl<0xd0000000:
		#Try using the high word of hkl as the lang ID for a default layout for that language
		simpleLayoutString=layoutString[0:4].rjust(8,'0')
		log.debugWarning("trying simple version: %s"%simpleLayoutString)
		layoutName=_lookupKeyboardLayoutNameWithHexString(simpleLayoutString)
	if not layoutName:
		#Try using the low word of hkl as the lang ID for a default layout for that language
		simpleLayoutString=layoutString[4:].rjust(8,'0')
		log.debugWarning("trying simple version: %s"%simpleLayoutString)
		layoutName=_lookupKeyboardLayoutNameWithHexString(simpleLayoutString)
	if not layoutName:
		log.debugWarning("Could not find layout name for keyboard layout, reporting as unknown") 
		layoutName=_("unknown layout")
	queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("layout %s")%layoutName)
	return 0

def handleTypedCharacter(window,wParam,lParam):
	focus=api.getFocusObject()
	if focus.windowClassName!="ConsoleWindowClass":
		eventHandler.queueEvent("typedCharacter",focus,ch=unichr(wParam))

@winUser.WINEVENTPROC
def winEventCallback(handle,eventID,window,objectID,childID,threadID,timestamp):
	global lastKeyboardLayoutChangeEventTime
	try:
		if eventID==EVENT_TYPEDCHARACTER:
			handleTypedCharacter(window,objectID,childID)
	except:
		log.error("helper.winEventCallback", exc_info=True)

class RemoteLoader64(object):

	def __init__(self):
		# Create a pipe so we can write to stdin of the loader process.
		pipeReadOrig, self._pipeWrite = winKernel.CreatePipe(None, 0)
		# Make the read end of the pipe inheritable.
		pipeRead = self._duplicateAsInheritable(pipeReadOrig)
		winKernel.closeHandle(pipeReadOrig)
		# stdout/stderr of the loader process should go to nul.
		with file("nul", "w") as nul:
			nulHandle = self._duplicateAsInheritable(nul.fileno())
		# Set the process to start with the appropriate std* handles.
		si = winKernel.STARTUPINFO(dwFlags=winKernel.STARTF_USESTDHANDLES, hSTDInput=pipeRead, hSTDOutput=nulHandle, hSTDError=nulHandle)
		pi = winKernel.PROCESS_INFORMATION()
		# Even if we have uiAccess privileges, they will not be inherited by default.
		# Therefore, explicitly specify our own process token, which causes them to be inherited.
		token = winKernel.OpenProcessToken(winKernel.GetCurrentProcess(), winKernel.MAXIMUM_ALLOWED)
		try:
			winKernel.CreateProcessAsUser(token, None, u"lib64/nvdaHelperRemoteLoader.exe", None, None, True, None, None, None, si, pi)
			# We don't need the thread handle.
			winKernel.closeHandle(pi.hThread)
			self._process = pi.hProcess
		except:
			winKernel.closeHandle(self._pipeWrite)
			raise
		finally:
			winKernel.closeHandle(pipeRead)
			winKernel.closeHandle(token)

	def _duplicateAsInheritable(self, handle):
		curProc = winKernel.GetCurrentProcess()
		return winKernel.DuplicateHandle(curProc, handle, curProc, 0, True, winKernel.DUPLICATE_SAME_ACCESS)

	def terminate(self):
		# Closing the write end of the pipe will cause EOF for the waiting loader process, which will then exit gracefully.
		winKernel.closeHandle(self._pipeWrite)
		# Wait until it's dead.
		winKernel.waitForSingleObject(self._process, winKernel.INFINITE)
		winKernel.closeHandle(self._process)

def initialize():
	global _remoteLib, _remoteLoader64, localLib, winEventHookID,generateBeep,VBuf_getTextInRange
	localLib=cdll.LoadLibrary('lib/nvdaHelperLocal.dll')
	for name,func in [
		("nvdaController_speakText",nvdaController_speakText),
		("nvdaController_cancelSpeech",nvdaController_cancelSpeech),
		("nvdaController_brailleMessage",nvdaController_brailleMessage),
		("nvdaControllerInternal_inputLangChangeNotify",nvdaControllerInternal_inputLangChangeNotify),
		("nvdaControllerInternal_displayModelTextChangeNotify",nvdaControllerInternal_displayModelTextChangeNotify),
		("nvdaControllerInternal_logMessage",nvdaControllerInternal_logMessage),
	]:
		try:
			_setDllFuncPointer(localLib,"_%s"%name,func)
		except AttributeError:
			log.error("nvdaHelperLocal function pointer for %s could not be found, possibly old nvdaHelperLocal dll"%name)
	localLib.startServer()
	generateBeep=localLib.generateBeep
	generateBeep.argtypes=[c_char_p,c_float,c_uint,c_ubyte,c_ubyte]
	generateBeep.restype=c_uint
	# Handle VBuf_getTextInRange's BSTR out parameter so that the BSTR will be freed automatically.
	VBuf_getTextInRange = CFUNCTYPE(c_int, c_int, c_int, c_int, POINTER(BSTR), c_int)(
		("VBuf_getTextInRange", localLib),
		((1,), (1,), (1,), (2,), (1,)))
	#Load nvdaHelperRemote.dll but with an altered search path so it can pick up other dlls in lib
	h=windll.kernel32.LoadLibraryExW(os.path.abspath(ur"lib\nvdaHelperRemote.dll"),0,0x8)
	if not h:
		log.critical("Error loading nvdaHelperRemote.dll: %s" % WinError())
		return
	_remoteLib=CDLL("nvdaHelperRemote",handle=h)
	if _remoteLib.injection_initialize() == 0:
		raise RuntimeError("Error initializing NVDAHelperRemote")
	if os.environ.get('PROCESSOR_ARCHITEW6432')=='AMD64':
		_remoteLoader64=RemoteLoader64()
	winEventHookID=winUser.setWinEventHook(EVENT_TYPEDCHARACTER,EVENT_TYPEDCHARACTER,0,winEventCallback,0,0,0)

def terminate():
	global _remoteLib, _remoteLoader64, localLib, generateBeep, VBuf_getTextInRange
	winUser.unhookWinEvent(winEventHookID)
	if _remoteLib.injection_terminate() == 0:
		raise RuntimeError("Error terminating NVDAHelperRemote")
	_remoteLib=None
	if _remoteLoader64:
		_remoteLoader64.terminate()
		_remoteLoader64=None
	generateBeep=None
	VBuf_getTextInRange=None
	localLib=None
