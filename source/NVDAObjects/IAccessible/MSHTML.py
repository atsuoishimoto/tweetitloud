#NVDAObjects/MSHTML.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
import ctypes
from comtypes import COMError
import comtypes.client
import comtypes.automation
from comtypes import IServiceProvider
import winUser
import globalVars
import oleacc
import aria
from keyUtils import key, sendKey
import api
import textInfos
from logHandler import log
import speech
import controlTypes
from . import IAccessible
import NVDAObjects
import virtualBufferHandler

lastMSHTMLEditGainFocusTimeStamp=0

IID_IHTMLElement=comtypes.GUID('{3050F1FF-98B5-11CF-BB82-00AA00BDCE0B}')

nodeNamesToNVDARoles={
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
	"oL":controlTypes.ROLE_LIST,
	"dL":controlTypes.ROLE_LIST,
	"LI":controlTypes.ROLE_LISTITEM,
	"DD":controlTypes.ROLE_LISTITEM,
	"DT":controlTypes.ROLE_LISTITEM,
	"TR":controlTypes.ROLE_TABLEROW,
	"THEAD":controlTypes.ROLE_TABLEHEADER,
	"TBODY":controlTypes.ROLE_TABLEBODY,
	"HR":controlTypes.ROLE_SEPARATOR,
}

def IAccessibleFromHTMLNode(HTMLNode):
	try:
		s=HTMLNode.QueryInterface(IServiceProvider)
		return s.QueryService(oleacc.IAccessible._iid_,oleacc.IAccessible)
	except COMError:
		raise NotImplementedError

def HTMLNodeFromIAccessible(IAccessibleObject):
	try:
		s=IAccessibleObject.QueryInterface(IServiceProvider)
		return comtypes.client.dynamic.Dispatch(s.QueryService(IID_IHTMLElement,comtypes.automation.IDispatch))
	except COMError:
		raise NotImplementedError

def locateHTMLElementByID(document,ID):
	element=document.getElementById(ID)
	if element:
		return element
	nodeName=document.body.nodeName
	if nodeName=="FRAMESET":
		tag="frame"
	else:
		tag="iframe"
	frames=document.getElementsByTagName(tag)
	for frame in frames:
		pacc=IAccessibleFromHTMLNode(frame)
		childPacc=pacc.accChild(1)
		childElement=HTMLNodeFromIAccessible(childPacc)
		childElement=locateHTMLElementByID(childElement.document,ID)
		if childElement:
			return childElement

class MSHTMLTextInfo(textInfos.TextInfo):

	def _expandToLine(self,textRange):
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
		tempRange.moveToPoint(lineLeft,lineTop)
		textRange.setEndPoint("startToStart",tempRange)
		tempRange.moveToPoint(lineRight,lineTop)
		textRange.setEndPoint("endToStart",tempRange)

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
			if self.obj.HTMLNode.uniqueID!=self.obj.HTMLNode.document.activeElement.uniqueID:
				raise RuntimeError("Only works with currently selected element")
			if not editableBody:
				mark=self.obj.HTMLNode.document.selection.createRange().GetBookmark()
				self._rangeObj.MoveToBookmark(mark)
				t=self._rangeObj.duplicate()
				if not t.expand("word"):
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

	HTMLNodeNameNavSkipList=['#comment','SCRIPT']
	HTMLNodeNameChildNavUseIAccessibleList=['OBJECT','EMBED']

	@classmethod
	def findBestClass(cls,clsList,kwargs):
		clsList.append(cls)
		tempNode=HTMLNode=kwargs.get('HTMLNode')
		while tempNode:
			try:
				IAccessibleObject=IAccessibleFromHTMLNode(tempNode)
			except NotImplementedError:
				IAccessibleObject=None
			if IAccessibleObject:
				kwargs['IAccessibleObject']=IAccessibleObject
				kwargs['IAccessibleChildID']=0
				if tempNode is not HTMLNode:
					kwargs['HTMLNodeHasAncestorIAccessible']=True
				break
			try:
				tempNode=tempNode.parentNode
			except COMError:
				tempNode=None
		return super(MSHTML,cls).findBestClass(clsList,kwargs)

	def __init__(self,HTMLNode=None,HTMLNodeHasAncestorIAccessible=False,**kwargs):
		super(MSHTML,self).__init__(**kwargs)
		self.HTMLNodeHasAncestorIAccessible=HTMLNodeHasAncestorIAccessible
		if not HTMLNode and self.IAccessibleChildID==0:
			try:
				HTMLNode=HTMLNodeFromIAccessible(self.IAccessibleObject)
			except NotImplementedError:
				pass
		self.HTMLNode=HTMLNode
		try:
			self.HTMLNode.createTextRange()
			self.TextInfo=MSHTMLTextInfo
		except:
			pass
		if self.TextInfo==MSHTMLTextInfo:
			[self.bindKey_runtime(keyName,scriptName) for keyName,scriptName in [
				("ExtendedUp","moveByLine"),
				("ExtendedDown","moveByLine"),
				("ExtendedLeft","moveByCharacter"),
				("ExtendedRight","moveByCharacter"),
				("Control+ExtendedUp","moveByParagraph"),
				("Control+ExtendedDown","moveByParagraph"),
				("Control+ExtendedLeft","moveByWord"),
				("Control+ExtendedRight","moveByWord"),
				("Shift+ExtendedRight","changeSelection"),
				("Shift+ExtendedLeft","changeSelection"),
				("Shift+ExtendedHome","changeSelection"),
				("Shift+ExtendedEnd","changeSelection"),
				("Shift+ExtendedUp","changeSelection"),
				("Shift+ExtendedDown","changeSelection"),
				("Control+Shift+ExtendedLeft","changeSelection"),
				("Control+Shift+ExtendedRight","changeSelection"),
				("ExtendedHome","moveByCharacter"),
				("ExtendedEnd","moveByCharacter"),
				("control+extendedHome","moveByLine"),
				("control+extendedEnd","moveByLine"),
				("control+shift+extendedHome","changeSelection"),
				("control+shift+extendedEnd","changeSelection"),
				("ExtendedDelete","moveByCharacter"),
				("Back","backspace"),
			]]

	def _isEqual(self, other):
		if self.HTMLNode:
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
				text=self.HTMLNode.innerText
			except COMError:
				text=None
			if text:
				return text
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
				if nodeName in ("BODY","FRAMESET"):
					return controlTypes.ROLE_DOCUMENT
				if self.HTMLNodeHasAncestorIAccessible:
					return nodeNamesToNVDARoles.get(nodeName,controlTypes.ROLE_TEXTFRAME)
		if self.IAccessibleChildID>0:
			states=super(MSHTML,self).states
			if controlTypes.STATE_LINKED in states:
				return controlTypes.ROLE_LINK
		return super(MSHTML,self).role

	def _get_states(self):
		states=super(MSHTML,self).states
		e=self.HTMLNode
		if e:
			try:
				isContentEditable=e.isContentEditable
			except (COMError,NameError):
				isContentEditable=False
			if isContentEditable:
				states.add(controlTypes.STATE_EDITABLE)
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
				return MSHTML(HTMLNode=parentNode)
		return super(MSHTML,self).parent

	def _get_previous(self):
		if self.HTMLNode:
			try:
				previousNode=self.HTMLNode.previousSibling
			except COMError:
				return None
			obj=MSHTML(HTMLNode=previousNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				obj=obj.previous
			return obj
		return super(MSHTML,self).parent

	def _get_next(self):
		if self.HTMLNode:
			try:
				nextNode=self.HTMLNode.nextSibling
			except COMError:
				return None
			obj=MSHTML(HTMLNode=nextNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				obj=obj.next
			return obj
		return super(MSHTML,self).parent

	def _get_firstChild(self):
		if self.HTMLNode:
			if self.HTMLNodeName in self.HTMLNodeNameChildNavUseIAccessibleList:
				return super(MSHTML,self).firstChild
			try:
				childNode=self.HTMLNode.firstChild
			except COMError:
				return None
			obj=MSHTML(HTMLNode=childNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				return None
			return obj
		return super(MSHTML,self).firstChild

	def _get_lastChild(self):
		if self.HTMLNode:
			if self.HTMLNodeName in self.HTMLNodeNameChildNavUseIAccessibleList:
				return super(MSHTML,self).lastChild
			try:
				childNode=self.HTMLNode.lastChild
			except COMError:
				return None
			obj=MSHTML(HTMLNode=childNode)
			if obj and obj.HTMLNodeName in self.HTMLNodeNameNavSkipList:
				return None
			return obj
		return super(MSHTML,self).firstChild

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
			except (COMError,NameError):
				pass
		super(MSHTML,self).doAction(index=index)

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

