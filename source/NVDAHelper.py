import subprocess
import os

from ctypes import *
import keyboardHandler
import winUser
import speech
import eventHandler
import queueHandler
import api
import globalVars
from logHandler import log

EVENT_TYPEDCHARACTER=0X1000
EVENT_INPUTLANGCHANGE=0X1001

_remoteLib=None
_remoteLoader64=None
localLib=None

winEventHookID=None

def handleTypedCharacter(window,wParam,lParam):
	focus=api.getFocusObject()
	if focus.windowClassName!="ConsoleWindowClass":
		eventHandler.queueEvent("typedCharacter",focus,ch=unichr(wParam))

@winUser.WINEVENTPROC
def winEventCallback(handle,eventID,window,objectID,childID,threadID,timestamp):
	try:
		if eventID==EVENT_TYPEDCHARACTER:
			handleTypedCharacter(window,objectID,childID)
		elif eventID==EVENT_INPUTLANGCHANGE:
			keyboardHandler.speakKeyboardLayout(childID)
	except:
		log.error("helper.winEventCallback", exc_info=True)

def initialize():
	global _remoteLib, _remoteLoader64, localLib, winEventHookID
	localLib=cdll.LoadLibrary('lib/nvdaHelperLocal.dll')
	_remoteLib=cdll.LoadLibrary('lib/NVDAHelperRemote.dll')
	if _remoteLib.nvdaHelper_initialize() < 0:
		raise RuntimeError("Error initializing NVDAHelper")
	if os.environ.get('PROCESSOR_ARCHITEW6432')=='AMD64':
		_remoteLoader64=subprocess.Popen('lib64/nvdaHelperRemoteLoader.exe',stdin=subprocess.PIPE,stdout=file("nul","w"),stderr=subprocess.STDOUT)
	winEventHookID=winUser.setWinEventHook(EVENT_TYPEDCHARACTER,EVENT_INPUTLANGCHANGE,0,winEventCallback,0,0,0)

def terminate():
	global _remoteLib, _remoteLoader64, localLib
	winUser.unhookWinEvent(winEventHookID)
	if _remoteLib.nvdaHelper_terminate() < 0:
		raise RuntimeError("Error terminating NVDAHelper")
	_remoteLib=None
	if _remoteLoader64:
		_remoteLoader64.stdin.close()
		_remoteLoader64.wait()
		_remoteLoader64=None
	localLib=None
