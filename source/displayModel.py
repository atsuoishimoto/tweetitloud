from ctypes import *
from ctypes.wintypes import RECT
from comtypes import BSTR
import math
import api
import winUser
import NVDAHelper
import textInfos
from textInfos.offsets import OffsetsTextInfo

_getWindowTextInRect=None
_requestTextChangeNotificationsForWindow=None
#: Objects that have registered for text change notifications.
_textChangeNotificationObjs=[]

def initialize():
	global _getWindowTextInRect,_requestTextChangeNotificationsForWindow
	_getWindowTextInRect=CFUNCTYPE(c_long,c_long,c_long,c_int,c_int,c_int,c_int,c_int,c_int,POINTER(BSTR),POINTER(BSTR))(('displayModel_getWindowTextInRect',NVDAHelper.localLib),((1,),(1,),(1,),(1,),(1,),(1,),(1,),(1,),(2,),(2,)))
	_requestTextChangeNotificationsForWindow=NVDAHelper.localLib.displayModel_requestTextChangeNotificationsForWindow

def getWindowTextInRect(bindingHandle, windowHandle, left, top, right, bottom,minHorizontalWhitespace,minVerticalWhitespace):
	text, cpBuf = _getWindowTextInRect(bindingHandle, windowHandle, left, top, right, bottom,minHorizontalWhitespace,minVerticalWhitespace)
	if not text or not cpBuf:
		return "",[]

	characterRects = []
	cpBufIt = iter(cpBuf)
	for cp in cpBufIt:
		characterRects.append((ord(cp), ord(next(cpBufIt)), ord(next(cpBufIt)), ord(next(cpBufIt))))
	return text, characterRects

def requestTextChangeNotifications(obj, enable):
	if not enable:
		_textChangeNotificationObjs.remove(obj)
	_requestTextChangeNotificationsForWindow(obj.appModule.helperLocalBindingHandle, obj.windowHandle, enable)
	if enable:
		_textChangeNotificationObjs.append(obj)

def textChangeNotify(windowHandle, left, top, right, bottom):
	for obj in _textChangeNotificationObjs:
		if windowHandle == obj.windowHandle:
			# It is safe to call this event from this RPC thread.
			# This avoids an extra core cycle.
			obj.event_textChange()

class DisplayModelTextInfo(OffsetsTextInfo):

	minHorizontalWhitespace=8
	minVerticalWhitespace=32

	_cache__textAndRects = True
	def _get__textAndRects(self):
		left, top, width, height = self.obj.location
		return getWindowTextInRect(self.obj.appModule.helperLocalBindingHandle, self.obj.windowHandle, left, top, left + width, top + height,self.minHorizontalWhitespace,self.minVerticalWhitespace)

	def _getStoryText(self):
		return self._textAndRects[0]

	def _getStoryLength(self):
		return len(self._getStoryText())

	def _getTextRange(self, start, end):
		return self._getStoryText()[start:end]

	def _getPointFromOffset(self, offset):
		text,rects=self._textAndRects
		if not text or not rects or offset>=len(rects):
			raise LookupError
		x,y=rects[offset][:2]
		return textInfos.Point(x, y)

	def _getOffsetFromPoint(self, x, y):
		for charOffset, (charLeft, charTop, charRight, charBottom) in enumerate(self._textAndRects[1]):
			if charLeft<=x<charRight and charTop<=y<charBottom:
				return charOffset
		raise LookupError

	def _getClosestOffsetFromPoint(self,x,y):
		#Enumerate the character rectangles
		a=enumerate(self._textAndRects[1])
		#Convert calculate center points for all the rectangles
		b=((charOffset,(charLeft+(charRight-charLeft)/2,charTop+(charBottom-charTop)/2)) for charOffset,(charLeft,charTop,charRight,charBottom) in a)
		#Calculate distances from all center points to the given x and y
		#But place the distance before the character offset, to make sorting by distance easier
		c=((math.sqrt(abs(x-cx)**2+abs(y-cy)**2),charOffset) for charOffset,(cx,cy) in b)
		#produce a static list of distances and character offsets, sorted by distance 
		d=sorted(c)
		#Return the lowest offset with the shortest distance
		return d[0][1] if len(d)>0 else 0

	def _getNVDAObjectFromOffset(self,offset):
		try:
			p=self._getPointFromOffset(offset)
		except (NotImplementedError,LookupError):
			return self.obj
		obj=api.getDesktopObject().objectFromPoint(p.x,p.y)
		from NVDAObjects.window import Window
		if not obj or not isinstance(obj,Window) or not winUser.isDescendantWindow(self.obj.windowHandle,obj.windowHandle):
			return self.obj
		return obj

	def _getOffsetsFromNVDAObject(self,obj):
		l=obj.location
		if not l:
			raise RuntimeError
		x=l[0]+(l[2]/2)
		y=l[1]+(l[3]/2)
		offset=self._getClosestOffsetFromPoint(x,y)
		return offset,offset

	def _get_clipboardText(self):
		return super(DisplayModelTextInfo,self).clipboardText.replace('\0',' ')

class EditableTextDisplayModelTextInfo(DisplayModelTextInfo):

	minHorizontalWhitespace=1
	minVerticalWhitespace=4

	def _getCaretOffset(self):
		caretRect = winUser.getGUIThreadInfo(self.obj.windowThreadID).rcCaret
		objLocation=self.obj.location
		objRect=RECT(objLocation[0],objLocation[1],objLocation[0]+objLocation[2],objLocation[1]+objLocation[3])
		tempPoint = winUser.POINT()
		tempPoint.x=caretRect.left
		tempPoint.y=caretRect.top
		winUser.user32.ClientToScreen(self.obj.windowHandle, byref(tempPoint))
		caretRect.left=max(objRect.left,tempPoint.x)
		caretRect.top=max(objRect.top,tempPoint.y)
		tempPoint.x=caretRect.right
		tempPoint.y=caretRect.bottom
		winUser.user32.ClientToScreen(self.obj.windowHandle, byref(tempPoint))
		caretRect.right=min(objRect.right,tempPoint.x)
		caretRect.bottom=min(objRect.bottom,tempPoint.y)
		import speech
		for charOffset, (charLeft, charTop, charRight, charBottom) in enumerate(self._textAndRects[1]):
			#speech.speakMessage("caret %d,%d char %d,%d"%(caretRect.top,caretRect.bottom,charTop,charBottom))
			if caretRect.left>=charLeft and caretRect.right<=charRight and ((caretRect.top<=charTop and caretRect.bottom>=charBottom) or (caretRect.top>=charTop and caretRect.bottom<=charBottom)):
				return charOffset
		raise RuntimeError

	def _setCaretOffset(self,offset):
		rects=self._textAndRects[1]
		if offset>=len(rects):
			raise RuntimeError("offset %d out of range")
		left,top,right,bottom=rects[offset]
		x=left #+(right-left)/2
		y=top+(bottom-top)/2
		oldX,oldY=winUser.getCursorPos()
		winUser.setCursorPos(x,y)
		winUser.mouse_event(winUser.MOUSEEVENTF_LEFTDOWN,0,0,None,None)
		winUser.mouse_event(winUser.MOUSEEVENTF_LEFTUP,0,0,None,None)
		winUser.setCursorPos(oldX,oldY)

	def _getSelectionOffsets(self):
		offset=self._getCaretOffset()
		return offset,offset

	def _setSelectionOffsets(self,start,end):
		if start!=end:
			raise TypeError("Expanded selections not supported")
		self._setCaretOffset(start)
