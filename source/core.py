#core.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2008 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

"""NVDA core"""

# Do this first to initialise comtypes.client.gen_dir and the comtypes.gen search path.
import comtypes.client
# Append our comInterfaces directory to the comtypes.gen search path.
import comtypes.gen
import comInterfaces
comtypes.gen.__path__.append(comInterfaces.__path__[0])

#Monkey patch comtypes to support byref in variants
from comtypes.automation import VARIANT, VT_BYREF
from ctypes import cast, c_void_p
from _ctypes import _Pointer
oldVARIANT_value_fset=VARIANT.value.fset
def newVARIANT_value_fset(self,value):
	realValue=value
	if isinstance(value,_Pointer):
		try:
			value=value.contents
		except (NameError,AttributeError):
			pass
	oldVARIANT_value_fset(self,value)
	if realValue is not value:
		self.vt|=VT_BYREF
		self._.c_void_p=cast(realValue,c_void_p)
VARIANT.value=property(VARIANT.value.fget,newVARIANT_value_fset,VARIANT.value.fdel)

#Monkeypatch comtypes lazybind dynamic IDispatch support to fallback to the more basic dynamic IDispatch support if the former does not work
#Example: ITypeComp.bind gives back a vardesc, which comtypes does not yet support
import comtypes.client.lazybind
old__getattr__=comtypes.client.lazybind.Dispatch.__getattr__
def new__getattr__(self,name):
	try:
		return old__getattr__(self,name)
	except (NameError, AttributeError):
		return getattr(comtypes.client.dynamic._Dispatch(self._comobj),name)
comtypes.client.lazybind.Dispatch.__getattr__=new__getattr__



import sys
import nvwave
import os
import time
import logHandler
import globalVars
from logHandler import log

# Work around an issue with comtypes where __del__ seems to be called twice on COM pointers.
# This causes Release() to be called more than it should, which is very nasty and will eventually cause us to access pointers which have been freed.
from comtypes import _compointer_base
_cpbDel = _compointer_base.__del__
def newCpbDel(self):
	if hasattr(self, "_deleted"):
		# Don't allow this to be called more than once.
		log.debugWarning("COM pointer %r already deleted" % self)
		return
	_cpbDel(self)
	self._deleted = True
newCpbDel.__name__ = "__del__"
_compointer_base.__del__ = newCpbDel
del _compointer_base

def doStartupDialogs():
	import config
	import gui
	if config.conf["general"]["showWelcomeDialogAtStartup"]:
		gui.WelcomeDialog.run()
	if globalVars.configFileError:
		gui.ConfigFileErrorDialog.run()
	if globalVars.gestureMapFileError:
		import wx
		gui.scriptUI.MessageDialog(_("""Your gesture map file contains errors. 
More details about the errors can be found in the log file."""), _("gesture map File Error"), wx.OK|wx.ICON_EXCLAMATION).run()

def restart():
	"""Restarts NVDA by starting a new copy with -r."""
	import subprocess
	import shellapi
	shellapi.ShellExecute(None,None,unicode(sys.executable),unicode(subprocess.list2cmdline(sys.argv+['-r'])),None,0)

def resetConfiguration():
	"""Loads the configuration, installs the correct language support and initialises audio so that it will use the configured synth and speech settings.
	"""
	import config
	import braille
	import speech
	import languageHandler
	log.debug("Terminating braille")
	braille.terminate()
	log.debug("terminating speech")
	speech.terminate()
	log.debug("Reloading config")
	config.load()
	logHandler.setLogLevelFromConfig()
	#Language
	lang = config.conf["general"]["language"]
	log.debug("setting language to %s"%lang)
	languageHandler.setLanguage(lang)
	#Speech
	log.debug("initializing speech")
	speech.initialize()
	#braille
	log.debug("Initializing braille")
	braille.initialize()
	log.info("Reverted to saved configuration")

def main():
	"""NVDA's core main loop.
This initializes all modules such as audio, IAccessible, keyboard, mouse, and GUI. Then it initialises the wx application object and installs the core pump timer, which checks the queues and executes functions every 1 ms. Finally, it starts the wx main loop.
"""
	log.debug("Core starting")
	log.info("Config dir: %s"%os.path.abspath(globalVars.appArgs.configPath))
	log.debug("loading config")
	import config
	config.load()
	if not globalVars.appArgs.minimal:
		try:
			nvwave.playWaveFile("waves\\start.wav")
		except:
			pass
	logHandler.setLogLevelFromConfig()
	try:
		lang = config.conf["general"]["language"]
		import languageHandler
		log.debug("setting language to %s"%lang)
		languageHandler.setLanguage(lang)
	except:
		log.warning("Could not set language to %s"%lang)
	import versionInfo
	log.info("NVDA version %s" % versionInfo.version)
	log.info("Using Windows version %r" % (sys.getwindowsversion(),))
	log.info("Using Python version %s"%sys.version)
	log.info("Using comtypes version %s"%comtypes.__version__)
	log.debug("Creating wx application instance")
	import speechDictHandler
	log.debug("Speech Dictionary processing")
	speechDictHandler.initialize()
	import speech
	log.debug("Initializing speech")
	speech.initialize()
	if not globalVars.appArgs.minimal and (time.time()-globalVars.startTime)>5:
		log.debugWarning("Slow starting core (%.2f sec)" % (time.time()-globalVars.startTime))
		speech.speakMessage(_("Loading NVDA. Please wait..."))
	import wx
	log.info("Using wx version %s"%wx.version())
	app = wx.App(redirect=False)
	# HACK: wx currently raises spurious assertion failures when a timer is stopped but there is already an event in the queue for that timer.
	# Unfortunately, these assertion exceptions are raised in the middle of other code, which causes problems.
	# Therefore, disable assertions for now.
	app.SetAssertMode(wx.PYAPP_ASSERT_SUPPRESS)
	# We do support QueryEndSession events, but we don't want to do anything for them.
	app.Bind(wx.EVT_QUERY_END_SESSION, lambda evt: None)
	def onEndSession(evt):
		# NVDA will be terminated as soon as this function returns, so save configuration if appropriate.
		config.saveOnExit()
		speech.cancelSpeech()
		if not globalVars.appArgs.minimal:
			try:
				nvwave.playWaveFile("waves\\exit.wav",async=False)
			except:
				pass
		log.info("Windows session ending")
	app.Bind(wx.EVT_END_SESSION, onEndSession)
	import braille
	log.debug("Initializing braille")
	braille.initialize()
	import NVDAHelper
	log.debug("Initializing NVDAHelper")
	NVDAHelper.initialize()
	import displayModel
	log.debug("Initializing displayModel")
	displayModel.initialize()
	log.debug("Initializing GUI")
	import gui
	gui.initialize()
	# initialize wxpython localization support
	locale = wx.Locale()
	lang=languageHandler.getLanguage()
	if '_' in lang:
		wxLang=lang.split('_')[0]
	else:
		wxLang=lang
	if hasattr(sys,'frozen'):
		locale.AddCatalogLookupPathPrefix(os.path.join(os.getcwdu(),"locale"))
	try:
		locale.Init(lang,wxLang)
	except:
		pass
	import appModuleHandler
	log.debug("Initializing appModule Handler")
	appModuleHandler.initialize()
	import api
	import winUser
	import NVDAObjects.window
	desktopObject=NVDAObjects.window.Window(windowHandle=winUser.getDesktopWindow())
	api.setDesktopObject(desktopObject)
	api.setFocusObject(desktopObject)
	api.setNavigatorObject(desktopObject)
	api.setMouseObject(desktopObject)
	import JABHandler
	log.debug("initializing Java Access Bridge support")
	JABHandler.initialize()
	import winConsoleHandler
	log.debug("Initializing winConsole support")
	winConsoleHandler.initialize()
	import UIAHandler
	log.debug("Initializing UIA support")
	try:
		UIAHandler.initialize()
	except NotImplementedError:
		log.warning("UIA not available")
	except:
		log.error("Error initializing UIA support", exc_info=True)
	import IAccessibleHandler
	log.debug("Initializing IAccessible support")
	IAccessibleHandler.initialize()
	log.debug("Initializing input core")
	import inputCore
	inputCore.initialize()
	import keyboardHandler
	log.debug("Initializing keyboard handler")
	keyboardHandler.initialize()
	import mouseHandler
	log.debug("initializing mouse handler")
	mouseHandler.initialize()
	import globalPluginHandler
	log.debug("Initializing global plugin handler")
	globalPluginHandler.initialize()
	if not globalVars.appArgs.minimal:
		try:
			braille.handler.message(_("NVDA started"))
		except:
			log.error("", exc_info=True)
		wx.CallAfter(doStartupDialogs)
	if api.getFocusObject()==api.getDesktopObject():
		import eventHandler
		try:
			focus=api.getDesktopObject().objectWithFocus()
			if focus:
				eventHandler.queueEvent('gainFocus',focus)
		except:
			log.exception("Error retrieving initial focus")
	import queueHandler
	import watchdog
	import baseObject
	class CorePump(wx.Timer):
		"Checks the queues and executes functions."
		def __init__(self,*args,**kwargs):
			log.debug("Core pump starting")
			super(CorePump,self).__init__(*args,**kwargs)
		def Notify(self):
			try:
				JABHandler.pumpAll()
				IAccessibleHandler.pumpAll()
				queueHandler.pumpAll()
				mouseHandler.pumpAll()
			except:
				log.exception("errors in this core pump cycle")
			baseObject.AutoPropertyObject.invalidateCaches()
			watchdog.alive()
	log.debug("starting core pump")
	pump = CorePump()
	pump.Start(1)
	log.debug("Initializing watchdog")
	watchdog.initialize()
	log.info("NVDA initialized")

	log.debug("entering wx application main loop")
	app.MainLoop()

	log.info("Exiting")
	log.debug("Terminating watchdog")
	watchdog.terminate()
	log.debug("Terminating GUI")
	gui.terminate()
	config.saveOnExit()
	try:
		if globalVars.focusObject and hasattr(globalVars.focusObject,"event_loseFocus"):
			log.debug("calling lose focus on object with focus")
			globalVars.focusObject.event_loseFocus()
	except:
		log.error("Lose focus error",exc_info=True)
	try:
		speech.cancelSpeech()
	except:
		pass
	log.debug("Cleaning up running treeInterceptors")
	try:
		import treeInterceptorHandler
		treeInterceptorHandler.terminate()
	except:
		log.error("Error cleaning up treeInterceptors",exc_info=True)
	log.debug("Terminating global plugin handler")
	globalPluginHandler.terminate()
	log.debug("Terminating IAccessible support")
	try:
		IAccessibleHandler.terminate()
	except:
		log.error("Error terminating IAccessible support",exc_info=True)
	log.debug("Terminating UIA support")
	try:
		UIAHandler.terminate()
	except:
		log.error("Error terminating UIA support",exc_info=True)
	log.debug("Terminating winConsole support")
	try:
		winConsoleHandler.terminate()
	except:
		log.error("Error terminating winConsole support",exc_info=True)
	log.debug("Terminating Java Access Bridge support")
	try:
		JABHandler.terminate()
	except:
		log.error("Error terminating Java Access Bridge support",exc_info=True)
	log.debug("Terminating app module handler")
	appModuleHandler.terminate()
	log.debug("Terminating NVDAHelper")
	try:
		NVDAHelper.terminate()
	except:
		log.error("Error terminating NVDAHelper",exc_info=True)
	log.debug("Terminating keyboard handler")
	try:
		keyboardHandler.terminate()
	except:
		log.error("Error terminating keyboard handler")
	log.debug("Terminating mouse handler")
	try:
		mouseHandler.terminate()
	except:
		log.error("error terminating mouse handler",exc_info=True)
	log.debug("Terminating input core")
	try:
		inputCore.terminate()
	except:
		log.error("error terminating input core",exc_info=True)
	log.debug("Terminating braille")
	try:
		braille.terminate()
	except:
		log.error("Error terminating braille",exc_info=True)
	log.debug("Terminating speech")
	try:
		speech.terminate()
	except:
		log.error("Error terminating speech",exc_info=True)
	if not globalVars.appArgs.minimal:
		try:
			nvwave.playWaveFile("waves\\exit.wav",async=False)
		except:
			pass
	log.debug("core done")
