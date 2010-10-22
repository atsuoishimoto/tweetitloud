#scriptHandler.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2008 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
import weakref
import inspect
import appModuleHandler
import api
import queueHandler
from logHandler import log

_numScriptsQueued=0 #Number of scripts that are queued to be executed
_lastScriptTime=0 #Time in MS of when the last script was executed
_lastScriptRef=None #Holds a weakref to the last script that was executed
_lastScriptCount=0 #The amount of times the last script was repeated
_isScriptRunning=False

def findScript(gesture):
	return findScript_appModuleLevel(gesture)

def findScript_appModuleLevel(gesture):
	focusObject=api.getFocusObject()
	if not focusObject:
		return None
	appModule=focusObject.appModule
	if appModule and appModule.selfVoicing:
		return
	func=appModule.getScript(gesture) if appModule else None
	if func:
		return func
	return findScript_treeInterceptorLevel(gesture)

def findScript_treeInterceptorLevel(gesture):
	treeInterceptor=api.getFocusObject().treeInterceptor
	if treeInterceptor and treeInterceptor.isReady:
		func=treeInterceptor.getScript(gesture)
		if func and (not treeInterceptor.passThrough or getattr(func,"ignoreTreeInterceptorPassThrough",False)):
			return func
	return findScript_NVDAObjectLevel(gesture)

def findScript_NVDAObjectLevel(gesture):
	focusObj=api.getFocusObject()
	func=focusObj.getScript(gesture)
	if func:
		return func
	ancestors=reversed(api.getFocusAncestors())
	for obj in ancestors:
		func=obj.getScript(gesture)
		if func and getattr(func,'canPropagate',False): 
			return func
	return None

def getScriptName(script):
	return script.__name__[7:]

def _queueScriptCallback(script,gesture):
	global _numScriptsQueued
	_numScriptsQueued-=1
	executeScript(script,gesture)

def queueScript(script,gesture):
	global _numScriptsQueued
	_numScriptsQueued+=1
	queueHandler.queueFunction(queueHandler.eventQueue,_queueScriptCallback,script,gesture)

def executeScript(script,gesture):
	"""Executes a given script (function) passing it the given gesture.
	It also keeps track of the execution of duplicate scripts with in a certain amount of time, and counts how many times this happens.
	Use L{getLastScriptRepeatCount} to find out this count value.
	@param script: the function or method that should be executed. The function or method must take an argument of 'gesture'.
	@type script: callable.
	@param gesture: the input gesture that activated this script
	@type gesture: L{inputCore.InputGesture}
	"""
	global _lastScriptTime, _lastScriptCount, _lastScriptRef, _isScriptRunning 
	lastScriptRef=_lastScriptRef() if _lastScriptRef else None
	#We don't allow the same script to be executed from with in itself, but we still should pass the key through
	if _isScriptRunning and lastScriptRef==script.im_func:
		return gesture.send()
	_isScriptRunning=True
	try:
		scriptTime=time.time()
		scriptRef=weakref.ref(script.im_func)
		if (scriptTime-_lastScriptTime)<=0.5 and script.im_func==lastScriptRef:
			_lastScriptCount+=1
		else:
			_lastScriptCount=0
		_lastScriptRef=scriptRef
		_lastScriptTime=scriptTime
		script(gesture)
	except:
		log.exception("error executing script: %s with gesture %r"%(script,gesture.displayName))
	finally:
		_isScriptRunning=False

def getLastScriptRepeatCount():
	"""The count of how many times the most recent script has been executed.
	This should only be called from with in a script.
	@returns: a value greater or equal to 0. If the script has not been repeated it is 0, if it has been repeated once its 1, and so forth.
	@rtype: integer
	"""
	if (time.time()-_lastScriptTime)>0.5:
		return 0
	else:
		return _lastScriptCount

def isScriptWaiting():
	return bool(_numScriptsQueued)

def isCurrentScript(scriptFunc):
	"""Finds out if the given script is equal to the script that L{isCurrentScript} is being called from.
	@param scriptFunc: the script retreaved from ScriptableObject.getScript(gesture)
	@type scriptFunc: Instance method
	@returns: True if they are equal, False otherwise
	@rtype: boolean
	"""
	try:
	 	givenFunc=getattr(scriptFunc.im_self.__class__,scriptFunc.__name__)
	except AttributeError:
		log.debugWarning("Could not get unbound method from given script",exc_info=True) 
		return False
	parentFrame=inspect.currentframe().f_back
	try:
		realObj=parentFrame.f_locals['self']
	except KeyError:
		log.debugWarning("Could not get self instance from parent frame instance method",exc_info=True)
		return False
	try:
		realFunc=getattr(realObj.__class__,parentFrame.f_code.co_name)
	except AttributeError:
		log.debugWarning("Could not get unbound method from parent frame instance",exc_info=True)
		return False
	return givenFunc==realFunc
