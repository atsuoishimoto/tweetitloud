import ctypes
import IAccessibleHandler
import speech
import textInfos.offsets
import winKernel
import winUser
import globalVars
import controlTypes
import config
from . import Window
from .. import NVDAObjectTextInfo
import locale

#Window messages
SCI_POSITIONFROMPOINT=2022
SCI_POINTXFROMPOSITION=2164
SCI_POINTYFROMPOSITION=2165
SCI_GETTEXTRANGE=2162
SCI_GETTEXT=2182
SCI_GETTEXTLENGTH=2183
SCI_GETLENGTH=2006
SCI_GETCURRENTPOS=2008
SCI_GETANCHOR=2009
SCI_SETCURRENTPOS=2141
SCI_SETSELECTIONSTART=2142
SCI_GETSELECTIONSTART=2143
SCI_SETSELECTIONEND=2144
SCI_GETSELECTIONEND=2145
SCI_GETLINEENDPOSITION=2136
SCI_GETLINECOUNT=2154
SCI_LINEFROMPOSITION=2166
SCI_POSITIONFROMLINE=2167
SCI_GETSTYLEAT=2010
SCI_STYLEGETFONT=2486
SCI_STYLEGETSIZE=2485
SCI_STYLEGETBOLD=2483
SCI_STYLEGETITALIC=2484
SCI_STYLEGETUNDERLINE=2488
SCI_WORDSTARTPOSITION=2266
SCI_WORDENDPOSITION=2267
SCI_GETCODEPAGE=2137
SCI_POSITIONAFTER=2418

#constants
STYLE_DEFAULT=32
SC_CP_UTF8=65001

class CharacterRangeStruct(ctypes.Structure):
	_fields_=[
		('cpMin',ctypes.c_long),
		('cpMax',ctypes.c_long),
	]

class TextRangeStruct(ctypes.Structure):
	_fields_=[
		('chrg',CharacterRangeStruct),
		('lpstrText',ctypes.c_char_p),
	]

class ScintillaTextInfo(textInfos.offsets.OffsetsTextInfo):

	def _getOffsetFromPoint(self,x,y):
		return winUser.sendMessage(self.obj.windowHandle,SCI_POSITIONFROMPOINT,x,y)

	def _getPointFromOffset(self,offset):
		point=textInfos.Point(
		winUser.sendMessage(self.obj.windowHandle,SCI_POINTXFROMPOSITION,None,offset),
		winUser.sendMessage(self.obj.windowHandle,SCI_POINTYFROMPOSITION,None,offset)
		)
		if point.x and point.y:
			return point
		else:
			raise NotImplementedError

	def _getFormatFieldAndOffsets(self,offset,formatConfig,calculateOffsets=True):
		style=winUser.sendMessage(self.obj.windowHandle,SCI_GETSTYLEAT,offset,0)
		if calculateOffsets:
			#we need to manually see how far the style goes, limit to line
			lineStart,lineEnd=self._getLineOffsets(offset)
			startOffset=offset
			while startOffset>lineStart:
				curStyle=winUser.sendMessage(self.obj.windowHandle,SCI_GETSTYLEAT,startOffset-1,0)
				if curStyle==style:
					startOffset-=1
				else:
					break
			endOffset=offset+1
			while endOffset<lineEnd:
				curStyle=winUser.sendMessage(self.obj.windowHandle,SCI_GETSTYLEAT,endOffset,0)
				if curStyle==style:
					endOffset+=1
				else:
					break
		else:
			startOffset,endOffset=(self._startOffset,self._endOffset)
		formatField=textInfos.FormatField()
		if formatConfig["reportFontName"]:
			#To get font name, We need to allocate memory with in Scintilla's process, and then copy it out
			fontNameBuf=ctypes.create_string_buffer(32)
			internalBuf=winKernel.virtualAllocEx(self.obj.processHandle,None,len(fontNameBuf),winKernel.MEM_COMMIT,winKernel.PAGE_READWRITE)
			winUser.sendMessage(self.obj.windowHandle,SCI_STYLEGETFONT,style, internalBuf)
			winKernel.readProcessMemory(self.obj.processHandle,internalBuf,fontNameBuf,len(fontNameBuf),None)
			winKernel.virtualFreeEx(self.obj.processHandle,internalBuf,0,winKernel.MEM_RELEASE)
			formatField["font-name"]=fontNameBuf.value
		if formatConfig["reportFontSize"]:
			formatField["font-size"]="%spt"%winUser.sendMessage(self.obj.windowHandle,SCI_STYLEGETSIZE,style,0)
		if formatConfig["reportLineNumber"]:
			formatField["line-number"]=self._getLineNumFromOffset(offset)+1
		if formatConfig["reportFontAttributes"]:
			formatField["bold"]=bool(winUser.sendMessage(self.obj.windowHandle,SCI_STYLEGETBOLD,style,0))
			formatField["italic"]=bool(winUser.sendMessage(self.obj.windowHandle,SCI_STYLEGETITALIC,style,0))
			formatField["underline"]=bool(winUser.sendMessage(self.obj.windowHandle,SCI_STYLEGETUNDERLINE,style,0))
		return formatField,(startOffset,endOffset)

	def _getCaretOffset(self):
		return winUser.sendMessage(self.obj.windowHandle,SCI_GETCURRENTPOS,0,0)

	def _setCaretOffset(self,offset):
		winUser.sendMessage(self.obj.windowHandle,SCI_SETCURRENTPOS,offset,0)

	def _getSelectionOffsets(self):
		start=winUser.sendMessage(self.obj.windowHandle,SCI_GETSELECTIONSTART,0,0)
		end=winUser.sendMessage(self.obj.windowHandle,SCI_GETSELECTIONEND,0,0)
		return (start,end)

	def _setSelectionOffsets(self,start,end):
		winUser.sendMessage(self.obj.windowHandle,SCI_SETSELECTIONSTART,start,0)
		winUser.sendMessage(self.obj.windowHandle,SCI_SETSELECTIONEND,end,0)

	def _getStoryText(self):
		if not hasattr(self,'_storyText'):
			storyLength=self._getStoryLength()
			self._storyText=self._getTextRange(0,storyLength)
		return self._storyText

	def _getStoryLength(self):
		if not hasattr(self,'_storyLength'):
			self._storyLength=winUser.sendMessage(self.obj.windowHandle,SCI_GETTEXTLENGTH,0,0)
		return self._storyLength

	def _getLineCount(self):
		return winUser.sendMessage(self.obj.windowHandle,SCI_GETLINECOUNT,0,0)

	def _getTextRange(self,start,end):
		bufLen=(end-start)+1
		textRange=TextRangeStruct()
		textRange.chrg.cpMin=start
		textRange.chrg.cpMax=end
		processHandle=self.obj.processHandle
		internalBuf=winKernel.virtualAllocEx(processHandle,None,bufLen,winKernel.MEM_COMMIT,winKernel.PAGE_READWRITE)
		textRange.lpstrText=internalBuf
		internalTextRange=winKernel.virtualAllocEx(processHandle,None,ctypes.sizeof(textRange),winKernel.MEM_COMMIT,winKernel.PAGE_READWRITE)
		winKernel.writeProcessMemory(processHandle,internalTextRange,ctypes.byref(textRange),ctypes.sizeof(textRange),None)
		winUser.sendMessage(self.obj.windowHandle,SCI_GETTEXTRANGE,0,internalTextRange)
		winKernel.virtualFreeEx(processHandle,internalTextRange,0,winKernel.MEM_RELEASE)
		buf=ctypes.create_string_buffer(bufLen)
		winKernel.readProcessMemory(processHandle,internalBuf,buf,bufLen,None)
		winKernel.virtualFreeEx(processHandle,internalBuf,0,winKernel.MEM_RELEASE)
		cp=winUser.sendMessage(self.obj.windowHandle,SCI_GETCODEPAGE,0,0)
		if cp==SC_CP_UTF8:
			return unicode(buf.value, errors="replace", encoding="utf-8")
		else:
			return unicode(buf.value, errors="replace", encoding=locale.getlocale()[1])

	def _getWordOffsets(self,offset):
		start=winUser.sendMessage(self.obj.windowHandle,SCI_WORDSTARTPOSITION,offset,0)
		end=winUser.sendMessage(self.obj.windowHandle,SCI_WORDENDPOSITION,start,0)
		if end<=offset:
			start=end
			end=winUser.sendMessage(self.obj.windowHandle,SCI_WORDENDPOSITION,offset,0)
		return [start,end]

	def _getLineNumFromOffset(self,offset):
		return winUser.sendMessage(self.obj.windowHandle,SCI_LINEFROMPOSITION,offset,0)

	def _getLineOffsets(self,offset):
		curY=winUser.sendMessage(self.obj.windowHandle,SCI_POINTYFROMPOSITION,0,offset)
		start=winUser.sendMessage(self.obj.windowHandle,SCI_POSITIONFROMPOINT,0,curY)
		end=winUser.sendMessage(self.obj.windowHandle,SCI_POSITIONFROMPOINT,0xffff,curY)
		limit=self._getStoryLength()
		while winUser.sendMessage(self.obj.windowHandle,SCI_POINTYFROMPOSITION,0,end)==curY and end<limit:
 			end+=1
		return (start,end)

	def _getParagraphOffsets(self,offset):
		return self._getLineOffsets(offset)

	def _getCharacterOffsets(self,offset):
		return [offset,winUser.sendMessage(self.obj.windowHandle,SCI_POSITIONAFTER,offset,0)]

#The Scintilla NVDA object, inherists the generic MSAA NVDA object
class Scintilla(Window):

	TextInfo=ScintillaTextInfo

#The name of the object is gotten by the standard way of getting a window name, can't use MSAA name (since it contains all the text)
	def _get_name(self):
		return winUser.getWindowText(self.windowHandle)

#The role of the object should be editable text
	def _get_role(self):
		return controlTypes.ROLE_EDITABLETEXT

	def _get_states(self):
		states = super(Scintilla, self)._get_states()
		# Scintilla controls are always multiline.
		states.add(controlTypes.STATE_MULTILINE)
		return states

#We want all the standard text editing key commands to be handled by NVDA
[Scintilla.bindKey(keyName,scriptName) for keyName,scriptName in [
	("ExtendedUp","moveByLine"),
	("ExtendedDown","moveByLine"),
	("ExtendedLeft","moveByCharacter"),
	("ExtendedRight","moveByCharacter"),
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
	("ExtendedDelete","delete"),
	("Back","backspace"),
]]
