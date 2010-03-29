#brailleDisplayDrivers/alvaBC6.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2009 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import braille
import queueHandler
from logHandler import log
from ctypes import *
import time
import wx
import config
from keyboardHandler import KeyboardInputGesture

ALVA_KEY_CHECK_INTERVAL = 50
ALVA_NO_KEY = 0xFFFF

ALVA_FRONT_GROUP = 0x71
ALVA_ET_GROUP = 0x72
ALVA_SP_GROUP = 0x73
ALVA_CR_GROUP = 0x74
ALVA_MODIFIER_GROUP = 0x75
ALVA_ASCII_GROUP = 0x76
ALVA_RELEASE_MASK = 0x8000

ALVA_SP1 = (1 << 0)
ALVA_SP2 = (1 << 1)
ALVA_SP_LEFT = (1 << 2)
ALVA_SP_ENTER = (1 << 3)
ALVA_SP_UP = (1 << 4)
ALVA_SP_DOWN = (1 << 5)
ALVA_SP_RIGHT = (1 << 6)
ALVA_SP3 = (1 << 7)
ALVA_SP4 = (1 << 8)
# Only for BC680
ALVA_SPR1 = (1 << 9)
ALVA_SPR2 = (1 << 10)
ALVA_SPR_LEFT = (1 << 11)
ALVA_SPR_ENTER = (1 << 12)
ALVA_SPR_UP = (1 << 13)
ALVA_SPR_DOWN = (1 << 14)
ALVA_SPR_RIGHT = ( 1 << 15)
ALVA_SPR3 = (1 << 16)
ALVA_SPR4 = (1 << 17)

# FRONT_KEY BITMAPS
ALVA_T1 = (1 << 18)
ALVA_T2 = (1 << 19)
ALVA_T3 = (1 << 20)
ALVA_T4 = 1 << 21
ALVA_T5 = 1 << 22
# Only for BC680
ALVA_R_T1 = 1 << 23
ALVA_R_T2 = 1 << 24
ALVA_R_T3 = 1 << 25
ALVA_R_T4 = 1 << 26
ALVA_R_T5 = 1 << 27

# eTouch keys
ALVA_ETOUCH1 = 1 << 28
ALVA_ETOUCH2 = 1 << 29
ALVA_ETOUCH3 = 1 << 30
ALVA_ETOUCH4 = 1 << 31

#Try to load alvaw32.dll
try:
	AlvaLib=windll[r"brailleDisplayDrivers\alvaw32.dll"]
except:
	AlvaLib=None

class BrailleDisplayDriver(braille.BrailleDisplayDriverWithCursor):
	name = "alvaBC6"
	description = _("ALVA BC640/680 series")

	@classmethod
	def check(cls):
		if AlvaLib:
			log.info("Alva library was loaded")
		else:
			log.info("Alva library was not loaded")

		return bool(AlvaLib)

	def __init__(self):
		super(BrailleDisplayDriver,self).__init__()
		log.debug("ALVA BC6xx Braille init")
		_AlvaNumDevices=c_int(0)
		AlvaLib.AlvaScanDevices(byref(_AlvaNumDevices))
		if _AlvaNumDevices.value==0:
			raise RuntimeError("No ALVA display found")
		else:
			log.info("%d devices found" %_AlvaNumDevices.value)
			AlvaLib.AlvaOpen(0)
			self._alva_NumCells = 0
			self._alva_KeyCheckTimer = wx.PyTimer(self._alva_CheckKeyPresses)
			self._alva_KeyMask = 0
			self._alva_KeyCheckTimer.Start(ALVA_KEY_CHECK_INTERVAL)

	def terminate(self):
		super(BrailleDisplayDriver, self).terminate()
		try:
			self._alva_KeyCheckTimer.Stop()
			self._alva_KeyCheckTimer = None
		except:
			pass
		AlvaLib.AlvaClose(1)

	def _get_numCells(self):
		if self._alva_NumCells==0:
			NumCells = c_int(0)
			AlvaLib.AlvaGetCells(0, byref(NumCells))
			if NumCells.value==0:
							raise RuntimeError("Cannot obtain number of cells")
			self._alva_NumCells = NumCells.value
			log.info("ALVA BC6xx has %d cells" %self._alva_NumCells)
		return self._alva_NumCells

	def _display(self, cells):
		#log.info("Display %d cells" %len(cells))
		cells="".join([chr(x) for x in cells])
		AlvaLib.AlvaSendBraille(0, cells, 0, len(cells))

	def _alva_CheckKeyPresses(self):
		Key = c_uint16(0)
		while True:
			try:
				AlvaLib.AlvaGetKey(0, 0, byref(Key))
			except:
				log.error("Error reading keypress from ALVAW32.DLL", exc_info=True)
				return
			if Key.value == ALVA_NO_KEY:
				break
			if Key.value & ALVA_RELEASE_MASK:
				self._alva_OnKeyRelease()
			else:
				self._alva_OnKeyPress(Key.value)

	def _alva_OnKeyPress(self, key):
		KeyGroup = (key >> 8) & 0xFF
		KeyNumber = key & 0xFF
		if KeyGroup == ALVA_FRONT_GROUP:
			self._alva_KeyMask = self._alva_KeyMask | ( ALVA_T1 << KeyNumber)
		elif KeyGroup == ALVA_ET_GROUP:
			self._alva_KeyMask = self._alva_KeyMask | ( ALVA_ETOUCH1 << KeyNumber)
		elif KeyGroup == ALVA_SP_GROUP:
			self._alva_KeyMask = self._alva_KeyMask | (ALVA_SP1 << KeyNumber)
		elif KeyGroup == ALVA_CR_GROUP:
			log.debug("CR key %d" %KeyNumber)
			braille.handler.routeTo(KeyNumber)

	def _alva_OnKeyRelease(self):
		_KeyMask = self._alva_KeyMask
		self._alva_KeyMask = 0

		if _KeyMask == ALVA_SP1 or _KeyMask == ALVA_SPR1: # Shift-TAB
			KeyboardInputGesture.fromName('shift+tab').send()

		elif _KeyMask == ALVA_SP2 or _KeyMask == ALVA_SPR2: # Alt
			KeyboardInputGesture.fromName('F10').send()

		elif _KeyMask == ALVA_SP3 or _KeyMask == ALVA_SPR3:    # ESC
			KeyboardInputGesture.fromName('escape').send()

		elif _KeyMask == ALVA_SP4 or _KeyMask == ALVA_SPR4: # Tab
			KeyboardInputGesture.fromName('Tab').send()

		elif _KeyMask == ALVA_SP_UP or _KeyMask == ALVA_SPR_UP: # Arrow up
			KeyboardInputGesture.fromName('extendedup').send()

		elif _KeyMask == ALVA_SP_DOWN or _KeyMask == ALVA_SPR_DOWN: # Arrow down
			KeyboardInputGesture.fromName('extendeddown').send()

		elif _KeyMask == ALVA_SP_LEFT or _KeyMask == ALVA_SPR_LEFT: #Arrow left
			KeyboardInputGesture.fromName('extendedleft').send()

		elif _KeyMask == ALVA_SP_RIGHT or _KeyMask == ALVA_SPR_RIGHT: #Arrow right
			KeyboardInputGesture.fromName('extendedright').send()

		elif _KeyMask == ALVA_SP_ENTER or _KeyMask == ALVA_SPR_ENTER: # enter key
			KeyboardInputGesture.fromName('return').send()

		elif _KeyMask == (ALVA_SP1 | ALVA_SP3) or _KeyMask == (ALVA_SPR1 | ALVA_SPR3): # control panel
			import gui
			gui.showGui()

		elif _KeyMask == (ALVA_SP1 | ALVA_SP4) or _KeyMask == (ALVA_SPR1 | ALVA_SPR4): #Minimiza all apps
			KeyboardInputGesture.fromName('win+d').send()

		elif _KeyMask == (ALVA_SP2 | ALVA_SP3) or _KeyMask == (ALVA_SPR2 | ALVA_SPR3): # Start menu
			KeyboardInputGesture.fromName('extendedlwin').send()

		elif _KeyMask == (ALVA_SP2 | ALVA_SP4) or _KeyMask == (ALVA_SPR2 | ALVA_SPR4): #Alt Tab
			KeyboardInputGesture.fromName('alt+tab').send()

		elif _KeyMask == ALVA_T1 or _KeyMask == ALVA_R_T1: # Scroll backwards
			braille.handler.scrollBack()

		elif _KeyMask == ALVA_T2 or _KeyMask == ALVA_R_T2: # Scroll line up
			if braille.handler.buffer.regions: 
				braille.handler.buffer.regions[-1].previousLine()

		elif _KeyMask == ALVA_T3 or _KeyMask == ALVA_R_T3: # Goto focus
			log.warning("Goto focus not yet implemented")

		elif _KeyMask == ALVA_T4 or _KeyMask == ALVA_R_T4: # Scroll line down
			if braille.handler.buffer.regions:
				braille.handler.buffer.regions[-1].nextLine()

		elif _KeyMask == ALVA_T5 or _KeyMask == ALVA_R_T5: # Scroll forward
			braille.handler.scrollForward()

		elif _KeyMask == (ALVA_T1 | ALVA_T2) or _KeyMask == (ALVA_R_T1 | ALVA_R_T2): # Braille top
			pass

		elif _KeyMask == (ALVA_T1 | ALVA_T3) or _KeyMask == (ALVA_R_T1 | ALVA_R_T3): # Set verbosity
			pass

		elif _KeyMask == (ALVA_T1 | ALVA_T4) or _KeyMask == (ALVA_R_T1 | ALVA_R_T4): # Change cursor shape
			self.cursorShape = 0xFF if self.cursorShape == 0xC0 else 0xC0

		elif _KeyMask == (ALVA_T1 | ALVA_T5) or _KeyMask == (ALVA_R_T1 | ALVA_R_T5): # Braille input on/off
			pass

		elif _KeyMask == (ALVA_T2 | ALVA_T4) or _KeyMask == (ALVA_R_T2 | ALVA_R_T4): # Braille toggle 8/6 dots
			pass

		elif _KeyMask == (ALVA_T2 | ALVA_T3) or _KeyMask == (ALVA_R_T2 | ALVA_R_T3): # Literary Braille on/off
			pass

		elif _KeyMask == (ALVA_T2 | ALVA_T5) or _KeyMask == (ALVA_R_T2 | ALVA_R_T5): # Braille cursor on/off
			self.cursorBlinkRate = 0 if self.cursorBlinkRate else config.conf["braille"]["cursorBlinkRate"]
			# cursorBlinkRate sets the cursor up, so we have to blink ourself one more time to switch the cursor off
			self._blink()

		elif _KeyMask == (ALVA_T4 | ALVA_T5) or _KeyMask == (ALVA_R_T4 | ALVA_R_T5): # Braille bottom
			pass
