#NVDAObjects/MSHTML.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
from comtypes import COMError
import comtypes.client
import comtypes.automation
from comtypes import IServiceProvider
import contextlib
import winUser
import oleacc
import IAccessibleHandler
import aria
from keyboardHandler import KeyboardInputGesture
import api
import textInfos
from logHandler import log
import controlTypes
from . import IAccessible
from ..behaviors import EditableTextWithoutAutoSelectDetection
from .. import InvalidNVDAObject
from ..window import Window

IID_IHTMLElement=comtypes.GUID('{3050F1FF-98B5-11CF-BB82-00AA00BDCE0B}')

nodeNamesToNVDARoles={
	"FRAME":controlTypes.ROLE_FRAME,
	"IFRAME":controlTypes.ROLE_FRAME,
	"FRAMESET":controlTypes.ROLE_DOCUMENT,
	"BODY":controlTypes.ROLE_DOCUMENT,
	"TH":controlTypes.ROLE_TABLECELL,
	"IMG":controlTypes.ROLE_GRAPHIC,
	"A":controlTypes.ROLE_LINK,
	"LABEL":controlTypes.ROLE_LABEL,
	"#text":controlTypes.ROLE_STATICTEXT,
	"H1":controlTypes.ROLE_HEADING,
	"H2":controlTypes.ROLE_HEADING,
	"H3":controlTypes.ROLE_HEADING,
	"H4":controlTypes.ROLE_HEADING,
	"H5":controlTypes.ROLE_HEADING,
	"H6":controlTypes.ROLE_HEADING,
	"DIV":controlTypes.ROLE_SECTION,
	"P":controlTypes.ROLE_PARAGRAPH,
	"FORM":controlTypes.ROLE_FORM,
	"UL":controlTypes.ROLE_LIST,
	"OL":controlTypes.ROLE_LIST,
	"DL":controlTypes.ROLE_LIST,
	"LI":controlTypes.ROLE_LISTITEM,
	"DD":controlTypes.ROLE_LISTITEM,
	"DT":controlTypes.ROLE_LISTITEM,
	"TR":controlTypes.ROLE_TABLEROW,
	"THEAD":controlTypes.ROLE_TABLEHEADER,
	"TBODY":controlTypes.ROLE_TABLEBODY,
	"HR":controlTypes.ROLE_SEPARATOR,
	"OBJECT":controlTypes.ROLE_EMBEDDEDOBJECT,
	"APPLET":controlTypes.ROLE_EMBEDDEDOBJECT,
	"EMBED":controlTypes.ROLE_EMBEDDEDOBJECT,
}

def IAccessibleFromHTMLNode(HTMLNode):
	try:
		s=HTMLNode.QueryInterface(IServiceProvider)
		return s.QueryService(oleacc.IAccessible._iid_,oleacc.IAccessible)
	except COMError:
		raise NotImplementedError

def HTMLNodeFromIAccessible(IAccessibleObject):
	#Internet Explorer 8 can crash if you try asking for an IHTMLElement from the root MSHTML Registered Handler IAccessible
	#So only do it if we can get the role, and its not the MSAA client role.
	try:
		accRole=IAccessibleObject.accRole(0)
	except COMError:
		accRole=0
	if not accRole or accRole==oleacc.ROLE_SYSTEM_CLIENT:
		return None
	try:
		s=IAccessibleObject.QueryInterface(IServiceProvider)
		i=s.QueryService(IID_IHTMLElement,comtypes.automation.IDispatch)
		if not i:
			# QueryService should fail if IHTMLElement is not supported, but some applications misbehave and return a null COM pointer.
			raise NotImplementedError
		return comtypes.client.dynamic.Dispatch(i)
	except COMError:
		raise NotImplementedError

def locateHTMLElementByID(document,ID):
	try:
		element=document.getElementsByName(ID).item(0)
	except COMError as e:
		log.debugWarning("document.getElementsByName failed with COMError %s"%e)
		element=None
	if element:
		return element
	try:
		nodeName=document.body.nodeName
	except COMError as e:
		log.debugWarning("document.body.nodeName failed with COMError %s"%e)
		return None
	if nodeName=="FRAMESET":
		tag="frame"
	else:
		tag="iframe"
	try:
		frames=document.getElementsByTagName(tag)
	except COMError as e:
		log.debugWarning("document.getElementsByTagName failed with COMError %s"%e)
		return None
	for frame in frames:
		pacc=IAccessibleFromHTMLNode(frame)
		res=IAccessibleHandler.accChild(pacc,1)
		if not res: continue
		childElement=HTMLNodeFromIAccessible(res[0])
		if not childElement: continue
		childElement=locateHTMLElementByID(childElement.document,ID)
		if not childElement: continue
		return childElement

class MSHTMLTextInfo(textInfos.TextInfo):

	def _expandToLine(self,textRange):
		#Try to calculate the line range by finding screen coordinates and using moveToPoint
		parent=textRange.parentElement()
		if not parent.isMultiline: #fastest solution for single line edits (<input type="text">)
			textRange.expand("textEdit")
			return
		parentRect=parent.getBoundingClientRect()
		#This can be simplified when comtypes is fixed
		lineTop=comtypes.client.dynamic._Dispatch(textRange._comobj).offsetTop
		lineLeft=parentRect.left+parent.clientLeft
		#editable documents have a different right most boundary to <textarea> elements.
		if self.obj.HTMLNode.document.body.isContentEditable:
			lineRight=parentRect.right 
		else:
			lineRight=parentRect.left+parent.clientWidth
		tempRange=textRange.duplicate()
		try:
			tempRange.moveToPoint(lineLeft,lineTop)
			textRange.setEndPoint("startToStart",tempRange)
			tempRange.moveToPoint(lineRight,lineTop)
			textRange.setEndPoint("endToStart",tempRange)
			return
		except COMError:
			pass
		#MoveToPoint fails on Some (possibly floated) textArea elements.
		#Instead use the physical selection, by moving it with key presses, to work out the line.
		#This approach is somewhat slower, and less accurate.
		with self.obj.suspendCaretEvents():
			selObj=parent.document.selection
			oldSelRange=selObj.createRange().duplicate()
			textRange.select()
			KeyboardInputGesture.fromName("home").send()
			api.processPendingEvents(False)
			newSelStartMark=selObj.createRange().getBookmark()
			KeyboardInputGesture.fromName("end").send()
			api.processPendingEvents(False)
			newSelEndMark=selObj.createRange().getBookmark()
			tempRange.moveToBookmark(newSelStartMark)
			textRange.setEndPoint("startToStart",tempRange)
			tempRange.moveToBookmark(newSelEndMark)
			textRange.setEndPoint("endToStart",tempRange)
			oldSelRange.select()

	def __init__(self,obj,position,_rangeObj=None):
		super(MSHTMLTextInfo,self).__init__(obj,position)
		if _rangeObj:
			self._rangeObj=_rangeObj.duplicate()
			return
		try:
			editableBody=self.obj.HTMLNode.tagName=="BODY" and self.obj.HTMLNode.isContentEditable
		except:
			editableBody=False
		if editableBody:
			self._rangeObj=self.obj.HTMLNode.document.selection.createRange()
		else:
			self._rangeObj=self.obj.HTMLNode.createTextRange()
		if position in (textInfos.POSITION_CARET,textInfos.POSITION_SELECTION):
			activeElement=self.obj.HTMLNode.document.activeElement
			if not activeElement or self.obj.HTMLNode.uniqueID!=activeElement.uniqueID:
				raise RuntimeError("Only works with currently selected element")
			if not editableBody:
				mark=self.obj.HTMLNode.document.selection.createRange().GetBookmark()
				self._rangeObj.MoveToBookmark(mark)
				#When the caret is at the end of some edit fields, the rangeObj fetched is actually positioned on a magic position before the start
				#So if we detect this, force it to the end
				t=self._rangeObj.duplicate()
				if not t.expand("word") and t.expand("textedit") and t.compareEndPoints("startToStart",self._rangeObj)<0:
					self._rangeObj.expand("textedit")
					self._rangeObj.collapse(False)
			if position==textInfos.POSITION_CARET:
				self._rangeObj.collapse()
			return
		if position==textInfos.POSITION_FIRST:
			self._rangeObj.collapse()
		elif position==textInfos.POSITION_LAST:
			self._rangeObj.expand("textedit")
			self.collapse(True)
			self._rangeObj.move("character",-1)
		elif position==textInfos.POSITION_ALL:
			self._rangeObj.expand("textedit")
		elif isinstance(position,textInfos.Bookmark):
			if position.infoClass==self.__class__:
				self._rangeObj.moveToBookmark(position.data)
			else:
				raise TypeError("Bookmark was for %s type, not for %s type"%(position.infoClass.__name__,self.__class__.__name__))
		else:
			raise NotImplementedError("position: %s"%position)

	def expand(self,unit):
		if unit==textInfos.UNIT_PARAGRAPH:
			unit=textInfos.UNIT_LINE
		if unit==textInfos.UNIT_LINE and self.basePosition not in [textInfos.POSITION_SELECTION,textInfos.POSITION_CARET]:
			unit=textInfos.UNIT_SENTENCE
		if unit==textInfos.UNIT_READINGCHUNK:
			unit=textInfos.UNIT_SENTENCE
		if unit==textInfos.UNIT_CHARACTER:
			self._rangeObj.expand("character")
		elif unit==textInfos.UNIT_WORD:
			#Expand to word at the start of a control is broken in MSHTML
			#Unless we expand to character first.
			self._rangeObj.expand("character")
			self._rangeObj.expand("word")
		elif unit==textInfos.UNIT_SENTENCE:
			self._rangeObj.expand("sentence")
		elif unit==textInfos.UNIT_LINE:
			self._expandToLine(self._rangeObj)
		elif unit==textInfos.UNIT_STORY:
			self._rangeObj.expand("textedit")
		else:
			raise NotImplementedError("unit: %s"%unit)

	def _get_isCollapsed(self):
		if self._rangeObj.compareEndPoints("startToEnd",self._rangeObj)==0:
			return True
		else:
			return False

	def collapse(self,end=False):
		self._rangeObj.collapse(not end)

	def copy(self):
		return self.__class__(self.obj,None,_rangeObj=self._rangeObj.duplicate())

	def compareEndPoints(self,other,which):
		return self._rangeObj.compareEndPoints(which,other._rangeObj)

	def setEndPoint(self,other,which):
		self._rangeObj.setEndPoint(which,other._rangeObj)

	def _get_text(self):
		text=self._rangeObj.text
		if not text:
			text=""
		if controlTypes.STATE_PROTECTED in self.obj.states:
			text='*'*len(text)
		return text

	def move(self,unit,direction, endPoint=None):
		if unit in [textInfos.UNIT_READINGCHUNK,textInfos.UNIT_LINE]:
			unit=textInfos.UNIT_SENTENCE
		if unit==textInfos.UNIT_STORY:
			unit="textedit"
		if endPoint=="start":
			moveFunc=self._rangeObj.moveStart
		elif endPoint=="end":
			moveFunc=self._rangeObj.moveEnd
		else:
			moveFunc=self._rangeObj.move
		res=moveFunc(unit,direction)
		return res

	def updateCaret(self):
		self._rangeObj.select()

	def updateSelection(self):
		self._rangeObj.select()

	def _get_bookmark(self):
		return textInfos.Bookmark(self.__class__,self._rangeObj.getBookmark())

class MSHTML(IAccessible):

	HTMLNodeNameNavSkipList=['#comment','SCRIPT','HEAD','HTML','PARAM']
	HTMLNodeNameEmbedList=['OBJECT','EMBED','APPLET','FRAME','IFRAME']

	_ignoreCaretEvents=False #:Set to true when moving the caret to calculate lines, event_caret will be disabled.

	@contextlib.contextmanager
	def suspendCaretEvents(self):
		"""Suspends caret events while you need to move the caret to calculate things."""
		oldVal=self._ignoreCaretEvents
		self._ignoreCaretEvents=True
		yield oldVal
		self._ignoreCaretEvents=oldVal

	def event_caret(self):
		if self._ignoreCaretEvents: return
		return super(MSHTML,self).event_caret()

	@classmethod
	def kwargsFromSuper(cls,kwargs,relation=None):
		IAccessibleObject=kwargs['IAccessibleObject']
		HTMLNode=None
		try:
			HTMLNode=HTMLNodeFromIAccessible(IAccessibleObject)
		except NotImplementedError:
			pass
		if not HTMLNode:
			return False

		if relation=="focus":
			try:
				HTMLNode=HTMLNode.document.activeElement
				# The IAccessibleObject may be incorrect now, so let the constructor recalculate it.
				del kwargs['IAccessibleObject']
			except:
				log.exception("Error getting activeElement")

		kwargs['HTMLNode']=HTMLNode
		return True

	def findOverlayClasses(self,clsList):
		if self.TextInfo == MSHTMLTextInfo:
			clsList.append(EditableTextWithoutAutoSelectDetection)
		#fix for #974
		#this fails on some control in vs2008 new project wizard
		try:
			nodeName = self.HTMLNode.nodeName
		except COMError:
			pass
		else:
			if nodeNamesToNVDARoles.get(nodeName) == controlTypes.ROLE_DOCUMENT:
				clsList.append(Body)
			elif nodeName == "OBJECT":
				clsList.append(Object)
		clsList.append(MSHTML)
		if not self.HTMLNodeHasAncestorIAccessible:
			# The IAccessibleObject is for this node (not an ancestor), so IAccessible overlay classes are relevant.
			super(MSHTML,self).findOverlayClasses(clsList)

	def _get_treeInterceptorClass(self):
		if self.HTMLNode and self.role==controlTypes.ROLE_DOCUMENT and not self.isContentEditable:
			import virtualBuffers.MSHTML
			return virtualBuffers.MSHTML.MSHTML
		return super(MSHTML,self).treeInterceptorClass

	def __init__(self,HTMLNode=None,IAccessibleObject=None,IAccessibleChildID=None,**kwargs):
		self.HTMLNodeHasAncestorIAccessible=False
		if not IAccessibleObject:
			# Find an IAccessible for HTMLNode and determine whether it is for an ancestor.
			tempNode=HTMLNode
			while tempNode:
				try:
					IAccessibleObject=IAccessibleFromHTMLNode(tempNode)
				except NotImplementedError:
					IAccessibleObject=None
				if IAccessibleObject:
					IAccessibleChildID=0
					if tempNode is not HTMLNode:
						self.HTMLNodeHasAncestorIAccessible=True
					break
				try:
					tempNode=tempNode.parentNode
				except COMError:
					tempNode=None

		if not IAccessibleObject:
			raise InvalidNVDAObject("Couldn't get IAccessible, probably dead object")

		super(MSHTML,self).__init__(IAccessibleObject=IAccessibleObject,IAccessibleChildID=IAccessibleChildID,**kwargs)
		self.HTMLNode=HTMLNode

		#object and embed nodes give back an incorrect IAccessible via queryService, so we must treet it as an ancestor IAccessible
		if self.HTMLNodeName in ("OBJECT","EMBED"):
			self.HTMLNodeHasAncestorIAccessible=True
		try:
			self.HTMLNode.createTextRange()
			self.TextInfo=MSHTMLTextInfo
		except (NameError, COMError):
			pass

	def isDuplicateIAccessibleEvent(self,obj):
		if not super(MSHTML,self).isDuplicateIAccessibleEvent(obj):
			return False
		#MSHTML winEvents can't be trusted for uniqueness, so just do normal object comparison.
		return self==obj


	def _isEqual(self, other):
		if self.HTMLNode and other.HTMLNode:
			try:
				return self.windowHandle == other.windowHandle and self.HTMLNode.uniqueNumber == other.HTMLNode.uniqueNumber
			except (COMError,NameError):
				pass
		return super(MSHTML, self)._isEqual(other)

	def _get_name(self):
		if self.HTMLNodeHasAncestorIAccessible:
			return ""
		return super(MSHTML,self).name

	def _get_value(self):
		if self.HTMLNodeHasAncestorIAccessible:
			try:
				value=self.HTMLNode.data
			except (COMError,NameError):
				value=""
			return value
		IARole=self.IAccessibleRole
		if IARole in (oleacc.ROLE_SYSTEM_PANE,oleacc.ROLE_SYSTEM_TEXT):
			return ""
		else:
			return super(MSHTML,self).value

	def _get_description(self):
		if self.HTMLNodeHasAncestorIAccessible:
			return ""
		return super(MSHTML,self).description

	def _get_basicText(self):
		if self.HTMLNode:
			try:
				return self.HTMLNode.data or ""
			except (COMError, AttributeError, NameError):
				pass
			try:
				return self.HTMLNode.innerText or ""
			except (COMError, AttributeError, NameError):
				pass
		return super(MSHTML,self).basicText

	def _get_role(self):
		if self.HTMLNode:
			try:
				ariaRole=self.HTMLNode.getAttribute('role')
			except (COMError, NameError):
				ariaRole=None
			if ariaRole:
				role=aria.ariaRolesToNVDARoles.get(ariaRole)
				if role:
					return role
			nodeName=self.HTMLNodeName
			if nodeName:
				if nodeName in ("OBJECT","EMBED","APPLET"):
					return controlTypes.ROLE_EMBEDDEDOBJECT
				if self.HTMLNodeHasAncestorIAccessible or nodeName in ("BODY","FRAMESET","FRAME","IFRAME"):
					return nodeNamesToNVDARoles.get(nodeName,controlTypes.ROLE_TEXTFRAME)
		if self.IAccessibleChildID>0:
			states=super(MSHTML,self).states
			if controlTypes.STATE_LINKED in states:
				return controlTypes.ROLE_LINK
		return super(MSHTML,self).role

	def _get_states(self):
		if not self.HTMLNodeHasAncestorIAccessible:
			states=super(MSHTML,self).states
		else:
			states=set()
		e=self.HTMLNode
		if e:
			try:
				ariaRequired=e.GetAttribute('aria-required')
			except (COMError, NameError):
				ariaRequired=None
			if ariaRequired=="true":
				states.add(controlTypes.STATE_REQUIRED)
			try:
				ariaInvalid=e.GetAttribute('aria-invalid')
			except (COMError, NameError):
				ariaInvalid=None
			if ariaInvalid=="true":
				states.add(controlTypes.STATE_INVALID)
			try:
				ariaGrabbed=e.GetAttribute('aria-grabbed')
			except (COMError, NameError):
				ariaGrabbed=None
			if ariaGrabbed=="true":
				states.add(controlTypes.STATE_DRAGGING)
			elif ariaGrabbed=="false":
				states.add(controlTypes.STATE_DRAGGABLE)
			try:
				ariaDropeffect=e.GetAttribute('aria-dropeffect')
			except (COMError, NameError):
				ariaDropeffect='none'
			if ariaDropeffect and ariaDropeffect!="none":
				states.add(controlTypes.STATE_DROPTARGET)
			try:
				isContentEditable=e.isContentEditable
			except (COMError,NameError):
				isContentEditable=False
			if isContentEditable:
				states.add(controlTypes.STATE_EDITABLE)
				states.discard(controlTypes.STATE_READONLY)
			nodeName=self.HTMLNodeName
			if nodeName=="TEXTAREA":
				states.add(controlTypes.STATE_MULTILINE)
			try:
				required=e.getAttribute('aria-required')
			except (COMError, NameError):
				required=None
			if required and required.lower()=='true':
				states.add(controlTypes.STATE_REQUIRED)
		return states

	def _get_isContentEditable(self):
		if self.HTMLNode:
			try:
				return bool(self.HTMLNode.isContentEditable)
			except:
				return False
		else:
			return False

	def _get_parent(self):
		if self.HTMLNode:
			try:
				parentNode=self.HTMLNode.parentElement
			except (COMError,NameError):
				parentNode=None
			if not parentNode and self.HTMLNodeHasAncestorIAccessible:
				try:
					parentNode=self.HTMLNode.parentNode
				except (COMError,NameError):
					parentNode=None
			if parentNode:
				obj=MSHTML(HTMLNode=parentNode)
				if obj and obj.HTMLNodeName not in self.HTMLNodeNameNavSkipList:
					return obj
		return super(MSHTML,self).parent

	def _get_previous(self):
		if self.HTMLNode:
			try:
				previousNode=self.HTMLNode.previousSibling
			except COMError:
				previousNode=None
			if not previousNode:
				return None
			obj=MSHTML(HTMLNode=previousNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				obj=obj.previous
			return obj
		return super(MSHTML,self).previous

	def _get_next(self):
		if self.HTMLNode:
			try:
				nextNode=self.HTMLNode.nextSibling
			except COMError:
				nextNode=None
			if not nextNode:
				return None
			obj=MSHTML(HTMLNode=nextNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				obj=obj.next
			return obj
		return super(MSHTML,self).next

	def _get_firstChild(self):
		if self.HTMLNode:
			if self.HTMLNodeName in ("FRAME","IFRAME"):
				return super(MSHTML,self).firstChild
			try:
				childNode=self.HTMLNode.firstChild
			except COMError:
				childNode=None
			if not childNode:
				return None
			obj=MSHTML(HTMLNode=childNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				return obj.next
			return obj
		if self.HTMLNodeHasAncestorIAccessible:
			return None
		return super(MSHTML,self).firstChild

	def _get_lastChild(self):
		if self.HTMLNode:
			if self.HTMLNodeName in ("FRAME","IFRAME"):
				return super(MSHTML,self).lastChild
			try:
				childNode=self.HTMLNode.lastChild
			except COMError:
				childNode=None
			if not childNode:
				return None
			obj=MSHTML(HTMLNode=childNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				return obj.previous
			return obj
		if self.HTMLNodeHasAncestorIAccessible:
			return None
		return super(MSHTML,self).lastChild

	def _get_columnNumber(self):
		if not self.role==controlTypes.ROLE_TABLECELL or not self.HTMLNode:
			raise NotImplementedError
		try:
			return self.HTMLNode.cellIndex+1
		except:
			raise NotImplementedError

	def _get_rowNumber(self):
		if not self.role==controlTypes.ROLE_TABLECELL or not self.HTMLNode:
			raise NotImplementedError
		HTMLNode=self.HTMLNode
		while HTMLNode:
			try:
				return HTMLNode.rowIndex+1
			except:
				pass
			HTMLNode=HTMLNode.parentNode
		raise NotImplementedError

	def _get_rowCount(self):
		if self.role!=controlTypes.ROLE_TABLE or not self.HTMLNode:
			raise NotImplementedError
		try:
			return len([x for x in self.HTMLNode.rows])
		except:
			raise NotImplementedError

	def scrollIntoView(self):
		if not self.HTMLNode:
			return
		try:
			self.HTMLNode.scrollInToView()
		except (COMError,NameError):
			pass

	def doAction(self, index=None):
		if self.HTMLNode:
			try:
				self.HTMLNode.click()
				return
			except COMError:
				return
			except NameError:
				pass
		super(MSHTML,self).doAction(index=index)

	def setFocus(self):
		if self.HTMLNodeHasAncestorIAccessible:
			try:
				self.HTMLNode.focus()
			except (COMError, AttributeError, NameError):
				pass
			return
		super(MSHTML,self).setFocus()

	def _get_table(self):
		if self.role not in (controlTypes.ROLE_TABLECELL,controlTypes.ROLE_TABLEROW) or not self.HTMLNode:
			raise NotImplementedError
		HTMLNode=self.HTMLNode
		while HTMLNode:
			if HTMLNode.nodeName=="TABLE": return MSHTML(HTMLNode=HTMLNode)
			HTMLNode=HTMLNode.parentNode
		raise NotImplementedError

	def _get_HTMLNodeName(self):
		if not self.HTMLNode:
			return ""
		if not hasattr(self,'_HTMLNodeName'):
			try:
				nodeName=self.HTMLNode.nodeName
			except (COMError,NameError):
				nodeName=""
			self._HTMLNodeName=nodeName
		return self._HTMLNodeName

class V6ComboBox(IAccessible):
	"""The object which receives value change events for combo boxes in MSHTML/IE 6.
	"""

	def event_valueChange(self):
		focus = api.getFocusObject()
		if controlTypes.STATE_FOCUSED not in self.states or focus.role != controlTypes.ROLE_COMBOBOX:
			# This combo box is not focused.
			return super(V6ComboBox, self).event_valueChange()
		# This combo box is focused. However, the value change is not fired on the real focus object.
		# Therefore, redirect this event to the real focus object.
		focus.event_valueChange()

class Body(MSHTML):

	def _get_parent(self):
		# The parent of the body accessible is an irrelevant client object (description: MSAAHTML Registered Handler).
		# This object isn't returned when requesting OBJID_CLIENT, nor is it returned as a child of its parent.
		# Therefore, eliminate it from the ancestry completely.
		parent = super(Body, self).parent
		if parent:
			return parent.parent
		else:
			return parent

	def _get_shouldAllowIAccessibleFocusEvent(self):
		# We must override this because we override parent to skip the MSAAHTML Registered Handler client,
		# which might have the focused state.
		if controlTypes.STATE_FOCUSED in self.states:
			return True
		parent = super(Body, self).parent
		if not parent:
			return False
		return parent.shouldAllowIAccessibleFocusEvent

class Object(MSHTML):

	def _get_firstChild(self):
		# We want firstChild to return the accessible for the embedded object.
		from objidl import IOleWindow
		# Try to get the window for the embedded object.
		try:
			window = self.HTMLNode.object.QueryInterface(IOleWindow).GetWindow()
		except COMError:
			window = None
		if not window or window == self.windowHandle:
			return super(Object, self).firstChild
		return Window(windowHandle=window)

class PluginWindow(IAccessible):
	"""A window for a plugin.
	"""

	# MSHTML fires focus on this window after the plugin may already have fired a focus event.
	# We don't want this to override the focus event fired by the plugin.
	shouldAllowIAccessibleFocusEvent = False

class RootClient(IAccessible):
	"""The top level client of an MSHTML control.
	"""

	# Get rid of the URL.
	name = None
	# Get rid of "MSAAHTML Registered Handler".
	description = None

def findExtraIAccessibleOverlayClasses(obj, clsList):
	"""Determine the most appropriate class for MSHTML objects.
	This works similarly to L{NVDAObjects.NVDAObject.findOverlayClasses} except that it never calls any other findOverlayClasses method.
	"""
	windowClass = obj.windowClassName
	iaRole = obj.IAccessibleRole
	if windowClass == "Internet Explorer_TridentCmboBx" and iaRole == oleacc.ROLE_SYSTEM_COMBOBOX:
		clsList.append(V6ComboBox)
		return

	if windowClass != "Internet Explorer_Server":
		return

	if iaRole == oleacc.ROLE_SYSTEM_WINDOW and obj.event_objectID > 0:
		clsList.append(PluginWindow)
	elif iaRole == oleacc.ROLE_SYSTEM_CLIENT and obj.event_objectID == winUser.OBJID_CLIENT:
		clsList.append(RootClient)
