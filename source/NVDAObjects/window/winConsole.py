#NVDAObjects/WinConsole.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2007-2010 Michael Curran <mick@kulgan.net>, James Teh <jamie@jantrid.net>

import winConsoleHandler
from . import Window
from ..behaviors import Terminal, EditableTextWithoutAutoSelectDetection
import controlTypes
import api

class WinConsole(Terminal, EditableTextWithoutAutoSelectDetection, Window):

	def _get_TextInfo(self):
		consoleObject=winConsoleHandler.consoleObject
		if consoleObject and self.windowHandle == consoleObject.windowHandle:
			return winConsoleHandler.WinConsoleTextInfo
		return super(WinConsole,self).TextInfo

	def event_becomeNavigatorObject(self):
		if winConsoleHandler.consoleObject is not self:
			if winConsoleHandler.consoleObject:
				winConsoleHandler.disconnectConsole()
			winConsoleHandler.connectConsole(self)
			if self == api.getFocusObject():
				# The user is returning to the focus object with object navigation.
				# The focused console should always be monitored if possible.
				self.startMonitoring()
		super(WinConsole,self).event_becomeNavigatorObject()

	def event_gainFocus(self):
		if winConsoleHandler.consoleObject is not self:
			if winConsoleHandler.consoleObject:
				winConsoleHandler.disconnectConsole()
			winConsoleHandler.connectConsole(self)
		super(WinConsole, self).event_gainFocus()

	def event_loseFocus(self):
		super(WinConsole, self).event_loseFocus()
		if winConsoleHandler.consoleObject is self:
			winConsoleHandler.disconnectConsole()

	def event_nameChange(self):
		pass

	def _getTextLines(self):
		return winConsoleHandler.getConsoleVisibleLines()
