#appModules/audacity.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import appModuleHandler
import winUser
import controlTypes

class AppModule(appModuleHandler.AppModule):

	def event_NVDAObject_init(self,obj):
		if obj.windowClassName=="Button" and not obj.role in [controlTypes.ROLE_MENUBAR, controlTypes.ROLE_MENUITEM, controlTypes.ROLE_POPUPMENU]:
			obj.name=winUser.getWindowText(obj.windowHandle).replace('&','')
