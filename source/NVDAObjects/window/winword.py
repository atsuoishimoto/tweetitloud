#appModules/winword.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import ctypes
import comtypes.client
import comtypes.automation
import winUser
import globalVars
import speech
from keyUtils import sendKey, key
import config
import textInfos
import textInfos.offsets
import controlTypes
from . import Window
 
#Word constants

#Indexing
wdActiveEndAdjustedPageNumber=1
wdActiveEndPageNumber=3
wdNumberOfPagesInDocument=4
wdFirstCharacterLineNumber=10
wdWithInTable=12
wdStartOfRangeRowNumber=13
wdMaximumNumberOfRows=15
wdStartOfRangeColumnNumber=16
wdMaximumNumberOfColumns=18
#Horizontal alignment
wdAlignParagraphLeft=0
wdAlignParagraphCenter=1
wdAlignParagraphRight=2
wdAlignParagraphJustify=3
#Units
wdCharacter=1
wdWord=2
wdSentence=3
wdParagraph=4
wdLine=5
wdStory=6
wdColumn=9
wdRow=10
wdWindow=11
wdCell=12
wdCharFormat=13
wdParaFormat=14
wdTable=15
#GoTo - direction
wdGoToAbsolute=1
wdGoToRelative=2
wdGoToNext=2
#GoTo - units
wdGoToPage=1
wdGoToLine=3

NVDAUnitsToWordUnits={
	textInfos.UNIT_CHARACTER:wdCharacter,
	textInfos.UNIT_WORD:wdWord,
	textInfos.UNIT_LINE:wdLine,
	textInfos.UNIT_SENTENCE:wdSentence,
	textInfos.UNIT_PARAGRAPH:wdParagraph,
	textInfos.UNIT_TABLE:wdTable,
	textInfos.UNIT_CELL:wdCell,
	textInfos.UNIT_ROW:wdRow,
	textInfos.UNIT_COLUMN:wdColumn,
	textInfos.UNIT_STORY:wdStory,
	textInfos.UNIT_READINGCHUNK:wdSentence,
}

class WordDocumentTextInfo(textInfos.TextInfo):

	def _moveInTable(self,c=0,r=0):
		try:
			cell=self._rangeObj.cells[1]
		except:
			return False
		try:
			columnIndex=cell.columnIndex
			rowIndex=cell.rowIndex
		except:
			return False
		if columnIndex==1 and c<0:
			return False
		if rowIndex==1 and r<0:
			return False
		try:
			self._rangeObj=self._rangeObj.tables[1].columns[columnIndex+c].cells[rowIndex+r].range
		except:
			return False
		return True





	def _expandToLine(self,rangeObj):
		sel=self.obj.WinwordSelectionObject
		oldSel=sel.range
		sel.SetRange(rangeObj.start,rangeObj.end)
		sel.Expand(wdLine)
		rangeObj.SetRange(sel.Start,sel.End)
		sel.SetRange(oldSel.Start,oldSel.End)

	def _getFormatFieldAtRange(self,range,formatConfig):
		formatField=textInfos.FormatField()
		fontObj=None
		paraFormatObj=None
		if formatConfig["reportSpellingErrors"] and range.spellingErrors.count>0: 
			formatField["invalid-spelling"]=True
		if formatConfig["reportLineNumber"]:
			formatField["line-number"]=range.Information(wdFirstCharacterLineNumber)
		if formatConfig["reportPage"]:
			formatField["page-number"]=range.Information(wdActiveEndAdjustedPageNumber)
		if formatConfig["reportStyle"]:
			formatField["style"]=range.style.nameLocal
		if formatConfig["reportTables"] and range.Information(wdWithInTable):
			tableInfo={}
			tableInfo["column-count"]=range.Information(wdMaximumNumberOfColumns)
			tableInfo["row-count"]=range.Information(wdMaximumNumberOfRows)
			tableInfo["column-number"]=range.Information(wdStartOfRangeColumnNumber)
			tableInfo["row-number"]=range.Information(wdStartOfRangeRowNumber)
			formatField["table-info"]=tableInfo
		if formatConfig["reportAlignment"]:
			if not paraFormatObj: paraFormatObj=range.paragraphFormat
			alignment=paraFormatObj.alignment
			if alignment==wdAlignParagraphLeft:
				formatField["text-align"]="left"
			elif alignment==wdAlignParagraphCenter:
				formatField["text-align"]="center"
			elif alignment==wdAlignParagraphRight:
				formatField["text-align"]="right"
			elif alignment==wdAlignParagraphJustify:
				formatField["text-align"]="justify"
		if formatConfig["reportFontName"]:
			if not fontObj: fontObj=range.font
			formatField["font-name"]=fontObj.name
		if formatConfig["reportFontSize"]:
			if not fontObj: fontObj=range.font
			formatField["font-size"]="%spt"%fontObj.size
		if formatConfig["reportFontAttributes"]:
			if not fontObj: fontObj=range.font
			formatField["bold"]=bool(fontObj.bold)
			formatField["italic"]=bool(fontObj.italic)
			formatField["underline"]=bool(fontObj.underline)
			if fontObj.superscript:
				formatField["text-position"]="super"
			elif fontObj.subscript:
				formatField["text-position"]="sub"
		return formatField

	def _expandFormatRange(self,range):
		startLimit=self._rangeObj.start
		endLimit=self._rangeObj.end
		#Only Office 2007 onwards supports moving by format changes, -- and only moveEnd works.
		try:
			range.MoveEnd(13,1)
		except:
			range.Expand(wdWord)
		if range.start<startLimit:
			range.start=startLimit
		if range.end>endLimit:
			range.end=endLimit

	def __init__(self,obj,position,_rangeObj=None):
		super(WordDocumentTextInfo,self).__init__(obj,position)
		if _rangeObj:
			self._rangeObj=_rangeObj.Duplicate
			return
		if isinstance(position,textInfos.Point):
			self._rangeObj=self.obj.WinwordDocumentObject.application.activeWindow.RangeFromPoint(position.x,position.y)
		elif position==textInfos.POSITION_SELECTION:
			self._rangeObj=self.obj.WinwordSelectionObject.range
		elif position==textInfos.POSITION_CARET:
			self._rangeObj=self.obj.WinwordSelectionObject.range
			self._rangeObj.Collapse()
		elif position==textInfos.POSITION_ALL:
			self._rangeObj=self.obj.WinwordSelectionObject.range
			self._rangeObj.Expand(wdStory)
		elif position==textInfos.POSITION_FIRST:
			self._rangeObj=self.obj.WinwordSelectionObject.range
			self._rangeObj.SetRange(0,0)
		elif position==textInfos.POSITION_LAST:
			self._rangeObj=self.obj.WinwordSelectionObject.range
			self._rangeObj.moveEnd(wdStory,1)
			self._rangeObj.move(wdCharacter,-1)
		elif isinstance(position,textInfos.offsets.Offsets):
			self._rangeObj=self.obj.WinwordSelectionObject.range
			self._rangeObj.SetRange(position.startOffset,position.endOffset)
		else:
			raise NotImplementedError("position: %s"%position)

	def getTextWithFields(self,formatConfig=None):
		if not formatConfig:
			formatConfig=config.conf["documentFormatting"]
		range=self._rangeObj.duplicate
		range.Collapse()
		if not formatConfig["detectFormatAfterCursor"]:
			range.expand(wdCharacter)
			field=textInfos.FieldCommand("formatChange",self._getFormatFieldAtRange(range,formatConfig))
			return [field,self.text]
		commandList=[]
		endLimit=self._rangeObj.end
		range=self._rangeObj.duplicate
		range.Collapse()
		while range.end<endLimit:
			self._expandFormatRange(range)
			commandList.append(textInfos.FieldCommand("formatChange",self._getFormatFieldAtRange(range,formatConfig)))
			commandList.append(range.text)
			end=range.end
			range.start=end
			#Trying to set the start past the end of the document forces both start and end back to the previous offset, so catch this
			if range.end<end:
				break
		return commandList

	def expand(self,unit):
		if unit==textInfos.UNIT_LINE and self.basePosition not in (textInfos.POSITION_CARET,textInfos.POSITION_SELECTION):
			unit=textInfos.UNIT_SENTENCE
		if unit==textInfos.UNIT_LINE:
			self._expandToLine(self._rangeObj)
		elif unit==textInfos.UNIT_CHARACTER:
			self._rangeObj.moveEnd(wdCharacter,1)
		elif unit in NVDAUnitsToWordUnits:
			self._rangeObj.Expand(NVDAUnitsToWordUnits[unit])
		else:
			raise NotImplementedError("unit: %s"%unit)

	def compareEndPoints(self,other,which):
		if which=="startToStart":
			diff=self._rangeObj.Start-other._rangeObj.Start
		elif which=="startToEnd":
			diff=self._rangeObj.Start-other._rangeObj.End
		elif which=="endToStart":
			diff=self._rangeObj.End-other._rangeObj.Start
		elif which=="endToEnd":
			diff=self._rangeObj.End-other._rangeObj.End
		else:
			raise ValueError("bad argument - which: %s"%which)
		if diff<0:
			diff=-1
		elif diff>0:
			diff=1
		return diff

	def setEndPoint(self,other,which):
		if which=="startToStart":
			self._rangeObj.Start=other._rangeObj.Start
		elif which=="startToEnd":
			self._rangeObj.Start=other._rangeObj.End
		elif which=="endToStart":
			self._rangeObj.End=other._rangeObj.Start
		elif which=="endToEnd":
			self._rangeObj.End=other._rangeObj.End
		else:
			raise ValueError("bad argument - which: %s"%which)

	def _get_isCollapsed(self):
		if self._rangeObj.Start==self._rangeObj.End:
			return True
		else:
			return False

	def collapse(self,end=False):
		a=self._rangeObj.Start
		b=self._rangeObj.end
		startOffset=min(a,b)
		endOffset=max(a,b)
		if not end:
			offset=startOffset
		else:
			offset=endOffset
		self._rangeObj.SetRange(offset,offset)

	def copy(self):
		return WordDocumentTextInfo(self.obj,None,_rangeObj=self._rangeObj)

	def _get_text(self):
		text=self._rangeObj.text
		if not text:
			text=""
		return text

	def move(self,unit,direction,endPoint=None):
		if unit==textInfos.UNIT_LINE:
			unit=textInfos.UNIT_SENTENCE
		if unit in NVDAUnitsToWordUnits:
			unit=NVDAUnitsToWordUnits[unit]
		else:
			raise NotImplementedError("unit: %s"%unit)
		if endPoint=="start":
			moveFunc=self._rangeObj.MoveStart
		elif endPoint=="end":
			moveFunc=self._rangeObj.MoveEnd
		else:
			moveFunc=self._rangeObj.Move
		res=moveFunc(unit,direction)
		return res

	def _get_bookmark(self):
		return textInfos.offsets.Offsets(self._rangeObj.Start,self._rangeObj.End)

	def updateCaret(self):
		self.obj.WinwordSelectionObject.SetRange(self._rangeObj.Start,self._rangeObj.Start)

	def updateSelection(self):
		self.obj.WinwordSelectionObject.SetRange(self._rangeObj.Start,self._rangeObj.End)

class WordDocument(Window):

	TextInfo=WordDocumentTextInfo

	def __init__(self,*args,**kwargs):
		super(WordDocument,self).__init__(*args,**kwargs)

	def _get_role(self):
		return controlTypes.ROLE_EDITABLETEXT

	def _get_WinwordDocumentObject(self):
		if not hasattr(self,'_WinwordDocumentObject'): 
			ptr=ctypes.POINTER(comtypes.automation.IDispatch)()
			if ctypes.windll.oleacc.AccessibleObjectFromWindow(self.windowHandle,winUser.OBJID_NATIVEOM,ctypes.byref(comtypes.automation.IDispatch._iid_),ctypes.byref(ptr))!=0:
				raise OSError("No native object model")
			self._WinwordDocumentObject=comtypes.client.dynamic.Dispatch(ptr)
 		return self._WinwordDocumentObject

	def _get_WinwordSelectionObject(self):
		if not hasattr(self,'_WinwordSelectionObject'):
			self._WinwordSelectionObject=self.WinwordDocumentObject.selection
		return self._WinwordSelectionObject

	def script_nextRow(self,keyPress):
		info=self.makeTextInfo("caret")
		if not info._rangeObj.Information(wdWithInTable):
 			speech.speakMessage(_("not in table"))
		if info._moveInTable(0,1):
			info.updateCaret()
			info.expand(textInfos.UNIT_CELL)
			speech.speakTextInfo(info,reason=speech.REASON_CARET)
		else:
			speech.speakMessage("edge of table")

	def script_previousRow(self,keyPress):
		info=self.makeTextInfo("caret")
		if not info._rangeObj.Information(wdWithInTable):
 			speech.speakMessage(_("not in table"))
		if info._moveInTable(0,-1):
			info.updateCaret()
			info.expand(textInfos.UNIT_CELL)
			speech.speakTextInfo(info,reason=speech.REASON_CARET)
		else:
			speech.speakMessage("edge of table")

	def script_nextColumn(self,keyPress):
		info=self.makeTextInfo("caret")
		if not info._rangeObj.Information(wdWithInTable):
 			speech.speakMessage(_("not in table"))
		if info._moveInTable(1,0):
			info.updateCaret()
			info.expand(textInfos.UNIT_CELL)
			speech.speakTextInfo(info,reason=speech.REASON_CARET)
		else:
			speech.speakMessage("edge of table")

	def script_previousColumn(self,keyPress):
		info=self.makeTextInfo("caret")
		if not info._rangeObj.Information(wdWithInTable):
 			speech.speakMessage(_("not in table"))
		if info._moveInTable(-1,0):
			info.updateCaret()
			info.expand(textInfos.UNIT_CELL)
			speech.speakTextInfo(info,reason=speech.REASON_CARET)
		else:
			speech.speakMessage("edge of table")

[WordDocument.bindKey(keyName,scriptName) for keyName,scriptName in [
	("ExtendedUp","moveByLine"),
	("ExtendedDown","moveByLine"),
	("ExtendedLeft","moveByCharacter"),
	("ExtendedRight","moveByCharacter"),
	("Control+ExtendedLeft","moveByWord"),
	("Control+ExtendedRight","moveByWord"),
	("Shift+ExtendedRight","changeSelection"),
	("control+extendedDown","moveByParagraph"),
	("control+extendedUp","moveByParagraph"),
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
	("control+alt+extendedUp","previousRow"),
	("control+alt+extendedDown","nextRow"),
	("control+alt+extendedLeft","previousColumn"),
	("control+alt+extendedRight","nextColumn"),
	("ExtendedPrior","moveByLine"),
	("ExtendedNext","moveByLine"),
	("Control+ExtendedPrior","moveByLine"),
	("Control+ExtendedNext","moveByLine"),
]]

