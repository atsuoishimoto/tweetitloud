#nvda.pyw
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2008 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

"""The NVDA launcher. It can handle some command-line arguments (including help). It sets up logging, and then starts the core."""
 
import ctypes
import os
import sys
import locale
import gettext
import time
import optparse
import win32con
import globalVars
import config
import logHandler
from logHandler import log
import winUser
import winKernel

class NoConsoleOptionParser(optparse.OptionParser):
	"""A commandline option parser that shows its messages using dialogs,  as this pyw file has no dos console window associated with it"""

	def print_help(self, file=None):
		"""Shows help in a standard Windows message dialog"""
		winUser.MessageBox(0, unicode(self.format_help()), u"Help", 0)

	def error(self, msg):
		"""Shows an error in a standard Windows message dialog, and then exits NVDA"""
		out = ""
		if self.usage:
			out = self.get_usage()
		out += "\nerror: %s" % msg
		winUser.MessageBox(0, unicode(out), u"Error", 0)
		sys.exit(2)

globalVars.startTime=time.time()

if getattr(sys, "frozen", None):
	# We are running as an executable.
	# Append the path of the executable to sys so we can import modules from the dist dir.
	sys.path.append(sys.prefix)
	os.chdir(sys.prefix)
else:
	#We should always change directory to the location of this module (nvda.pyw), don't rely on sys.path[0]
	os.chdir(os.path.normpath(os.path.dirname(__file__)))

#Localization settings
locale.setlocale(locale.LC_ALL,'')
try:
	gettext.translation('nvda',localedir='locale',languages=[locale.getlocale()[0]]).install(True)
except:
	gettext.install('nvda',unicode=True)

#Process option arguments
parser=NoConsoleOptionParser()
parser.add_option('-q','--quit',action="store_true",dest='quit',default=False,help="Quit already running copy of NVDA")
parser.add_option('-r','--replace',action="store_true",dest='replace',default=False,help="Quit already running copy of NVDA and start this one")
parser.add_option('-k','--check-running',action="store_true",dest='check_running',default=False,help="Report whether NVDA is running via the exit code; 0 if running, 1 if not running")
parser.add_option('-f','--log-file',dest='logFileName',help="The file where log messages should be written to")
parser.add_option('-l','--log-level',type="int",dest='logLevel',default=0,help="The lowest level of message logged (debug 10, info 20, warning 30, error 40, critical 50), default is warning") 
parser.add_option('-c','--config-path',dest='configPath',default=config.getUserDefaultConfigPath(),help="The path where all settings for NVDA are stored")
parser.add_option('-m','--minimal',action="store_true",dest='minimal',default=False,help="No sounds, no interface, no start message etc")
parser.add_option('-s','--secure',action="store_true",dest='secure',default=False,help="Secure mode (disable Python console)")
parser.add_option('--no-sr-flag',action="store_false",dest='changeScreenReaderFlag',default=True,help="Don't change the global system screen reader flag")
(globalVars.appArgs,extraArgs)=parser.parse_args()

def terminateRunningNVDA(window):
	processID,threadID=winUser.getWindowThreadProcessID(window)
	winUser.PostMessage(window,win32con.WM_QUIT,0,0)
	h=winKernel.openProcess(winKernel.SYNCHRONIZE,False,processID)
	if not h:
		# The process is already dead.
		return
	try:
		res=winKernel.waitForSingleObject(h,4000)
		if res==0:
			# The process terminated within the timeout period.
			return
	finally:
		winKernel.closeHandle(h)

	# The process is refusing to exit gracefully, so kill it forcefully.
	h = winKernel.openProcess(winKernel.PROCESS_TERMINATE, False, processID)
	if not h:
		raise OSError("Could not open process for termination")
	try:
		winKernel.TerminateProcess(h, 1)
	finally:
		winKernel.closeHandle(h)

#Handle running multiple instances of NVDA
try:
	oldAppWindowHandle=winUser.FindWindow(u'wxWindowClassNR',u'NVDA')
except:
	oldAppWindowHandle=0
if not winUser.isWindow(oldAppWindowHandle):
	oldAppWindowHandle=0
if oldAppWindowHandle and (globalVars.appArgs.quit or globalVars.appArgs.replace):
	try:
		terminateRunningNVDA(oldAppWindowHandle)
	except:
		sys.exit(1)
if globalVars.appArgs.quit or (oldAppWindowHandle and not globalVars.appArgs.replace):
	sys.exit(0)
elif globalVars.appArgs.check_running:
	# NVDA is not running.
	sys.exit(1)

#Ensure multiple instances are not fully started by using a mutex
from nvda_service import getInputDesktopName
ERROR_ALREADY_EXISTS=0XB7
desktopName=getInputDesktopName().split("\\")[1]
mutex=ctypes.windll.kernel32.CreateMutexW(None,True,u"Local\\NVDA_%s"%desktopName)
if not mutex or ctypes.windll.kernel32.GetLastError()==ERROR_ALREADY_EXISTS:
	if mutex: ctypes.windll.kernel32.CloseHandle(mutex)
	sys.exit(1)

#Initialize the config path (make sure it exists)
config.initConfigPath()

#os.environ['PYCHECKER']="--limit 10000 -q --changetypes"
#import pychecker.checker
#Initial logging and logging code

logLevel=globalVars.appArgs.logLevel
if logLevel<=0:
	logLevel=log.INFO
logHandler.initialize()
logHandler.log.setLevel(logLevel)

log.info("Starting NVDA")
if globalVars.appArgs.changeScreenReaderFlag:
	winUser.setSystemScreenReaderFlag(True)
#Accept wm_quit from other processes, even if running with higher privilages
try:
	if not ctypes.windll.user32.ChangeWindowMessageFilter(win32con.WM_QUIT,1):
		raise WinError()
except AttributeError:
	pass
# Make this the last application to be shut down and don't display a retry dialog box.
winKernel.SetProcessShutdownParameters(0x100, winKernel.SHUTDOWN_NORETRY)
try:
	import core
	core.main()
except:
	log.critical("core failure",exc_info=True)
	sys.exit(1)
finally:
	if globalVars.appArgs.changeScreenReaderFlag:
		winUser.setSystemScreenReaderFlag(False)
	ctypes.windll.kernel32.CloseHandle(mutex)

log.info("NVDA exit")
