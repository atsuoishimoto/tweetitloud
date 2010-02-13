import os
import _winreg
import winKernel

from ctypes import *
import keyboardHandler
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
lastKeyboardLayoutChangeEventTime=None

winEventHookID=None

#utility function to point an exported function pointer in a dll  to a ctypes wrapped python function
def _setDllFuncPointer(dll,name,cfunc):
	cast(getattr(dll,name),POINTER(c_void_p)).contents.value=cast(cfunc,c_void_p).value

#Implementation of nvdaController methods
@WINFUNCTYPE(c_long,POINTER(c_wchar_p))
def nvdaController_getNVDAVersionString(version):
	import versionInfo
	version.contents.value=versionInfo.version
	return 0

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

@WINFUNCTYPE(c_long,c_long,c_ulong,c_wchar_p)
def nvdaController_inputLangChangeNotify(threadID,hkl,layoutString):
	if threadID!=winUser.getWindowThreadProcessID(winUser.getForegroundWindow())[1]:
		return
	import queueHandler
	import ui
	import languageHandler
	layoutName=None
	languageName=None
	try:
		key = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, "SYSTEM\\CurrentControlSet\\Control\\Keyboard Layouts\\"+ layoutString)
	except WindowsError:
		key=None
	if key:
		try:
			s = _winreg.QueryValueEx(key, "Layout Display Name")[0]
		except:
			s=None
		if s:
			buf=create_unicode_buffer(256)
			windll.shlwapi.SHLoadIndirectString(s,buf,256,None)
			layoutName=buf.value
	buf=create_unicode_buffer(1024)
	windll.kernel32.GetLocaleInfoW(hkl&0xffff,languageHandler.LOCALE_SLANGUAGE,buf,1024)
	if buf:
		languageName=buf.value
	if not layoutName: layoutName=_("unknown layout")
	if not languageName: languageName=_("unknown language")
	queueHandler.queueFunction(queueHandler.eventQueue,ui.message,_("Layout %s, language %s")%(layoutName,languageName))
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
	global _remoteLib, _remoteLoader64, localLib, winEventHookID,generateBeep
	localLib=cdll.LoadLibrary('lib/nvdaHelperLocal.dll')
	for name,func in [
		("getNVDAVersionString",nvdaController_getNVDAVersionString),
		("speakText",nvdaController_speakText),
		("cancelSpeech",nvdaController_cancelSpeech),
		("brailleMessage",nvdaController_brailleMessage),
		("inputLangChangeNotify",nvdaController_inputLangChangeNotify),
	]:
		try:
			_setDllFuncPointer(localLib,"_nvdaController_%s"%name,func)
		except AttributeError:
			log.error("nvdaHelperLocal function pointer for %s could not be found, possibly old nvdaHelperLocal dll"%name)
	localLib.startServer()
	generateBeep=localLib.generateBeep
	generateBeep.argtypes=[c_char_p,c_float,c_uint,c_ubyte,c_ubyte]
	generateBeep.restype=c_uint
	_remoteLib=cdll.LoadLibrary('lib/NVDAHelperRemote.dll')
	if _remoteLib.nvdaHelper_initialize() < 0:
		raise RuntimeError("Error initializing NVDAHelper")
	if os.environ.get('PROCESSOR_ARCHITEW6432')=='AMD64':
		_remoteLoader64=RemoteLoader64()
	winEventHookID=winUser.setWinEventHook(EVENT_TYPEDCHARACTER,EVENT_TYPEDCHARACTER,0,winEventCallback,0,0,0)

def terminate():
	global _remoteLib, _remoteLoader64, localLib
	winUser.unhookWinEvent(winEventHookID)
	if _remoteLib.nvdaHelper_terminate() < 0:
		raise RuntimeError("Error terminating NVDAHelper")
	_remoteLib=None
	if _remoteLoader64:
		_remoteLoader64.terminate()
		_remoteLoader64=None
	localLib=None
