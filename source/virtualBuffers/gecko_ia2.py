from . import VirtualBuffer, VirtualBufferTextInfo, VBufStorage_findMatch_word
import treeInterceptorHandler
import controlTypes
import NVDAObjects.IAccessible
import NVDAObjects.behaviors
import winUser
import IAccessibleHandler
import oleacc
from logHandler import log
import textInfos
from comtypes.gen.IAccessible2Lib import IAccessible2
from comtypes import COMError
import aria
import config

class Gecko_ia2_TextInfo(VirtualBufferTextInfo):

	def _normalizeControlField(self,attrs):
		accRole=attrs['IAccessible::role']
		accRole=int(accRole) if accRole.isdigit() else accRole
		role=IAccessibleHandler.IAccessibleRolesToNVDARoles.get(accRole,controlTypes.ROLE_UNKNOWN)
		if attrs.get('IAccessible2::attribute_tag',"").lower()=="blockquote":
			role=controlTypes.ROLE_BLOCKQUOTE
		states=set(IAccessibleHandler.IAccessibleStatesToNVDAStates[x] for x in [1<<y for y in xrange(32)] if int(attrs.get('IAccessible::state_%s'%x,0)) and x in IAccessibleHandler.IAccessibleStatesToNVDAStates)
		states|=set(IAccessibleHandler.IAccessible2StatesToNVDAStates[x] for x in [1<<y for y in xrange(32)] if int(attrs.get('IAccessible2::state_%s'%x,0)) and x in IAccessibleHandler.IAccessible2StatesToNVDAStates)
		defaultAction=attrs.get('defaultAction','')
		if defaultAction=="click":
			states.add(controlTypes.STATE_CLICKABLE)
		grabbed = attrs.get("IAccessible2::attribute_grabbed")
		if grabbed == "false":
			states.add(controlTypes.STATE_DRAGGABLE)
		elif grabbed == "true":
			states.add(controlTypes.STATE_DRAGGING)
		if attrs.get("IAccessible2::attribute_dropeffect", "none") != "none":
			states.add(controlTypes.STATE_DROPTARGET)
		if role==controlTypes.ROLE_LINK and controlTypes.STATE_LINKED not in states:
			# This is a named link destination, not a link which can be activated. The user doesn't care about these.
			role=controlTypes.ROLE_TEXTFRAME
		level=attrs.get('IAccessible2::attribute_level',"")
		xmlRoles=attrs.get("IAccessible2::attribute_xml-roles", "").split(" ")
		# Get the first landmark role, if any.
		landmark=next((xr for xr in xmlRoles if xr in aria.landmarkRoles),None)

		attrs['role']=role
		attrs['states']=states
		if level is not "" and level is not None:
			attrs['level']=level
		if landmark:
			attrs["landmark"]=landmark
		return super(Gecko_ia2_TextInfo,self)._normalizeControlField(attrs)

class Gecko_ia2(VirtualBuffer):

	TextInfo=Gecko_ia2_TextInfo

	def __init__(self,rootNVDAObject):
		super(Gecko_ia2,self).__init__(rootNVDAObject,backendName="gecko_ia2")

	def _get_shouldPrepare(self):
		return super(Gecko_ia2,self).shouldPrepare and controlTypes.STATE_BUSY not in self.rootNVDAObject.states

	def __contains__(self,obj):
		#Special code to handle Mozilla combobox lists
		if obj.windowClassName.startswith('Mozilla') and winUser.getWindowStyle(obj.windowHandle)&winUser.WS_POPUP:
			parent=obj.parent
			while parent and parent.windowHandle==obj.windowHandle:
				parent=parent.parent
			if parent:
				obj=parent.parent
		if not (isinstance(obj,NVDAObjects.IAccessible.IAccessible) and isinstance(obj.IAccessibleObject,IAccessibleHandler.IAccessible2)) or not obj.windowClassName.startswith('Mozilla') or not winUser.isDescendantWindow(self.rootNVDAObject.windowHandle,obj.windowHandle):
			return False
		if self.rootNVDAObject.windowHandle==obj.windowHandle:
			ID=obj.IAccessibleObject.uniqueID
			try:
				self.rootNVDAObject.IAccessibleObject.accChild(ID)
			except:
				return False

		return self._isNVDAObjectInApplication(obj)

	def _get_isAlive(self):
		if self.isLoading:
			return True
		root=self.rootNVDAObject
		if not root:
			return False
		states=root.states
		if not winUser.isWindow(root.windowHandle) or controlTypes.STATE_DEFUNCT in states or controlTypes.STATE_READONLY not in states:
			return False
		try:
			if not NVDAObjects.IAccessible.getNVDAObjectFromEvent(root.windowHandle,winUser.OBJID_CLIENT,root.IAccessibleObject.uniqueID):
				return False
		except:
			return False
		return True

	def getNVDAObjectFromIdentifier(self, docHandle, ID):
		return NVDAObjects.IAccessible.getNVDAObjectFromEvent(docHandle, winUser.OBJID_CLIENT, ID)

	def getIdentifierFromNVDAObject(self,obj):
		docHandle=obj.windowHandle
		ID=obj.IAccessibleObject.uniqueID
		return docHandle,ID

	def _shouldIgnoreFocus(self, obj):
		if obj.role == controlTypes.ROLE_DOCUMENT and controlTypes.STATE_EDITABLE not in obj.states:
			return True
		return super(Gecko_ia2, self)._shouldIgnoreFocus(obj)

	def _postGainFocus(self, obj):
		if isinstance(obj, NVDAObjects.behaviors.EditableText):
			# We aren't passing this event to the NVDAObject, so we need to do this ourselves.
			obj.initAutoSelectDetection()
		super(Gecko_ia2, self)._postGainFocus(obj)

	def _shouldSetFocusToObj(self, obj):
		if obj.role == controlTypes.ROLE_GRAPHIC and controlTypes.STATE_LINKED in obj.states:
			return True
		return super(Gecko_ia2,self)._shouldSetFocusToObj(obj) and obj.role!=controlTypes.ROLE_EMBEDDEDOBJECT

	def _activateNVDAObject(self, obj):
		try:
			obj.doAction()
		except:
			log.debugWarning("could not programmatically activate field, trying mouse")
			l=obj.location
			if l:
				x=(l[0]+l[2]/2)
				y=l[1]+(l[3]/2) 
				oldX,oldY=winUser.getCursorPos()
				winUser.setCursorPos(x,y)
				winUser.mouse_event(winUser.MOUSEEVENTF_LEFTDOWN,0,0,None,None)
				winUser.mouse_event(winUser.MOUSEEVENTF_LEFTUP,0,0,None,None)
				winUser.setCursorPos(oldX,oldY)
			else:
				log.debugWarning("no location for field")

	def _searchableAttribsForNodeType(self,nodeType):
		if nodeType.startswith('heading') and nodeType[7:].isdigit():
			attrs={"IAccessible::role":[IAccessibleHandler.IA2_ROLE_HEADING],"IAccessible2::attribute_level":[nodeType[7:]]}
		elif nodeType=="heading":
			attrs={"IAccessible::role":[IAccessibleHandler.IA2_ROLE_HEADING]}
		elif nodeType=="table":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_TABLE]}
			if not config.conf["documentFormatting"]["includeLayoutTables"]:
				attrs["table-layout"]=[None]
		elif nodeType=="link":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_LINK],"IAccessible::state_%d"%oleacc.STATE_SYSTEM_LINKED:[1]}
		elif nodeType=="visitedLink":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_LINK],"IAccessible::state_%d"%oleacc.STATE_SYSTEM_TRAVERSED:[1]}
		elif nodeType=="unvisitedLink":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_LINK],"IAccessible::state_%d"%oleacc.STATE_SYSTEM_LINKED:[1],"IAccessible::state_%d"%oleacc.STATE_SYSTEM_TRAVERSED:[None]}
		elif nodeType=="formField":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_PUSHBUTTON,oleacc.ROLE_SYSTEM_RADIOBUTTON,oleacc.ROLE_SYSTEM_CHECKBUTTON,oleacc.ROLE_SYSTEM_COMBOBOX,oleacc.ROLE_SYSTEM_LIST,oleacc.ROLE_SYSTEM_OUTLINE,oleacc.ROLE_SYSTEM_TEXT],"IAccessible::state_%s"%oleacc.STATE_SYSTEM_READONLY:[None]}
		elif nodeType=="list":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_LIST]}
		elif nodeType=="listItem":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_LISTITEM]}
		elif nodeType=="button":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_PUSHBUTTON]}
		elif nodeType=="edit":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_TEXT],"IAccessible::state_%s"%oleacc.STATE_SYSTEM_READONLY:[None]}
		elif nodeType=="frame":
			attrs={"IAccessible::role":[IAccessibleHandler.IA2_ROLE_INTERNAL_FRAME]}
		elif nodeType=="separator":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_SEPARATOR]}
		elif nodeType=="radioButton":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_RADIOBUTTON]}
		elif nodeType=="comboBox":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_COMBOBOX]}
		elif nodeType=="checkBox":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_CHECKBUTTON]}
		elif nodeType=="graphic":
			attrs={"IAccessible::role":[oleacc.ROLE_SYSTEM_GRAPHIC]}
		elif nodeType=="blockQuote":
			attrs={"IAccessible2::attribute_tag":["BLOCKQUOTE"]}
		elif nodeType=="focusable":
			attrs={"IAccessible::state_%s"%oleacc.STATE_SYSTEM_FOCUSABLE:[1]}
		elif nodeType=="landmark":
			attrs={"IAccessible2::attribute_xml-roles":[VBufStorage_findMatch_word(lr) for lr in aria.landmarkRoles]}
		elif nodeType=="embeddedObject":
			attrs={"IAccessible2::attribute_tag":["EMBED","OBJECT","APPLET"]}
		else:
			return None
		return attrs

	def event_stateChange(self,obj,nextHandler):
		if not self.isAlive:
			return treeInterceptorHandler.killTreeInterceptor(self)
		return nextHandler()

	def event_scrollingStart(self, obj, nextHandler):
		if not self._handleScrollTo(obj):
			return nextHandler()

	def _getNearestTableCell(self, tableID, startPos, origRow, origCol, origRowSpan, origColSpan, movement, axis):
		if not axis:
			# First or last.
			return super(Gecko_ia2, self)._getNearestTableCell(tableID, startPos, origRow, origCol, origRowSpan, origColSpan, movement, axis)

		# Determine destination row and column.
		destRow = origRow
		destCol = origCol
		if axis == "row":
			destRow += origRowSpan if movement == "next" else -1
		elif axis == "column":
			destCol += origColSpan if movement == "next" else -1

		if destCol < 1:
			# Optimisation: We're definitely at the edge of the column.
			raise LookupError

		# For Gecko, we can use the table object to directly retrieve the cell with the exact destination coordinates.
		docHandle = startPos.NVDAObjectAtStart.windowHandle
		table = self.getNVDAObjectFromIdentifier(docHandle, tableID)
		try:
			cell = table.IAccessibleTableObject.accessibleAt(destRow - 1, destCol - 1).QueryInterface(IAccessible2)
			cell = NVDAObjects.IAccessible.IAccessible(IAccessibleObject=cell, IAccessibleChildID=0)
			return self.makeTextInfo(cell)
		except (COMError, RuntimeError):
			raise LookupError

	def _get_documentConstantIdentifier(self):
		try:
			return self.rootNVDAObject.IAccessibleObject.accValue(0)
		except COMError:
			return None
