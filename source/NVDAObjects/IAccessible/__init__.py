#NVDAObjects/IAccessible.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

from comtypes import COMError, IServiceProvider, GUID
import ctypes
import os
import re
from comInterfaces.tom import ITextDocument
import tones
import textInfos.offsets
import colors
import time
import displayModel
import IAccessibleHandler
import oleacc
import JABHandler
import winUser
import globalVars
from logHandler import log
import speech
import braille
import api
import config
import controlTypes
from NVDAObjects.window import Window
from NVDAObjects import NVDAObject, NVDAObjectTextInfo, InvalidNVDAObject
import NVDAObjects.JAB
import eventHandler
import queueHandler
from NVDAObjects.behaviors import ProgressBar, Dialog, EditableTextWithAutoSelectDetection

def getNVDAObjectFromEvent(hwnd,objectID,childID):
	try:
		accHandle=IAccessibleHandler.accessibleObjectFromEvent(hwnd,objectID,childID)
	except:
		accHandle=None
	if not accHandle:
		return None
	(pacc,accChildID)=accHandle
	obj=IAccessible(IAccessibleObject=pacc,IAccessibleChildID=accChildID,event_windowHandle=hwnd,event_objectID=objectID,event_childID=childID)
	return obj

def getNVDAObjectFromPoint(x,y):
	accHandle=IAccessibleHandler.accessibleObjectFromPoint(x,y)
	if not accHandle:
		return None
	(pacc,child)=accHandle
	obj=IAccessible(IAccessibleObject=pacc,IAccessibleChildID=child)
	return obj

class IA2TextTextInfo(textInfos.offsets.OffsetsTextInfo):

	detectFormattingAfterCursorMaybeSlow=False

	def _getOffsetFromPoint(self,x,y):
		if self.obj.IAccessibleTextObject.nCharacters>0:
			return self.obj.IAccessibleTextObject.OffsetAtPoint(x,y,IAccessibleHandler.IA2_COORDTYPE_SCREEN_RELATIVE)
		else:
			raise NotImplementedError

	def _getPointFromOffset(self,offset):
		try:
			res=self.obj.IAccessibleTextObject.characterExtents(offset,IAccessibleHandler.IA2_COORDTYPE_SCREEN_RELATIVE)
		except:
			raise NotImplementedError
		point=textInfos.Point(res[0]+(res[2]/2),res[1]+(res[3]/2))
		return point

	def _get_unit_mouseChunk(self):
		return "mouseChunk"

	def expand(self,unit):
		if unit==self.unit_mouseChunk:
			isMouseChunkUnit=True
			oldStart=self._startOffset
			oldEnd=self._endOffset
			unit=super(IA2TextTextInfo,self).unit_mouseChunk
		else:
			isMouseChunkUnit=False
		super(IA2TextTextInfo,self).expand(unit)
		if isMouseChunkUnit:
			text=self._getTextRange(self._startOffset,self._endOffset)
			try:
				self._startOffset=text.rindex(u'\ufffc',0,oldStart-self._startOffset)
			except ValueError:
				pass
			try:
				self._endOffset=text.index(u'\ufffc',oldEnd-self._startOffset)
			except ValueError:
				pass

	def _getCaretOffset(self):
		try:
			offset=self.obj.IAccessibleTextObject.caretOffset
		except COMError:
			log.debugWarning("IAccessibleText::caretOffset failed", exc_info=True)
			raise RuntimeError("Retrieving caret offset failed")
		if offset<0:
			raise RuntimeError("no active caret in this object")
		return offset

	def _setCaretOffset(self,offset):
		self.obj.IAccessibleTextObject.SetCaretOffset(offset)

	def _getSelectionOffsets(self):
		try:
			nSelections=self.obj.IAccessibleTextObject.nSelections
		except:
			nSelections=0
		if nSelections:
			(start,end)=self.obj.IAccessibleTextObject.Selection[0]
		else:
			start=self._getCaretOffset()
			end=start
		return [min(start,end),max(start,end)]

	def _setSelectionOffsets(self,start,end):
		for selIndex in range(self.obj.IAccessibleTextObject.NSelections):
			self.obj.IAccessibleTextObject.RemoveSelection(selIndex)
		self.obj.IAccessibleTextObject.AddSelection(start,end)

	def _getStoryLength(self):
		try:
			return self.obj.IAccessibleTextObject.NCharacters
		except:
			log.debugWarning("IAccessibleText::nCharacters failed",exc_info=True)
			return 0

	def _getLineCount(self):
			return -1

	def _getTextRange(self,start,end):
		try:
			return self.obj.IAccessibleTextObject.text(start,end)
		except:
			return ""

	def _getFormatFieldAndOffsets(self,offset,formatConfig,calculateOffsets=True):
		try:
			startOffset,endOffset,attribsString=self.obj.IAccessibleTextObject.attributes(offset)
		except COMError:
			log.debugWarning("could not get attributes",exc_info=True)
			return textInfos.FormatField(),(self._startOffset,self._endOffset)
		formatField=textInfos.FormatField()
		if not attribsString and offset>0:
			try:
				attribsString=self.obj.IAccessibleTextObject.attributes(offset-1)[2]
			except COMError:
				pass
		if attribsString:
			formatField.update(IAccessibleHandler.splitIA2Attribs(attribsString))
		try:
			textAlign=formatField.pop("text-align")
		except KeyError:
			textAlign=None
		if textAlign:
			if "right" in textAlign:
				textAlign="right"
			elif "center" in textAlign:
				textAlign="center"
			elif "justify" in textAlign:
				textAlign="justify"
			formatField["text-align"]=textAlign
		try:
			fontWeight=formatField.pop("font-weight")
		except KeyError:
			fontWeight=None
		if fontWeight is not None and (fontWeight.lower()=="bold" or (fontWeight.isdigit() and int(fontWeight)>=700)):
			formatField["bold"]=True
		else:
			formatField["bold"]=False
		try:
			fontStyle=formatField.pop("font-style")
		except KeyError:
			fontStyle=None
		if fontStyle is not None and fontStyle.lower()=="italic":
			formatField["italic"]=True
		else:
			formatField["italic"]=False
		try:
			invalid=formatField.pop("invalid")
		except KeyError:
			invalid=None
		if invalid and invalid.lower()=="spelling":
			formatField["invalid-spelling"]=True
		color=formatField.get('color')
		if color:
			try:
				formatField['color']=colors.RGB.fromString(color)
			except ValueError:
				pass
		backgroundColor=formatField.get('background-color')
		if backgroundColor:
			try:
				formatField['background-color']=colors.RGB.fromString(backgroundColor)
			except ValueError:
				pass
		return formatField,(startOffset,endOffset)

	def _getCharacterOffsets(self,offset):
		try:
			if offset>=self.obj.IAccessibleTextObject.nCharacters:
				return offset,offset+1
		except:
			pass
		try:
			return self.obj.IAccessibleTextObject.TextAtOffset(offset,IAccessibleHandler.IA2_TEXT_BOUNDARY_CHAR)[0:2]
		except:
			return super(IA2TextTextInfo,self)._getCharacterOffsets(offset)

	def _getWordOffsets(self,offset):
		try:
			if offset>=self.obj.IAccessibleTextObject.nCharacters:
				return offset,offset+1
		except:
			pass
		try:
			return self.obj.IAccessibleTextObject.TextAtOffset(offset,IAccessibleHandler.IA2_TEXT_BOUNDARY_WORD)[0:2]
		except:
			return super(IA2TextTextInfo,self)._getWordOffsets(offset)

	def _getLineOffsets(self,offset):
		try:
			start,end,text=self.obj.IAccessibleTextObject.TextAtOffset(offset,IAccessibleHandler.IA2_TEXT_BOUNDARY_LINE)
			return start,end
		except:
			log.debugWarning("IAccessibleText::textAtOffset failed",exc_info=True)
			return offset,offset+1

	def _getSentenceOffsets(self,offset):
		try:
			if offset>=self.obj.IAccessibleTextObject.nCharacters:
				return offset,offset+1
		except:
			pass
		try:
			start,end,text=self.obj.IAccessibleTextObject.TextAtOffset(offset,IAccessibleHandler.IA2_TEXT_BOUNDARY_SENTENCE)
			if start==end:
				raise NotImplementedError
			return start,end
		except:
			return super(IA2TextTextInfo,self)._getSentenceOffsets(offset)

	def _getParagraphOffsets(self,offset):
		try:
			if offset>=self.obj.IAccessibleTextObject.nCharacters:
				return offset,offset+1
		except:
			pass
		try:
			start,end,text=self.obj.IAccessibleTextObject.TextAtOffset(offset,IAccessibleHandler.IA2_TEXT_BOUNDARY_PARAGRAPH)
			if start>=end:
				raise RuntimeError("did not expand to paragraph correctly")
			return start,end
		except:
			return super(IA2TextTextInfo,self)._getParagraphOffsets(offset)

	def _lineNumFromOffset(self,offset):
		return -1

	def getEmbeddedObject(self, offset=0):
		offset += self._startOffset

		# Mozilla uses IAccessibleHypertext to facilitate quick retrieval of embedded objects.
		try:
			ht = self.obj.IAccessibleTextObject.QueryInterface(IAccessibleHandler.IAccessibleHypertext)
			hl = ht.hyperlink(ht.hyperlinkIndex(offset))
			return IAccessible(IAccessibleObject=hl.QueryInterface(IAccessibleHandler.IAccessible2), IAccessibleChildID=0)
		except COMError:
			pass

		# Otherwise, we need to count the embedded objects to determine which child to use.
		# This could possibly be optimised by caching.
		text = self._getTextRange(0, offset + 1)
		childIndex = text.count(u"\uFFFC")
		try:
			return IAccessible(IAccessibleObject=IAccessibleHandler.accChild(self.obj.IAccessibleObject, childIndex)[0], IAccessibleChildID=0)
		except COMError:
			pass

		raise LookupError

class IAccessible(Window):
	"""
the NVDAObject for IAccessible
@ivar IAccessibleChildID: the IAccessible object's child ID
@type IAccessibleChildID: int
"""

	IAccessibleTableUsesTableCellIndexAttrib=False #: Should the table-cell-index IAccessible2 object attribute be used rather than indexInParent?

	@classmethod
	def getPossibleAPIClasses(cls,kwargs,relation=None):
		if not kwargs.get('IAccessibleChildID'):
			from . import MSHTML
			yield MSHTML.MSHTML

	@classmethod
	def kwargsFromSuper(cls,kwargs,relation=None):
		acc=None
		objID=None
		windowHandle=kwargs['windowHandle']
		if isinstance(relation,tuple):
			acc=IAccessibleHandler.accessibleObjectFromPoint(relation[0],relation[1])
		elif relation=="focus":
			objID=winUser.OBJID_CLIENT
			acc=IAccessibleHandler.accessibleObjectFromEvent(windowHandle,objID,0)
			if not acc:
				return False
			testAccFocus=acc
			usedAccFocus=False
			# Keep doing accFocus until we can't anymore or until accFocus keeps returning the same object.
			while True:
				testAccFocus=IAccessibleHandler.accFocus(testAccFocus[0])
				# Only set the acc variable if we get something useful using accFocus.
				if testAccFocus and testAccFocus!=acc:
					acc=testAccFocus
					usedAccFocus=True
				else:
					# We can't go any further.
					break
			if usedAccFocus:
				# We don't know the event parameters for this object.
				objID=None
				# This object may also be in a different window, so we need to recalculate the window handle.
				kwargs['windowHandle']=None
		elif relation in ("parent","foreground"):
			objID=winUser.OBJID_CLIENT
		else:
			objID=winUser.OBJID_WINDOW
		if not acc and objID is not None:
			acc=IAccessibleHandler.accessibleObjectFromEvent(windowHandle,objID,0)
		if not acc:
			return False
		kwargs['IAccessibleObject']=acc[0]
		kwargs['IAccessibleChildID']=acc[1]
		if objID:
			# We know the event parameters, so pass them to the NVDAObject.
			kwargs['event_windowHandle']=windowHandle
			kwargs['event_objectID']=objID
			kwargs['event_childID']=0
		return True

	@classmethod
	def windowHasExtraIAccessibles(cls,windowHandle):
		"""Finds out whether this window has things such as a system menu / titleBar / scroll bars, which would be represented as extra IAccessibles"""
		style=winUser.getWindowStyle(windowHandle)
		return bool(style&winUser.WS_SYSMENU)

	def findOverlayClasses(self,clsList):
		if self.event_objectID==winUser.OBJID_CLIENT and JABHandler.isJavaWindow(self.windowHandle): 
			clsList.append(JavaVMRoot)

		windowClassName=self.windowClassName
		role=self.IAccessibleRole

		if hasattr(self, "IAccessibleTextObject"):
			if role==oleacc.ROLE_SYSTEM_TEXT:
				isEditable=True
			else:
				try:
					isEditable=bool(self.IAccessibleObject.states&IAccessibleHandler.IA2_STATE_EDITABLE)
				except:
					isEditable=False
			if isEditable:
				clsList.append(EditableTextWithAutoSelectDetection)

		# Use window class name and role to search for a class match in our static map.
		keys=[(windowClassName,role),(None,role),(windowClassName,None)]
		normalizedWindowClassName=Window.normalizeWindowClassName(windowClassName)
		if normalizedWindowClassName!=windowClassName:
			keys.insert(1,(normalizedWindowClassName,role))
			keys.append((normalizedWindowClassName,None))
		for key in keys: 
			newCls=None
			classString=_staticMap.get(key,None)
			if classString and classString.find('.')>0:
				modString,classString=os.path.splitext(classString)
				classString=classString[1:]
				mod=__import__(modString,globals(),locals(),[])
				newCls=getattr(mod,classString)
			elif classString:
				newCls=globals()[classString]
			if newCls:
				clsList.append(newCls)

		# Some special cases.
		if windowClassName=="GeckoPluginWindow" and self.event_objectID==0 and self.IAccessibleChildID==0:
			from mozilla import GeckoPluginWindowRoot
			clsList.append(GeckoPluginWindowRoot)
		if (windowClassName in ("MozillaWindowClass", "GeckoPluginWindow") and not isinstance(self.IAccessibleObject, IAccessibleHandler.IAccessible2)) or windowClassName in ("MacromediaFlashPlayerActiveX", "ApolloRuntimeContentWindow", "ShockwaveFlash", "ShockwaveFlashLibrary"):
			# This is possibly a Flash object.
			from . import adobeFlash
			adobeFlash.findExtraOverlayClasses(self, clsList)
		elif windowClassName.startswith('Mozilla'):
			from . import mozilla
			mozilla.findExtraOverlayClasses(self, clsList)
		elif windowClassName.startswith('bosa_sdm'):
			from .msOffice import SDM
			clsList.append(SDM)
		elif windowClassName == "DirectUIHWND" and role == oleacc.ROLE_SYSTEM_TEXT:
			from NVDAObjects.window import DisplayModelEditableText
			clsList.append(DisplayModelEditableText)
		elif windowClassName == "ListBox" and role == oleacc.ROLE_SYSTEM_LISTITEM:
			windowStyle = self.windowStyle
			if (windowStyle & winUser.LBS_OWNERDRAWFIXED or windowStyle & winUser.LBS_OWNERDRAWVARIABLE) and not windowStyle & winUser.LBS_HASSTRINGS:
				# This is an owner drawn ListBox and text has not been set for the items.
				# See http://msdn.microsoft.com/en-us/library/ms971352.aspx#msaa_sa_listbxcntrls
				clsList.append(InaccessibleListBoxItem)
		elif windowClassName == "MsoCommandBar":
			from .msOffice import BrokenMsoCommandBar
			if BrokenMsoCommandBar.appliesTo(self):
				clsList.append(BrokenMsoCommandBar)
		elif windowClassName.startswith("Internet Explorer_"):
			from . import MSHTML
			MSHTML.findExtraIAccessibleOverlayClasses(self, clsList)

		#Support for Windowless richEdit
		if not hasattr(IAccessible,"IID_ITextServices"):
			try:
				IAccessible.IID_ITextServices=ctypes.cast(ctypes.windll.msftedit.IID_ITextServices,ctypes.POINTER(GUID)).contents
			except WindowsError:
				log.debugWarning("msftedit not available, couldn't retrieve IID_ITextServices")
				IAccessible.IID_ITextServices=None
		if IAccessible.IID_ITextServices:
			try:
				pDoc=self.IAccessibleObject.QueryInterface(IServiceProvider).QueryService(IAccessible.IID_ITextServices,ITextDocument)
			except COMError:
				pDoc=None
			if pDoc:
				self._ITextDocumentObject=pDoc
				self.useITextDocumentSupport=True
				self.editAPIVersion=2
				from NVDAObjects.window.edit import Edit
				clsList.append(Edit)

		#Window root IAccessibles
		if self.event_objectID in (None,winUser.OBJID_WINDOW) and self.event_childID==0 and self.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW:
			clsList.append(WindowRoot)

		if self.event_objectID==winUser.OBJID_TITLEBAR and self.event_childID==0:
			clsList.append(Titlebar)

		clsList.append(IAccessible)


		if self.event_objectID==winUser.OBJID_CLIENT and self.event_childID==0:
			# This is the main (client) area of the window, so we can use other classes at the window level.
			super(IAccessible,self).findOverlayClasses(clsList)
			#Generic client IAccessibles with no children should be classed as content and should use displayModel 
			if clsList[0]==IAccessible and len(clsList)==3 and self.IAccessibleRole==oleacc.ROLE_SYSTEM_CLIENT and self.childCount==0:
				clsList.insert(0,ContentGenericClient)
 
	def __init__(self,windowHandle=None,IAccessibleObject=None,IAccessibleChildID=None,event_windowHandle=None,event_objectID=None,event_childID=None):
		"""
@param pacc: a pointer to an IAccessible object
@type pacc: ctypes.POINTER(IAccessible)
@param child: A child ID that will be used on all methods of the IAccessible pointer
@type child: int
@param hwnd: the window handle, if known
@type hwnd: int
@param objectID: the objectID for the IAccessible Object, if known
@type objectID: int
"""
		# Try every trick in the book to get the window handle if we don't have it.
		if not windowHandle and isinstance(IAccessibleObject,IAccessibleHandler.IAccessible2):
			try:
				windowHandle=IAccessibleObject.windowHandle
			except COMError, e:
				log.debugWarning("IAccessible2::windowHandle failed: %s" % e)
			#Mozilla Gecko: we can never use a MozillaWindowClass window for Gecko 1.9
			tempWindow=windowHandle
			while tempWindow and winUser.getClassName(tempWindow)=="MozillaWindowClass":
				tempWindow=winUser.getAncestor(tempWindow,winUser.GA_PARENT)
			if tempWindow and winUser.getClassName(tempWindow).startswith('Mozilla'):
				windowHandle=tempWindow
		try:
			Identity=IAccessibleHandler.getIAccIdentity(IAccessibleObject,IAccessibleChildID)
		except:
			Identity=None
		if event_windowHandle is None and Identity and 'windowHandle' in Identity:
			event_windowHandle=Identity['windowHandle']
		if event_objectID is None and Identity and 'objectID' in Identity:
			event_objectID=Identity['objectID']
		if event_childID is None and Identity and 'childID' in Identity:
			event_childID=Identity['childID']
		if not windowHandle and event_windowHandle:
			windowHandle=event_windowHandle
		if not windowHandle:
			windowHandle=IAccessibleHandler.windowFromAccessibleObject(IAccessibleObject)
		if not windowHandle:
			log.debugWarning("Resorting to WindowFromPoint on accLocation")
			try:
				left,top,width,height = IAccessibleObject.accLocation(0)
				windowHandle=winUser.user32.WindowFromPoint(winUser.POINT(left,top))
			except COMError, e:
				log.debugWarning("accLocation failed: %s" % e)
		if not windowHandle:
			raise InvalidNVDAObject("Can't get a window handle from IAccessible")

		# Set the event params based on our calculated/construction info if we must.
		if event_windowHandle is None:
			event_windowHandle=windowHandle
		if event_objectID is None and isinstance(IAccessibleObject,IAccessibleHandler.IAccessible2):
			event_objectID=winUser.OBJID_CLIENT
		if event_childID is None and isinstance(IAccessibleObject,IAccessibleHandler.IAccessible2):
			try:
				event_childID=IAccessibleObject.uniqueID
			except:
				log.debugWarning("could not get IAccessible2::uniqueID to use as event_childID",exc_info=True)
		if event_childID is None:
			event_childID=IAccessibleChildID

		self.IAccessibleObject=IAccessibleObject
		self.IAccessibleChildID=IAccessibleChildID
		self.event_windowHandle=event_windowHandle
		self.event_objectID=event_objectID
		self.event_childID=event_childID
		super(IAccessible,self).__init__(windowHandle=windowHandle)

		try:
			self.IAccessibleActionObject=IAccessibleObject.QueryInterface(IAccessibleHandler.IAccessibleAction)
		except:
			pass
		try:
			self.IAccessibleTableObject=self.IAccessibleObject.QueryInterface(IAccessibleHandler.IAccessibleTable)
		except:
			pass
		try:
			self.IAccessibleTextObject=IAccessibleObject.QueryInterface(IAccessibleHandler.IAccessibleText)
		except:
			pass
		if None not in (event_windowHandle,event_objectID,event_childID):
			IAccessibleHandler.liveNVDAObjectTable[(event_windowHandle,event_objectID,event_childID)]=self

	def isDuplicateIAccessibleEvent(self,obj):
		"""Compaires the object of an event to self to see if the event should be treeted as duplicate."""
		#MSAA child elements do not have unique winEvent params as a childID could be reused if an element was deleted etc
		if self.IAccessibleChildID>0:
			return False
		return obj.event_windowHandle==self.event_windowHandle and obj.event_objectID==self.event_objectID and obj.event_childID==self.event_childID

	def _get_shouldAllowIAccessibleFocusEvent(self):
		"""Determine whether a focus event should be allowed for this object.
		Normally, this checks for the focused state to help eliminate redundant or invalid focus events.
		However, some implementations do not correctly set the focused state, so this must be overridden.
		@return: C{True} if the focus event should be allowed.
		@rtype: bool
		"""
		#this object or one of its ancestors must have state_focused.
		testObj = self
		while testObj:
			if controlTypes.STATE_FOCUSED in testObj.states:
				break
			parent = testObj.parent
			# Cache the parent.
			testObj.parent = parent
			testObj = parent
		else:
			return False
		return True

	def _get_TextInfo(self):
		if hasattr(self,'IAccessibleTextObject'):
			return IA2TextTextInfo
		return super(IAccessible,self).TextInfo

	def _isEqual(self,other):
		if self.IAccessibleChildID!=other.IAccessibleChildID:
			return False
		if self.IAccessibleObject==other.IAccessibleObject: 
			return True
		try:
			if isinstance(self.IAccessibleObject,IAccessibleHandler.IAccessible2) and isinstance(other.IAccessibleObject,IAccessibleHandler.IAccessible2):
				# These are both IAccessible2 objects, so we can test unique ID.
				# Unique ID is only guaranteed to be unique within a given window, so we must check window handle as well.
				selfIA2Window=self.IAccessibleObject.windowHandle
				selfIA2ID=self.IAccessibleObject.uniqueID
				otherIA2Window=other.IAccessibleObject.windowHandle
				otherIA2ID=other.IAccessibleObject.uniqueID
				if selfIA2Window!=otherIA2Window:
					# The window handles are different, so these are definitely different windows.
					return False
				# At this point, we know that the window handles are equal.
				if selfIA2Window and (selfIA2ID or otherIA2ID):
					# The window handles are valid and one of the objects has a valid unique ID.
					# Therefore, we can safely determine equality or inequality based on unique ID.
					return selfIA2ID==otherIA2ID
		except:
			pass
		if self.event_windowHandle is not None and other.event_windowHandle is not None and self.event_windowHandle!=other.event_windowHandle:
			return False
		if self.event_objectID is not None and other.event_objectID is not None and self.event_objectID!=other.event_objectID:
			return False
		if self.event_childID is not None and other.event_childID is not None and self.event_childID!=other.event_childID:
			return False
		if not super(IAccessible,self)._isEqual(other):
			return False
		selfIden=self.IAccessibleIdentity
		otherIden=other.IAccessibleIdentity
		if selfIden!=otherIden:
			return False
		if self.location!=other.location:
			return False
 		if self.IAccessibleRole!=other.IAccessibleRole:
			return False
		if self.name!=other.name:
			return False
		return True

	def _get_name(self):
		#The edit field in a combo box should not have a label
		if self.role==controlTypes.ROLE_EDITABLETEXT:
			# Make sure to cache the parents.
			parent=self.parent=self.parent
			if parent and parent.role==controlTypes.ROLE_WINDOW:
				# The parent of the edit field is a window, so try the next ancestor.
				parent=self.parent.parent=self.parent.parent
			# Only scrap the label on the edit field if the parent combo box has a label.
			if parent and parent.role==controlTypes.ROLE_COMBOBOX and parent.name:
				return ""

		try:
			res=self.IAccessibleObject.accName(self.IAccessibleChildID)
		except:
			res=None
		if not res and hasattr(self,'IAccessibleTextObject'):
			try:
				res=self.makeTextInfo(textInfos.POSITION_CARET).text
				if res:
					return
			except (NotImplementedError, RuntimeError):
				try:
					res=self.makeTextInfo(textInfos.POSITION_ALL).text
				except (NotImplementedError, RuntimeError):
					res=None
		return res if isinstance(res,basestring) and not res.isspace() else None

	def _get_value(self):
		try:
			res=self.IAccessibleObject.accValue(self.IAccessibleChildID)
		except:
			res=None
		return res if isinstance(res,basestring) and not res.isspace() else None

	def _get_actionCount(self):
		if hasattr(self,'IAccessibleActionObject'):
			try:
				return self.IAccessibleActionObject.nActions()
			except COMError:
				return 0
		return 1

	def getActionName(self,index=None):
		if not index:
			index=self.defaultActionIndex
		if hasattr(self,'IAccessibleActionObject'):
			try:
				return self.IAccessibleActionObject.name(index)
			except COMError:
				raise NotImplementedError
		elif index==0:
			try:
				action=self.IAccessibleObject.accDefaultAction(self.IAccessibleChildID)
			except COMError:
				action=None
			if action:
				return action
		raise NotImplementedError

	def doAction(self,index=None):
		if not index:
			index=self.defaultActionIndex
		if hasattr(self,'IAccessibleActionObject'):
			try:
				self.IAccessibleActionObject.doAction(index)
				return
			except COMError:
				raise NotImplementedError
		elif index==0:
			try:
				self.IAccessibleObject.accDoDefaultAction(self.IAccessibleChildID)
				return
			except COMError:
				raise NotImplementedError
		raise NotImplementedError

	def _get_IAccessibleIdentity(self):
		if not hasattr(self,'_IAccessibleIdentity'):
			try:
				self._IAccessibleIdentity=IAccessibleHandler.getIAccIdentity(self.IAccessibleObject,self.IAccessibleChildID)
			except:
				self._IAccessibleIdentity=None
		return self._IAccessibleIdentity

	def _get_IAccessibleRole(self):
		if isinstance(self.IAccessibleObject,IAccessibleHandler.IAccessible2):
			try:
				role=self.IAccessibleObject.role()
			except:
				role=0
		else:
			role=0
		if role==0:
			try:
				role=self.IAccessibleObject.accRole(self.IAccessibleChildID)
			except:
				role=0
		return role


	def _get_role(self):
		IARole=self.IAccessibleRole
		if IARole==oleacc.ROLE_SYSTEM_CLIENT:
			superRole=super(IAccessible,self).role
			if superRole!=controlTypes.ROLE_WINDOW:
					return superRole
		if isinstance(IARole,basestring):
			IARole=IARole.split(',')[0].lower()
			log.debug("IARole: %s"%IARole)
		return IAccessibleHandler.IAccessibleRolesToNVDARoles.get(IARole,controlTypes.ROLE_UNKNOWN)

	def _get_IAccessibleStates(self):
		try:
			res=self.IAccessibleObject.accState(self.IAccessibleChildID)
		except:
			return 0
		return res if isinstance(res,int) else 0

	def _get_states(self):
		states=set()
		if self.event_objectID in (winUser.OBJID_CLIENT, winUser.OBJID_WINDOW) and self.event_childID == 0:
			states.update(super(IAccessible, self).states)
		try:
			IAccessibleStates=self.IAccessibleStates
		except:
			log.debugWarning("could not get IAccessible states",exc_info=True)
		else:
			states.update(IAccessibleHandler.IAccessibleStatesToNVDAStates[x] for x in (y for y in (1<<z for z in xrange(32)) if y&IAccessibleStates) if IAccessibleHandler.IAccessibleStatesToNVDAStates.has_key(x))
		if not hasattr(self.IAccessibleObject,'states'):
			# Not an IA2 object.
			return states
		try:
			IAccessible2States=self.IAccessibleObject.states
		except:
			log.debugWarning("could not get IAccessible2 states",exc_info=True)
			IAccessible2States=IAccessibleHandler.IA2_STATE_DEFUNCT
		states=states|set(IAccessibleHandler.IAccessible2StatesToNVDAStates[x] for x in (y for y in (1<<z for z in xrange(32)) if y&IAccessible2States) if IAccessibleHandler.IAccessible2StatesToNVDAStates.has_key(x))
		try:
			IA2Attribs=self.IA2Attributes
		except COMError:
			log.debugWarning("could not get IAccessible2 attributes",exc_info=True)
			IA2Attribs=None
		if IA2Attribs:
			grabbed = IA2Attribs.get("grabbed")
			if grabbed == "false":
				states.add(controlTypes.STATE_DRAGGABLE)
			elif grabbed == "true":
				states.add(controlTypes.STATE_DRAGGING)
			if IA2Attribs.get("dropeffect", "none") != "none":
				states.add(controlTypes.STATE_DROPTARGET)
		if controlTypes.STATE_HASPOPUP in states and controlTypes.STATE_AUTOCOMPLETE in states:
			states.remove(controlTypes.STATE_HASPOPUP)
		if controlTypes.STATE_HALFCHECKED in states:
			states.discard(controlTypes.STATE_CHECKED)
		return states

	re_positionInfoEncodedAccDescription=re.compile(r"L(?P<level>\d+), (?P<indexInGroup>\d+) of (?P<similarItemsInGroup>\d+)")

	def _get_decodedAccDescription(self):
		try:
			description=self.IAccessibleObject.accDescription(self.IAccessibleChildID)
		except COMError:
			return None
		if description.startswith('description:'):
			return description[12:].strip()
		m=self.re_positionInfoEncodedAccDescription.match(description)
		if m:
			return m
		return description

	hasEncodedAccDescription=False #:If true, accDescription contains info such as level, and number of items etc.

	def _get_description(self):
		if self.hasEncodedAccDescription:
			d=self.decodedAccDescription
			if isinstance(d,basestring):
				return d
			else:
				return ""
		try:
			res=self.IAccessibleObject.accDescription(self.IAccessibleChildID)
		except:
			res=None
		return res if isinstance(res,basestring) and not res.isspace() else None

	def _get_keyboardShortcut(self):
		try:
			res=self.IAccessibleObject.accKeyboardShortcut(self.IAccessibleChildID)
		except:
			res=None
		return res if isinstance(res,basestring) and not res.isspace() else None

	def _get_childCount(self):
		if self.IAccessibleChildID>0:
			return 0
		try:
			return max(self.IAccessibleObject.accChildCount,0)
		except COMError:
			return 0

	def _get_location(self):
		try:
			return self.IAccessibleObject.accLocation(self.IAccessibleChildID)
		except COMError:
			return None

	def isPointInObject(self,x,y):
		if self.windowHandle and not super(IAccessible,self).isPointInObject(x,y):
			return False
		res=IAccessibleHandler.accHitTest(self.IAccessibleObject,self.IAccessibleChildID,x,y)
		if not res or res[0]!=self.IAccessibleObject or res[1]!=self.IAccessibleChildID:
			return False
		return True

	def _get_labeledBy(self):
		try:
			(pacc,accChild)=IAccessibleHandler.accNavigate(self.IAccessibleObject,self.IAccessibleChildID,IAccessibleHandler.NAVRELATION_LABELLED_BY)
			obj=IAccessible(IAccessibleObject=pacc,IAccessibleChildID=accChild)
			return obj
		except:
			return None

	parentUsesSuperOnWindowRootIAccessible=True #: on a window root IAccessible, super should be used instead of accParent

	def _get_parent(self):
		if self.IAccessibleChildID>0:
			return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=0,event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=0) or super(IAccessible,self).parent
		if self.parentUsesSuperOnWindowRootIAccessible and self.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW:
			return super(IAccessible,self).parent
		res=IAccessibleHandler.accParent(self.IAccessibleObject,self.IAccessibleChildID)
		if res:
			parentObj=IAccessible(IAccessibleObject=res[0],IAccessibleChildID=res[1])
			if parentObj:
				#Hack around bad MSAA implementations that deliberately skip the window root IAccessible in the ancestry (Skype, iTunes)
				if parentObj.windowHandle!=self.windowHandle and self.IAccessibleRole!=oleacc.ROLE_SYSTEM_WINDOW and winUser.getAncestor(self.windowHandle,winUser.GA_PARENT)==parentObj.windowHandle:
					windowObj=Window(windowHandle=self.windowHandle)
					if windowObj and windowObj.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW and windowObj.parent==parentObj:
						return windowObj
			return self.correctAPIForRelation(parentObj,relation="parent") or super(IAccessible,self).parent
		return super(IAccessible,self).parent

	def _get_next(self):
		if self.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW:
			return super(IAccessible,self).next 
		res=IAccessibleHandler.accNavigate(self.IAccessibleObject,self.IAccessibleChildID,oleacc.NAVDIR_NEXT)
		if not res:
			return None
		if res[0]==self.IAccessibleObject:
			#A sanity check for childIDs.
			if self.IAccessibleChildID>0 and res[1]>self.IAccessibleChildID:
				return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=res[1],event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=res[1])
		else:
			return self.correctAPIForRelation(IAccessible(IAccessibleObject=res[0],IAccessibleChildID=res[1]))

	def _get_previous(self):
		if self.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW:
			return super(IAccessible,self).previous
		res=IAccessibleHandler.accNavigate(self.IAccessibleObject,self.IAccessibleChildID,oleacc.NAVDIR_PREVIOUS)
		if not res:
			return None
		if res[0]==self.IAccessibleObject:
			#A sanity check for childIDs.
			if self.IAccessibleChildID>1 and res[1]<self.IAccessibleChildID:
				return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=res[1],event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=res[1])
		else:
			return self.correctAPIForRelation(IAccessible(IAccessibleObject=res[0],IAccessibleChildID=res[1]))

	def _get_firstChild(self):
		child=IAccessibleHandler.accNavigate(self.IAccessibleObject,self.IAccessibleChildID,oleacc.NAVDIR_FIRSTCHILD)
		if not child and self.IAccessibleChildID==0:
			children=IAccessibleHandler.accessibleChildren(self.IAccessibleObject,0,1)
			if len(children)>0:
				child=children[0]
		if child and child[0]==self.IAccessibleObject:
			#A sanity check for childIDs.
			if self.IAccessibleChildID==0 and child[1]>0: 
				return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=child[1],event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=child[1])
		elif child:
			obj=IAccessible(IAccessibleObject=child[0],IAccessibleChildID=child[1])
			if (obj and winUser.isDescendantWindow(self.windowHandle,obj.windowHandle)) or self.windowHandle==winUser.getDesktopWindow():
				return self.correctAPIForRelation(obj)

	def _get_lastChild(self):
		child=IAccessibleHandler.accNavigate(self.IAccessibleObject,self.IAccessibleChildID,oleacc.NAVDIR_LASTCHILD)
		if not child and self.IAccessibleChildID==0:
			try:
				childCount=self.IAccessibleObject.accChildCount
			except COMError:
				childCount=0
			if childCount>0:
				children=IAccessibleHandler.accessibleChildren(self.IAccessibleObject,childCount-1,1)
				if len(children)>0:
					child=children[-1]
		if child and child[0]==self.IAccessibleObject:
			#A sanity check for childIDs.
			if self.IAccessibleChildID==0 and child[1]>0: 
				return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=child[1],event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=child[1])
		elif child:
			obj=IAccessible(IAccessibleObject=child[0],IAccessibleChildID=child[1])
			if (obj and winUser.isDescendantWindow(self.windowHandle,obj.windowHandle)) or self.windowHandle==winUser.getDesktopWindow():
				return self.correctAPIForRelation(obj)

	def _get_children(self):
		if self.IAccessibleChildID>0:
			return []
		try:
			childCount= self.IAccessibleObject.accChildCount
		except COMError:
			childCount=0
		if childCount<=0:
			return []
		children=[]
		for IAccessibleObject,IAccessibleChildID in IAccessibleHandler.accessibleChildren(self.IAccessibleObject,0,childCount):
			if IAccessibleObject==self.IAccessibleObject:
				children.append(IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=IAccessibleChildID,event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=IAccessibleChildID))
				continue
			try:
				accRole=IAccessibleObject.accRole(0)
			except COMError:
				accRole=0
			#For Window root IAccessibles, we just want to use the new window handle, but use the best API for that window, rather than IAccessible
			#If it does happen to be IAccessible though, we only want the client, not the window root IAccessible
			if accRole==oleacc.ROLE_SYSTEM_WINDOW:
				try:
					windowHandle=oleacc.WindowFromAccessibleObject(IAccessibleObject)
				except WindowsError as e:
					log.debugWarning("WindowFromAccessibleObject failed: %s" % e)
					windowHandle=None
				if windowHandle:
					kwargs=dict(windowHandle=windowHandle)
					APIClass=Window.findBestAPIClass(kwargs,relation="parent") #Need a better relation type for this, but parent works ok -- gives the client
					children.append(APIClass(**kwargs))
					continue
			children.append(IAccessible(IAccessibleObject=IAccessibleObject,IAccessibleChildID=IAccessibleChildID))
		children=[x for x in children if x and winUser.isDescendantWindow(self.windowHandle,x.windowHandle)]
		return children

	def _get_IA2Attributes(self):
		try:
			attribs = self.IAccessibleObject.attributes
		except COMError as e:
			log.debugWarning("IAccessibleObject.attributes COMError %s"%e)
			attribs=None
		if attribs:
			return IAccessibleHandler.splitIA2Attribs(attribs)
		return {}

	def event_IA2AttributeChange(self):
		# We currently only care about changes to the accessible drag and drop attributes, which we map to states, so treat this as a stateChange.
		self.event_stateChange()

	def _get_rowNumber(self):
		table=self.table
		if table:
			if self.IAccessibleTableUsesTableCellIndexAttrib:
				try:
					index=self.IA2Attributes['table-cell-index']
				except KeyError:
					raise NotImplementedError
			else:
				index=self.IAccessibleObject.indexInParent
			index=int(index)
			try:
				return table.IAccessibleTableObject.rowIndex(index)+1
			except COMError:
				log.debugWarning("IAccessibleTable::rowIndex failed", exc_info=True)
		raise NotImplementedError

	def _get_columnNumber(self):
		table=self.table
		if table:
			if self.IAccessibleTableUsesTableCellIndexAttrib:
				try:
					index=self.IA2Attributes['table-cell-index']
				except KeyError:
					raise NotImplementedError
			else:
				index=self.IAccessibleObject.indexInParent
			index=int(index)
			try:
				return table.IAccessibleTableObject.columnIndex(index)+1
			except COMError:
				log.debugWarning("IAccessibleTable::columnIndex failed", exc_info=True)
		raise NotImplementedError

	def _get_rowCount(self):
		if hasattr(self,'IAccessibleTableObject'):
			try:
				return self.IAccessibleTableObject.nRows
			except COMError:
				log.debugWarning("IAccessibleTable::nRows failed", exc_info=True)
		raise NotImplementedError

	def _get_columnCount(self):
		if hasattr(self,'IAccessibleTableObject'):
			try:
				return self.IAccessibleTableObject.nColumns
			except COMError:
				log.debugWarning("IAccessibleTable::nColumns failed", exc_info=True)
		raise NotImplementedError

	def _get_table(self):
		if not isinstance(self.IAccessibleObject,IAccessibleHandler.IAccessible2):
			return None
		table=getattr(self,'_table',None)
		if table:
			return table
		checkAncestors=False
		if self.IAccessibleTableUsesTableCellIndexAttrib:
			try:
				attribs=self.IAccessibleObject.attributes
			except COMError:
				attribs=None
			if attribs and 'table-cell-index:' in attribs:
				checkAncestors=True
		obj=self.parent
		while checkAncestors and obj and not hasattr(obj,'IAccessibleTableObject'):
			parent=obj.parent=obj.parent
			obj=parent
		if not obj or not hasattr(obj,'IAccessibleTableObject'):
			return None
		self._table=obj
		return obj

	def _get_activeChild(self):
		if self.IAccessibleChildID==0:
			res=IAccessibleHandler.accFocus(self.IAccessibleObject)
			if res:
				if res[0]==self.IAccessibleObject:
					return IAccessible(windowHandle=self.windowHandle,IAccessibleObject=self.IAccessibleObject,IAccessibleChildID=res[1],event_windowHandle=self.event_windowHandle,event_objectID=self.event_objectID,event_childID=res[1])
				return IAccessible(IAccessibleObject=res[0],IAccessibleChildID=res[1])

	def _get_hasFocus(self):
		if (self.IAccessibleStates&oleacc.STATE_SYSTEM_FOCUSED):
			return True
		else:
			return False

	def setFocus(self):
		try:
			self.IAccessibleObject.accSelect(1,self.IAccessibleChildID)
		except:
			pass

	def scrollIntoView(self):
		if isinstance(self.IAccessibleObject, IAccessibleHandler.IAccessible2):
			try:
				self.IAccessibleObject.scrollTo(IAccessibleHandler.IA2_SCROLL_TYPE_ANYWHERE)
			except:
				log.debugWarning("IAccessible2::scrollTo failed", exc_info=True)

	def _get_allowIAccessibleChildIDAndChildCountForPositionInfo(self):
		"""if true position info should fall back to using the childID and the parent's accChildCount for position information if there is nothing better available."""
		return config.conf["presentation"]["guessObjectPositionInformationWhenUnavailable"]

	def _get_positionInfo(self):
		if isinstance(self.IAccessibleObject,IAccessibleHandler.IAccessible2):
			try:
				level,similarItemsInGroup,indexInGroup=self.IAccessibleObject.groupPosition
				return dict(level=level,indexInGroup=indexInGroup,similarItemsInGroup=similarItemsInGroup)
			except COMError:
				pass
		if self.hasEncodedAccDescription:
			d=self.decodedAccDescription
			if d and not isinstance(d,basestring):
				groupdict=d.groupdict()
				return dict(level=int(groupdict.get('level','0')),indexInGroup=int(groupdict.get('indexInGroup','0')),similarItemsInGroup=int(groupdict.get('similarItemsInGroup','0')))
		if self.allowIAccessibleChildIDAndChildCountForPositionInfo and self.IAccessibleChildID>0:
			indexInGroup=self.IAccessibleChildID
			parent=self.parent
			if parent:
				similarItemsInGroup=parent.childCount
				return dict(indexInGroup=indexInGroup,similarItemsInGroup=similarItemsInGroup)
		return {}

	def _get_indexInParent(self):
		if isinstance(self.IAccessibleObject, IAccessibleHandler.IAccessible2):
			try:
				return self.IAccessibleObject.indexInParent
			except COMError:
				pass
		raise NotImplementedError

	def _get__IA2Relations(self):
		if not isinstance(self.IAccessibleObject, IAccessibleHandler.IAccessible2):
			raise NotImplementedError
		import ctypes
		import comtypes.hresult
		try:
			size = self.IAccessibleObject.nRelations
		except COMError:
			raise NotImplementedError
		if size <= 0:
			return ()
		relations = (ctypes.POINTER(IAccessibleHandler.IAccessibleRelation) * size)()
		count = ctypes.c_int()
		# The client allocated relations array is an [out] parameter instead of [in, out], so we need to use the raw COM method.
		res = self.IAccessibleObject._IAccessible2__com__get_relations(size, relations, ctypes.byref(count))
		if res != comtypes.hresult.S_OK:
			raise NotImplementedError
		return list(relations)

	def _getIA2RelationFirstTarget(self, relationType):
		for relation in self._IA2Relations:
			try:
				if relation.relationType == relationType:
					return IAccessible(IAccessibleObject=IAccessibleHandler.normalizeIAccessible(relation.target(0)), IAccessibleChildID=0)
			except COMError:
				pass
		return None

	def _get_flowsTo(self):
		return self._getIA2RelationFirstTarget(IAccessibleHandler.IA2_RELATION_FLOWS_TO)

	def _get_flowsFrom(self):
		return self._getIA2RelationFirstTarget(IAccessibleHandler.IA2_RELATION_FLOWS_FROM)

	def _get_embeddingTextInfo(self):
		if not hasattr(self, "IAccessibleTextObject"):
			raise NotImplementedError
		try:
			hl = self.IAccessibleTextObject.QueryInterface(IAccessibleHandler.IAccessibleHyperlink)
			hlOffset = hl.startIndex
			return self.parent.makeTextInfo(textInfos.offsets.Offsets(hlOffset, hlOffset + 1))
		except COMError:
			pass
		return None

	def event_valueChange(self):
		if hasattr(self,'IAccessibleTextObject'):
			self.hasContentChangedSinceLastSelection=True
			return
		return super(IAccessible,self).event_valueChange()

	def event_alert(self):
		if self.role != controlTypes.ROLE_ALERT:
			# Ignore alert events on objects that aren't alerts.
			return
		# If the focus is within the alert object, don't report anything for it.
		if eventHandler.isPendingEvents("gainFocus"):
			# The alert event might be fired before the focus.
			api.processPendingEvents()
		if self in api.getFocusAncestors():
			return
		speech.cancelSpeech()
		speech.speakObject(self, reason=speech.REASON_FOCUS)
		for child in self.recursiveDescendants:
			if controlTypes.STATE_FOCUSABLE in child.states:
				speech.speakObject(child, reason=speech.REASON_FOCUS)

	def event_caret(self):
		super(IAccessible, self).event_caret()
		if self.IAccessibleRole==oleacc.ROLE_SYSTEM_CARET:
			return
		focusObject=api.getFocusObject()
		if self!=focusObject and not self.treeInterceptor and hasattr(self,'IAccessibleTextObject'):
			inDocument=None
			for ancestor in reversed(api.getFocusAncestors()+[focusObject]):
				if ancestor.role==controlTypes.ROLE_DOCUMENT:
					inDocument=ancestor
					break
			if not inDocument:
				return
			parent=self
			caretInDocument=False
			while parent:
				if parent==inDocument:
 					caretInDocument=True
					break
				parent=parent.parent
			if not caretInDocument:
				return
			try:
				info=self.makeTextInfo(textInfos.POSITION_CARET)
			except RuntimeError:
				return
			info.expand(textInfos.UNIT_CHARACTER)
			try:
				char=ord(info.text)
			except:
				char=0
			if char!=0xfffc:
				IAccessibleHandler.processFocusNVDAEvent(self)

	def _get_groupName(self):
		return None
		if self.IAccessibleChildID>0:
			return None
		else:
			return super(IAccessible,self)._get_groupName()

	def speakDescendantObjects(self,hashList=None):
		if hashList is None:
			hashList=[]
		child=self.firstChild
		while child and winUser.isDescendantWindow(self.windowHandle,child.windowHandle):
			h=hash(child)
			if h not in hashList:
				hashList.append(h)
				speech.speakObject(child,reason=speech.REASON_FOCUS)
				child.speakDescendantObjects(hashList=hashList)
			child=child.next

	def event_selection(self):
		return self.event_stateChange()

	def event_selectionAdd(self):
		return self.event_stateChange()

	def event_selectionRemove(self):
		return self.event_stateChange()

	def event_selectionWithIn(self):
		return self.event_stateChange()

	def _get_presentationType(self):
		if not self.windowHasExtraIAccessibles(self.windowHandle) and self.role==controlTypes.ROLE_WINDOW:
			return self.presType_layout
		return super(IAccessible,self).presentationType

	def _get_isPresentableFocusAncestor(self):
		IARole = self.IAccessibleRole
		if IARole == oleacc.ROLE_SYSTEM_CLIENT and self.windowStyle & winUser.WS_SYSMENU:
			return True
		if IARole == oleacc.ROLE_SYSTEM_WINDOW:
			return False
		return super(IAccessible, self).isPresentableFocusAncestor

	def _get_devInfo(self):
		info = super(IAccessible, self).devInfo
		iaObj = self.IAccessibleObject
		info.append("IAccessibleObject: %r" % iaObj)
		childID = self.IAccessibleChildID
		info.append("IAccessibleChildID: %r" % childID)
		info.append("IAccessible event parameters: windowHandle=%r, objectID=%r, childID=%r" % (self.event_windowHandle, self.event_objectID, self.event_childID))
		try:
			ret = iaObj.accRole(childID)
			for name, const in oleacc.__dict__.iteritems():
				if ret == const:
					ret = name
					break
			else:
				ret = repr(ret)
		except Exception as e:
			ret = "exception: %s" % e
		info.append("IAccessible accRole: %s" % ret)
		try:
			temp = iaObj.accState(childID)
			ret = ", ".join(
				name for name, const in oleacc.__dict__.iteritems()
				if name.startswith("STATE_") and temp & const
			) + " (%d)" % temp
		except Exception as e:
			ret = "exception: %s" % e
		info.append("IAccessible accState: %s" % ret)
		return info

class ContentGenericClient(IAccessible):

	TextInfo=displayModel.DisplayModelTextInfo
	presentationType=IAccessible.presType_content
	role=controlTypes.ROLE_UNKNOWN

	def _get_value(self):
		val=self.displayText
		truncate=len(val)>200
		if truncate:
			return u"%s\u2026"%val[:200]
		return val

class WindowRoot(IAccessible):

	TextInfo=displayModel.DisplayModelTextInfo

	def _get_container(self):
		#Support for groupbox windows
		groupboxObj=IAccessibleHandler.findGroupboxObject(self)
		if groupboxObj:
			return groupboxObj
		return super(WindowRoot,self).container


class ShellDocObjectView(IAccessible):

	def event_gainFocus(self):
		#Sometimes Shell DocObject View gets focus, when really the document inside it should
		#Adobe Reader 9 licence agreement
		if eventHandler.isPendingEvents("gainFocus") or self.childCount!=1:
			return super(ShellDocObjectView,self).event_gainFocus()
		child=self.firstChild
		if not child or child.windowClassName!="Internet Explorer_Server" or child.role!=controlTypes.ROLE_PANE:
			return super(ShellDocObjectView,self).event_gainFocus()
		child=child.firstChild
		if not child or child.windowClassName!="Internet Explorer_Server" or child.role!=controlTypes.ROLE_DOCUMENT:
			return super(ShellDocObjectView,self).event_gainFocus()
		eventHandler.queueEvent("gainFocus",child)

class JavaVMRoot(IAccessible):

	def _get_firstChild(self):
		jabContext=JABHandler.JABContext(hwnd=self.windowHandle)
		return NVDAObjects.JAB.JAB(jabContext=jabContext)

	def _get_lastChild(self):
		jabContext=JABHandler.JABContext(hwnd=self.windowHandle)
		return NVDAObjects.JAB.JAB(jabContext=jabContext)

	def _get_children(self):
		children=[]
		jabContext=JABHandler.JABContext(hwnd=self.windowHandle)
		obj=NVDAObjects.JAB.JAB(jabContext=jabContext)
		if obj:
			children.append(obj)
		return children

class Groupbox(IAccessible):

	def _get_description(self):
		next=self.next
		if next and next.name==self.name and next.role==controlTypes.ROLE_GRAPHIC:
			next=next.next
		if next and next.role==controlTypes.ROLE_STATICTEXT:
			nextNext=next.next
			if nextNext and nextNext.name!=next.name:
				return next.name
		return super(Groupbox,self)._get_description()

class TrayClockWClass(IAccessible):
	"""
	Based on NVDAObject but the role is changed to clock.
	"""

	def _get_role(self):
		return controlTypes.ROLE_CLOCK

class OutlineItem(IAccessible):

	def _get_value(self):
		val=super(OutlineItem,self)._get_value()
		try:
			int(val)
		except:
			return val

class Tooltip(IAccessible):

	def event_show(self):
		# TODO: Abstract this somehow.
		if (config.conf["presentation"]["reportTooltips"] and (self.IAccessibleRole==oleacc.ROLE_SYSTEM_TOOLTIP)) or (config.conf["presentation"]["reportHelpBalloons"] and (self.IAccessibleRole==oleacc.ROLE_SYSTEM_HELPBALLOON)):
			speech.speakObject(self,reason=speech.REASON_FOCUS)
			# TODO: Don't use getBrailleTextForProperties directly.
			braille.handler.message(braille.getBrailleTextForProperties(name=self.name, role=self.role))

class List(IAccessible):

	def _get_role(self):
		return controlTypes.ROLE_LIST

	def speakDescendantObjects(self,hashList=None):
		child=self.activeChild
		if child:
			speech.speakObject(child,reason=speech.REASON_FOCUS)

class ComboBox(IAccessible):

	def speakDescendantObjects(self,hashList=None):
		child=self.activeChild
		if child:
			speech.speakObject(child,reason=speech.REASON_FOCUS)

class Outline(IAccessible):

	def speakDescendantObjects(self,hashList=None):
		child=self.activeChild
		if child:
			speech.speakObject(child,reason=speech.REASON_FOCUS)

class SysLinkClient(IAccessible):

	def reportFocus(self):
		pass

class SysLink(IAccessible):

	def _get_name(self):
		#Workaround for #451 - explorer returns incorrect string length, thus it can contain garbage characters
		name=super(SysLink,self).name
		if name: 
			#Remove any data after the null character
			i=name.find('\0')
			if i>=0: name=name[:i]
		return name

class TaskList(IAccessible):
	isPresentableFocusAncestor = False

	def event_gainFocus(self):
		# Normally, we don't want to act on this focus event.
		if self.childCount == 0:
			# However, in Windows 7, the task list gets focus even if alt+tab is pressed with no applications open.
			# In this case, we must report the focus so the user knows where the focus has landed.
			return super(TaskList, self).event_gainFocus()

class TaskListIcon(IAccessible):

	allowIAccessibleChildIDAndChildCountForPositionInfo=True

	def _get_role(self):
		return controlTypes.ROLE_ICON

	def reportFocus(self):
		if controlTypes.STATE_INVISIBLE in self.states:
			return
		super(TaskListIcon,self).reportFocus()

class MenuItem(IAccessible):

	def _get_description(self):
		name=self.name
		description=super(MenuItem,self)._get_description()
		if description!=name:
			return description
		else:
			return None

	def _get_name(self):
		return super(MenuItem,self).name or self.displayText

	def event_gainFocus(self):
		if eventHandler.isPendingEvents("gainFocus"):
			return
		super(MenuItem, self).event_gainFocus()

class Taskbar(IAccessible):
	name = _("Taskbar")

class Button(IAccessible):

	def _get_name(self):
		name=super(Button,self).name
		if not name or name.isspace():
			name=self.displayText
		return name

class InaccessibleListBoxItem(IAccessible):
	"""
	Used for list item IAccessibles in inaccessible owner drawn ListBox controls.
	Overrides name to use display model text as MSAA doesn't provide a suitable name (it's usually either empty or contains garbage).
	"""

	def _get_name(self):
		return self.displayText

class StaticText(IAccessible):
	"""Support for owner-drawn staticText controls where accName is empty."""

	def _get_name(self):
		name=super(StaticText,self).name
		if not name or name.isspace():
				name=self.displayText
		return name


class Titlebar(IAccessible):
	"""A class for the standard MSAA titlebar, which shortcuts presentationType to be layout (for performance) and  makes the description property empty, as the standard accDescription is rather annoying."""

	presentationType=IAccessible.presType_layout

	def _get_description(self):
		return ""

class ReBarWindow32Client(IAccessible):
	"""
	The client IAccessible for a ReBarWindow32 window.
	Overrides firstChild/lastChild as accNavigate is not implemented, and IEnumVariant (children) gives back some strange buttons beside each child window with no accNavigate.
	"""

	def _get_firstChild(self):
		return super(IAccessible,self).firstChild

	def _get_lastChild(self):
		return super(IAccessible,self).lastChild

#A class for the listview window class, found sof ar only in the Cygwin Setup program.
#Makes sure its available in simple review mode, and uses display model
class ListviewPane(IAccessible):
	presentationType=IAccessible.presType_content
	role=controlTypes.ROLE_LIST
	TextInfo=displayModel.DisplayModelTextInfo
	name=""

###class mappings

_staticMap={
	("ReBarWindow32",oleacc.ROLE_SYSTEM_CLIENT):"ReBarWindow32Client",
	("Static",oleacc.ROLE_SYSTEM_STATICTEXT):"StaticText",
	("msctls_statusbar32",oleacc.ROLE_SYSTEM_STATICTEXT):"StaticText",
	(None,oleacc.ROLE_SYSTEM_PUSHBUTTON):"Button",
	("tooltips_class32",oleacc.ROLE_SYSTEM_TOOLTIP):"Tooltip",
	("tooltips_class32",oleacc.ROLE_SYSTEM_HELPBALLOON):"Tooltip",
	(None,oleacc.ROLE_SYSTEM_DIALOG):"Dialog",
	(None,oleacc.ROLE_SYSTEM_ALERT):"Dialog",
	(None,oleacc.ROLE_SYSTEM_PROPERTYPAGE):"Dialog",
	(None,oleacc.ROLE_SYSTEM_GROUPING):"Groupbox",
	("TrayClockWClass",oleacc.ROLE_SYSTEM_CLIENT):"TrayClockWClass",
	("TRxRichEdit",oleacc.ROLE_SYSTEM_CLIENT):"delphi.TRxRichEdit",
	(None,oleacc.ROLE_SYSTEM_OUTLINEITEM):"OutlineItem",
	(None,oleacc.ROLE_SYSTEM_LIST):"List",
	(None,oleacc.ROLE_SYSTEM_COMBOBOX):"ComboBox",
	(None,oleacc.ROLE_SYSTEM_OUTLINE):"Outline",
	(None,oleacc.ROLE_SYSTEM_PROGRESSBAR):"ProgressBar",
	("TRichView",oleacc.ROLE_SYSTEM_CLIENT):"delphi.TRichView",
	("TRichViewEdit",oleacc.ROLE_SYSTEM_CLIENT):"delphi.TRichViewEdit",
	("TTntDrawGrid.UnicodeClass",oleacc.ROLE_SYSTEM_CLIENT):"List",
	("SysListView32",oleacc.ROLE_SYSTEM_LIST):"sysListView32.List",
	("SysListView32",oleacc.ROLE_SYSTEM_LISTITEM):"sysListView32.ListItem",
	("SysListView32",oleacc.ROLE_SYSTEM_MENUITEM):"sysListView32.ListItem",
	("SysTreeView32",oleacc.ROLE_SYSTEM_OUTLINE):"sysTreeView32.TreeView",
	("SysTreeView32",oleacc.ROLE_SYSTEM_OUTLINEITEM):"sysTreeView32.TreeViewItem",
	("SysTreeView32",oleacc.ROLE_SYSTEM_MENUITEM):"sysTreeView32.TreeViewItem",
	("SysTreeView32",0):"sysTreeView32.BrokenCommctrl5Item",
	("ATL:SysListView32",oleacc.ROLE_SYSTEM_LISTITEM):"sysListView32.ListItem",
	("TWizardForm",oleacc.ROLE_SYSTEM_CLIENT):"delphi.Form",
	("SysLink",oleacc.ROLE_SYSTEM_CLIENT):"SysLinkClient",
	("SysLink",oleacc.ROLE_SYSTEM_LINK):"SysLink",
	("#32771",oleacc.ROLE_SYSTEM_LIST):"TaskList",
	("TaskSwitcherWnd",oleacc.ROLE_SYSTEM_LIST):"TaskList",
	("#32771",oleacc.ROLE_SYSTEM_LISTITEM):"TaskListIcon",
	("TaskSwitcherWnd",oleacc.ROLE_SYSTEM_LISTITEM):"TaskListIcon",
	("TGroupBox",oleacc.ROLE_SYSTEM_CLIENT):"delphi.TGroupBox",
	("TFormOptions",oleacc.ROLE_SYSTEM_CLIENT):"delphi.Form",
	("TMessageForm",oleacc.ROLE_SYSTEM_CLIENT):"delphi.Form",
	("TFormOptions",oleacc.ROLE_SYSTEM_WINDOW):"delphi.Form",
	("TTabSheet",oleacc.ROLE_SYSTEM_CLIENT):"delphi.TabSheet",
	("MsiDialogCloseClass",oleacc.ROLE_SYSTEM_CLIENT):"Dialog",
	(None,oleacc.ROLE_SYSTEM_MENUITEM):"MenuItem",
	("TPTShellList",oleacc.ROLE_SYSTEM_LISTITEM):"sysListView32.ListItem",
	("TProgressBar",oleacc.ROLE_SYSTEM_PROGRESSBAR):"ProgressBar",
	("AVL_AVView",None):"adobeAcrobat.AcrobatNode",
	("AVL_AVView",oleacc.ROLE_SYSTEM_TEXT):"adobeAcrobat.AcrobatTextNode",
	("AcrobatSDIWindow",oleacc.ROLE_SYSTEM_CLIENT):"adobeAcrobat.AcrobatSDIWindowClient",
	("mscandui21.candidate",oleacc.ROLE_SYSTEM_PUSHBUTTON):"IME.IMECandidate",
	("SysMonthCal32",oleacc.ROLE_SYSTEM_CLIENT):"SysMonthCal32.SysMonthCal32",
	("hh_kwd_vlist",oleacc.ROLE_SYSTEM_LIST):"hh.KeywordList",
	("Scintilla",oleacc.ROLE_SYSTEM_CLIENT):"scintilla.Scintilla",
	("TScintilla",oleacc.ROLE_SYSTEM_CLIENT):"scintilla.Scintilla",
	("AkelEditW",oleacc.ROLE_SYSTEM_CLIENT):"akelEdit.AkelEdit",
	("AkelEditA",oleacc.ROLE_SYSTEM_CLIENT):"akelEdit.AkelEdit",
	("MSOUNISTAT",oleacc.ROLE_SYSTEM_CLIENT):"msOffice.MSOUNISTAT",
	("QWidget",oleacc.ROLE_SYSTEM_CLIENT):"qt.Client",
	("QWidget",oleacc.ROLE_SYSTEM_LIST):"qt.Container",
	("QWidget",oleacc.ROLE_SYSTEM_OUTLINE):"qt.Container",
	("QWidget",oleacc.ROLE_SYSTEM_MENUBAR):"qt.Container",
	("QWidget",oleacc.ROLE_SYSTEM_OUTLINEITEM):"qt.TreeViewItem",
	("QPopup",oleacc.ROLE_SYSTEM_MENUPOPUP):"qt.Menu",
	("QWidget",oleacc.ROLE_SYSTEM_IPADDRESS):"qt.LayeredPane",
	("QWidget",oleacc.ROLE_SYSTEM_APPLICATION):"qt.Application",
	("Shell_TrayWnd",oleacc.ROLE_SYSTEM_CLIENT):"Taskbar",
	("Shell DocObject View",oleacc.ROLE_SYSTEM_CLIENT):"ShellDocObjectView",
	("listview",oleacc.ROLE_SYSTEM_CLIENT):"ListviewPane",
}
