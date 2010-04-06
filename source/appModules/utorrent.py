﻿#appModules/utorrent.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2010 James Teh <jamie@jantrid.net>

u"""App module for µTorrent
"""

import _default
import api
import controlTypes
from NVDAObjects.IAccessible import IAccessible

class TorrentList(IAccessible):

	def _get_shouldAllowIAccessibleFocusEvent(self):
		# Stop annoying duplicate focus events, which are fired even if a menu is open.
		focus = api.getFocusObject()
		focusRole = focus.role
		focusStates = focus.states
		if (self == focus or
			(focusRole == controlTypes.ROLE_MENUITEM and controlTypes.STATE_FOCUSED in focusStates) or
			(focusRole == controlTypes.ROLE_POPUPMENU and controlTypes.STATE_INVISIBLE not in focusStates)
		):
			return False
		return super(TorrentList, self).shouldAllowIAccessibleFocusEvent

class AppModule(_default.AppModule):

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.windowClassName == "SysListView32" and obj.windowControlID == 27:
			clsList.insert(0, TorrentList)
