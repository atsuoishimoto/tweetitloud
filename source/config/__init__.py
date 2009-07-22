"""Manages NVDA configuration.
""" 

import globalVars
import _winreg
import os
import sys
from cStringIO import StringIO
from configobj import ConfigObj
from validate import Validator
from logHandler import log
import shlobj

val = Validator()

#: The configuration specification
#: @type: ConfigObj
confspec = ConfigObj(StringIO(
"""# NVDA Configuration File

[general]
	language = string(default="Windows")
	saveConfigurationOnExit = boolean(default=False)
	askToExit = boolean(default=true)
	#possible log levels are DEBUG, IO, DEBUGWARNING, INFO
	loggingLevel = string(default="INFO")
	showWelcomeDialogAtStartup = boolean(default=true)

# Speech settings
[speech]
	# The synthesiser to use
	synth = string(default=auto)
	speakPunctuation = boolean(default=False)
	beepSpeechModePitch = integer(default=10000,min=50,max=11025)
outputDevice = string(default=default)

	[[__many__]]
		variant = string(default=None)
		rate = integer(default=50,min=0,max=100)
		pitch = integer(default=50,min=0,max=100)
		inflection = integer(default=50,min=0,max=100)
		capPitchChange = integer(default=30,min=-100,max=100)
		volume = integer(default=100,min=0,max=100)
		voice = string()
		raisePitchForCapitals = boolean(default=true)
		sayCapForCapitals = boolean(default=false)
		beepForCapitals = boolean(default=false)
		useSpellingFunctionality = boolean(default=true)

# Braille settings
[braille]
	display = string(default=noBraille)
	translationTable = string(default=en-us-comp8.ctb)
	expandAtCursor = boolean(default=true)
	cursorBlinkRate = integer(default=500,min=0,max=2000)
	messageTimeout = integer(default=4,min=1,max=20)

# Presentation settings
[presentation]
		reportClassOfClientObjects = boolean(default=false)
		reportKeyboardShortcuts = boolean(default=true)
		reportObjectPositionInformation = boolean(default=true)
		reportTooltips = boolean(default=false)
		reportHelpBalloons = boolean(default=true)
		reportObjectDescriptions = boolean(default=True)
	[[progressBarUpdates]]
		reportBackgroundProgressBars = boolean(default=false)
		#output modes are beep, speak, both, or off
		progressBarOutputMode = string(default="beep")
		speechPercentageInterval = integer(default=10)
		beepPercentageInterval = integer(default=1)
		beepMinHZ = integer(default=110)

[mouse]
	enableMouseTracking = boolean(default=True) #must be true for any of the other settings to work
	reportTextUnderMouse = boolean(default=True)
	mouseTextUnit = string(default="paragraph")
	reportObjectRoleOnMouseEnter = boolean(default=False)
	audioCoordinatesOnMouseMove = boolean(default=False)
	audioCoordinates_detectBrightness = boolean(default=False)
	audioCoordinates_blurFactor = integer(default=3)
	audioCoordinates_minVolume = float(default=0.1)
	audioCoordinates_maxVolume = float(default=1.0)
	audioCoordinates_minPitch = integer(default=220)
	audioCoordinates_maxPitch = integer(default=880)
	reportMouseShapeChanges = boolean(default=false)

#Keyboard settings
[keyboard]
	useCapsLockAsNVDAModifierKey = boolean(default=false)
	useNumpadInsertAsNVDAModifierKey = boolean(default=true)
	useExtendedInsertAsNVDAModifierKey = boolean(default=true)
	keyboardLayout = string(default="desktop")
	speakTypedCharacters = boolean(default=true)
	speakTypedWords = boolean(default=false)
	speakCommandKeys = boolean(default=false)

[virtualBuffers]
	maxLineLength = integer(default=100)
	linesPerPage = integer(default=25)
	useScreenLayout = boolean(default=True)
	reportVirtualPresentationOnFocusChanges = boolean(default=true)
	updateContentDynamically = boolean(default=true)
	autoPassThroughOnFocusChange = boolean(default=true)
	autoPassThroughOnCaretMove = boolean(default=false)
	passThroughAudioIndication = boolean(default=true)

#Settings for document reading (such as MS Word and wordpad)
[documentFormatting]
	#These settings affect what information is reported when you navigate to text where the formatting  or placement has changed
	detectFormatAfterCursor = boolean(default=false)
	reportFontName = boolean(default=false)
	reportFontSize = boolean(default=false)
	reportFontAttributes = boolean(default=false)
	reportAlignment = boolean(default=false)
	reportStyle = boolean(default=false)
	reportSpellingErrors = boolean(default=true)
	reportPage = boolean(default=true)
	reportLineNumber = boolean(default=False)
	reportTables = boolean(default=true)
	includeLayoutTables = boolean(default=False)
	reportLinks = boolean(default=true)
	reportLists = boolean(default=true)
	reportHeadings = boolean(default=true)
	reportBlockQuotes = boolean(default=true)
"""
), list_values=False, encoding="UTF-8")
confspec.newlines = "\r\n"

#: The active configuration, C{None} if it has not yet been loaded.
#: @type: ConfigObj
conf = None

def load():
	"""Loads the configuration from the configFile.
	It also takes note of the file's modification time so that L{save} won't lose any changes made to the file while NVDA is running. 
	"""
	global conf
	configFileName=os.path.join(globalVars.appArgs.configPath,"nvda.ini")
	conf = ConfigObj(configFileName, configspec = confspec, indent_type = "\t", encoding="UTF-8")
	# Python converts \r\n to \n when reading files in Windows, so ConfigObj can't determine the true line ending.
	conf.newlines = "\r\n"
	conf.validate(val)

def updateSynthConfig(name):
	"""Makes sure that the config contains a specific synth section for the given synth name.
@param name: the synth name
@type name: string
""" 
	speech = conf["speech"]
	# If there are no settings for this synth, make sure there are defaults.
	if not speech.has_key(name):
		speech[name] = {}
		conf.validate(val, copy = True)
		return True
	else:
		return False

def save():
	"""Saves the configuration to the config file.
	"""
	global conf
	if not os.path.isdir(globalVars.appArgs.configPath):
		try:
			os.makedirs(globalVars.appArgs.configPath)
		except OSError, e:
			log.warning("Could not create configuration directory")
			log.debugWarning("", exc_info=True)
			raise e
	try:
		# Copy default settings and formatting.
		conf.validate(val, copy = True)
		conf.write()
		log.info("Configuration saved")
	except Exception, e:
		log.warning("Could not save configuration - probably read only file system")
		log.debugWarning("", exc_info=True)
		raise e

def saveOnExit():
	"""Save the configuration if configured to save on exit.
	This should only be called if NVDA is about to exit.
	Errors are ignored.
	"""
	if conf["general"]["saveConfigurationOnExit"]:
		try:
			save()
		except:
			pass

def isInstalledCopy():
	"""Checks to see if this running copy of NVDA is installed on the system"""
	try:
		k=_winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE,"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\NVDA")
		instDir=_winreg.QueryValueEx(k,"UninstallDirectory")[0]
	except WindowsError:
		return False
	_winreg.CloseKey(k)
	try:
		return os.stat(instDir)==os.stat(os.getcwdu()) 
	except WindowsError:
		return False

def getUserDefaultConfigPath():
	if isInstalledCopy():
		try:
			return os.path.join(shlobj.SHGetFolderPath(0, shlobj.CSIDL_APPDATA), "nvda")
		except WindowsError:
			pass
	return u'.\\'

def getSystemConfigPath():
	if isInstalledCopy():
		try:
			return os.path.join(shlobj.SHGetFolderPath(0, shlobj.CSIDL_COMMON_APPDATA), "nvda")
		except WindowsError:
			pass
	return None

RUN_REGKEY = ur"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"

def getStartAfterLogon():
	try:
		k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, RUN_REGKEY)
		val = _winreg.QueryValueEx(k, u"nvda")[0]
		return os.stat(val) == os.stat(sys.argv[0])
	except (WindowsError, OSError):
		return False

def setStartAfterLogon(enable):
	if getStartAfterLogon() == enable:
		return
	k = _winreg.OpenKey(_winreg.HKEY_CURRENT_USER, RUN_REGKEY, 0, _winreg.KEY_WRITE)
	if enable:
		_winreg.SetValueEx(k, u"nvda", None, _winreg.REG_SZ, sys.argv[0])
	else:
		_winreg.DeleteValue(k, u"nvda")

SERVICE_FILENAME = u"nvda_service.exe"

def isServiceInstalled():
	if not os.path.isfile(SERVICE_FILENAME):
		return False
	try:
		k = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, ur"SYSTEM\CurrentControlSet\Services\nvda")
		val = _winreg.QueryValueEx(k, u"ImagePath")[0].replace(u'"', u'')
		return os.stat(val) == os.stat(SERVICE_FILENAME)
	except (WindowsError, OSError):
		return False

def execElevated(path, params=None, wait=False):
	import shellapi
	import winKernel
	import winUser
	sei = shellapi.SHELLEXECUTEINFO(lpVerb=u"runas", lpFile=os.path.abspath(path), lpParameters=params, nShow=winUser.SW_HIDE)
	if wait:
		sei.fMask = shellapi.SEE_MASK_NOCLOSEPROCESS
	shellapi.ShellExecuteEx(sei)
	if wait:
		try:
			winKernel.waitForSingleObject(sei.hProcess, winKernel.INFINITE)
			return winKernel.GetExitCodeProcess(sei.hProcess)
		finally:
			winKernel.closeHandle(sei.hProcess)

SLAVE_FILENAME = u"nvda_slave.exe"

NVDA_REGKEY = ur"SOFTWARE\NVDA"

def getStartOnLogonScreen():
	try:
		k = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, NVDA_REGKEY)
		return bool(_winreg.QueryValueEx(k, u"startOnLogonScreen")[0])
	except WindowsError:
		return False

def _setStartOnLogonScreen(enable):
	k = _winreg.OpenKey(_winreg.HKEY_LOCAL_MACHINE, NVDA_REGKEY, 0, _winreg.KEY_WRITE)
	_winreg.SetValueEx(k, u"startOnLogonScreen", None, _winreg.REG_DWORD, int(enable))

def setStartOnLogonScreen(enable):
	if getStartOnLogonScreen() == enable:
		return
	try:
		# Try setting it directly.
		_setStartOnLogonScreen(enable)
	except WindowsError:
		# We probably don't have admin privs, so we need to elevate to do this using the slave.
		if execElevated(SLAVE_FILENAME, "config_setStartOnLogonScreen %d" % enable, wait=True) != 0:
			raise RuntimeError("Slave failed to set startOnLogonScreen")

def getConfigDirs(subpath=None):
	"""Retrieve all directories that should be used when searching for configuration.
	IF C{subpath} is provided, it will be added to each directory returned.
	@param subpath: The path to be added to each directory, C{None} for none.
	@type subpath: str
	@return: The configuration directories in the order in which they should be searched.
	@rtype: list of str
	"""
	return [os.path.join(dir, subpath) if subpath else dir
		for dir in (getUserDefaultConfigPath(),)
	]

def addConfigDirsToPythonPackagePath(module, subdir=None):
	"""Add the configuration directories to the module search path (__path__) of a Python package.
	C{subdir} is added to each configuration directory. It defaults to the name of the Python package.
	@param module: The root module of the package.
	@type module: module
	@param subdir: The subdirectory to be used, C{None} for the name of C{module}.
	@type subdir: str
	"""
	if not subdir:
		subdir = module.__name__
	dirs = getConfigDirs(subdir)
	dirs.extend(module.__path__ )
	module.__path__ = dirs
