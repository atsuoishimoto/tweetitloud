#cursorManager.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2008 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

"""
Implementation of cursor managers.
A cursor manager provides caret navigation and selection commands for a virtual text range.
"""

import baseObject
import gui.scriptUI
import textInfos
import api
import speech
import config
import braille

class CursorManager(baseObject.ScriptableObject):
	"""
	A mix-in providing caret navigation and selection commands for the object's virtual text range.
	This is required where a text range is not linked to a physical control and thus does not provide commands to move the cursor, select and copy text, etc.
	This base cursor manager requires that the text range being used stores its own caret and selection information.

	This is a mix-in class; i.e. it should be inherited alongside another L{baseObject.ScriptableObject}.
	The class into which it is inherited must provide a C{makeTextInfo(position)} method.

	@ivar selection: The current caret/selection range.
	@type selection: L{textInfos.TextInfo}
	"""

	_lastFindText=""

	def __init__(self, *args, **kwargs):
		super(CursorManager, self).__init__(*args, **kwargs)
		self.initCursorManager()

	def initOverlayClass(self):
		"""Performs automatic initialisation if this is being used as an overlay class."""
		self.initCursorManager()

	def initCursorManager(self):
		"""Initialise this cursor manager.
		This must be called before the cursor manager functionality can be used.
		It is normally called by L{__init__} or L{initOverlayClass}.
		"""
		self._lastSelectionMovedStart=False

	def _get_selection(self):
		return self.makeTextInfo(textInfos.POSITION_SELECTION)

	def _set_selection(self, info):
		info.updateSelection()
		braille.handler.handleCaretMove(self)

	def _caretMovementScriptHelper(self,unit,direction=None,posConstant=textInfos.POSITION_SELECTION,posUnit=None,posUnitEnd=False,extraDetail=False,handleSymbols=False):
		oldInfo=self.makeTextInfo(posConstant)
		info=oldInfo.copy()
		info.collapse(end=not self._lastSelectionMovedStart)
		if not self._lastSelectionMovedStart and not oldInfo.isCollapsed:
			info.move(textInfos.UNIT_CHARACTER,-1)
		if posUnit is not None:
			info.expand(posUnit)
			info.collapse(end=posUnitEnd)
			if posUnitEnd:
				info.move(textInfos.UNIT_CHARACTER,-1)
		if direction is not None:
			info.expand(unit)
			info.collapse(end=posUnitEnd)
			info.move(unit,direction)
		self.selection=info
		info.expand(unit)
		speech.speakTextInfo(info,unit=unit,reason=speech.REASON_CARET)
		if not oldInfo.isCollapsed:
			speech.speakSelectionChange(oldInfo,self.selection)

	def doFindTextDialog(self):
		findDialog=gui.scriptUI.TextEntryDialog(_("Type the text you wish to find"),title=_("Find"),default=self._lastFindText,callback=self.doFindText)
		findDialog.run()

	def doFindText(self,text,reverse=False):
		if not text:
			return
		info=self.makeTextInfo(textInfos.POSITION_CARET)
		res=info.find(text,reverse=reverse)
		if res:
			self.selection=info
			speech.cancelSpeech()
			info.move(textInfos.UNIT_LINE,1,endPoint="end")
			speech.speakTextInfo(info,reason=speech.REASON_CARET)
		else:
			errorDialog=gui.scriptUI.MessageDialog(_("text \"%s\" not found")%text,title=_("Find Error"),style=gui.scriptUI.wx.OK|gui.scriptUI.wx.ICON_ERROR)
			errorDialog.run()
		CursorManager._lastFindText=text

	def script_find(self,gesture): 
		self.doFindTextDialog()
	script_find.__doc__ = _("find a text string from the current cursor position")

	def script_findNext(self,gesture):
		if not self._lastFindText:
			self.doFindTextDialog()
			return
		self.doFindText(self._lastFindText)
	script_findNext.__doc__ = _("find the next occurrence of the previously entered text string from the current cursor's position")

	def script_findPrevious(self,gesture):
		if not self._lastFindText:
			self.doFindTextDialog()
			return
		self.doFindText(self._lastFindText,reverse=True)
	script_findPrevious.__doc__ = _("find the previous occurrence of the previously entered text string from the current cursor's position")

	def script_moveByPage_back(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,-config.conf["virtualBuffers"]["linesPerPage"],extraDetail=False)

	def script_moveByPage_forward(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,config.conf["virtualBuffers"]["linesPerPage"],extraDetail=False)

	def script_moveByCharacter_back(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_CHARACTER,-1,extraDetail=True,handleSymbols=True)

	def script_moveByCharacter_forward(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_CHARACTER,1,extraDetail=True,handleSymbols=True)

	def script_moveByWord_back(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_WORD,-1,extraDetail=True,handleSymbols=True)

	def script_moveByWord_forward(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_WORD,1,extraDetail=True,handleSymbols=True)

	def script_moveByLine_back(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,-1)

	def script_moveByLine_forward(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,1)

	def script_moveByParagraph_back(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_PARAGRAPH,-1)

	def script_moveByParagraph_forward(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_PARAGRAPH,1)

	def script_startOfLine(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_CHARACTER,posUnit=textInfos.UNIT_LINE,extraDetail=True,handleSymbols=True)

	def script_endOfLine(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_CHARACTER,posUnit=textInfos.UNIT_LINE,posUnitEnd=True,extraDetail=True,handleSymbols=True)

	def script_topOfDocument(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,posConstant=textInfos.POSITION_FIRST)

	def script_bottomOfDocument(self,gesture):
		self._caretMovementScriptHelper(textInfos.UNIT_LINE,posConstant=textInfos.POSITION_LAST)

	def _selectionMovementScriptHelper(self,unit=None,direction=None,toPosition=None):
		oldInfo=self.makeTextInfo(textInfos.POSITION_SELECTION)
		if toPosition:
			newInfo=self.makeTextInfo(toPosition)
			if newInfo.compareEndPoints(oldInfo,"startToStart")>0:
				newInfo.setEndPoint(oldInfo,"startToStart")
			if newInfo.compareEndPoints(oldInfo,"endToEnd")<0:
				newInfo.setEndPoint(oldInfo,"endToEnd")
		elif unit:
			newInfo=oldInfo.copy()
		if unit:
			if self._lastSelectionMovedStart:
				newInfo.move(unit,direction,endPoint="start")
			else:
				newInfo.move(unit,direction,endPoint="end")
		self.selection = newInfo
		if newInfo.compareEndPoints(oldInfo,"startToStart")!=0:
			self._lastSelectionMovedStart=True
		else:
			self._lastSelectionMovedStart=False
		if newInfo.compareEndPoints(oldInfo,"endToEnd")!=0:
			self._lastSelectionMovedStart=False
		speech.speakSelectionChange(oldInfo,newInfo)

	def script_selectCharacter_forward(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_CHARACTER,direction=1)

	def script_selectCharacter_back(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_CHARACTER,direction=-1)

	def script_selectWord_forward(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_WORD,direction=1)

	def script_selectWord_back(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_WORD,direction=-1)

	def script_selectLine_forward(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=1)

	def script_selectLine_back(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=-1)

	def script_selectPage_forward(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=config.conf["virtualBuffers"]["linesPerPage"])

	def script_selectPage_back(self,gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=-config.conf["virtualBuffers"]["linesPerPage"])

	def script_selectParagraph_forward(self, gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_PARAGRAPH, direction=1)

	def script_selectParagraph_back(self, gesture):
		self._selectionMovementScriptHelper(unit=textInfos.UNIT_PARAGRAPH, direction=-1)

	def script_selectToBeginningOfLine(self,gesture):
		curInfo=self.makeTextInfo(textInfos.POSITION_SELECTION)
		curInfo.collapse()
		tempInfo=curInfo.copy()
		tempInfo.expand(textInfos.UNIT_LINE)
		if curInfo.compareEndPoints(tempInfo,"startToStart")>0:
			self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=-1)

	def script_selectToEndOfLine(self,gesture):
		curInfo=self.makeTextInfo(textInfos.POSITION_SELECTION)
		curInfo.collapse()
		tempInfo=curInfo.copy()
		curInfo.expand(textInfos.UNIT_CHARACTER)
		tempInfo.expand(textInfos.UNIT_LINE)
		if curInfo.compareEndPoints(tempInfo,"endToEnd")<0:
			self._selectionMovementScriptHelper(unit=textInfos.UNIT_LINE,direction=1)

	def script_selectToTopOfDocument(self,gesture):
		self._selectionMovementScriptHelper(toPosition=textInfos.POSITION_FIRST)

	def script_selectToBottomOfDocument(self,gesture):
		self._selectionMovementScriptHelper(toPosition=textInfos.POSITION_LAST,unit=textInfos.UNIT_CHARACTER,direction=1)

	def script_selectAll(self,gesture):
		self._selectionMovementScriptHelper(toPosition=textInfos.POSITION_ALL)

	def script_copyToClipboard(self,gesture):
		info=self.makeTextInfo(textInfos.POSITION_SELECTION)
		if info.isCollapsed:
			speech.speakMessage(_("no selection"))
			return
		if info.copyToClipboard():
			speech.speakMessage(_("copied to clipboard"))

	__gestures = {
		"kb:pageUp": "moveByPage_back",
		"kb:pageDown": "moveByPage_forward",
		"kb:upArrow": "moveByLine_back",
		"kb:downArrow": "moveByLine_forward",
		"kb:leftArrow": "moveByCharacter_back",
		"kb:rightArrow": "moveByCharacter_forward",
		"kb:control+leftArrow": "moveByWord_back",
		"kb:control+rightArrow": "moveByWord_forward",
		"kb:control+upArrow": "moveByParagraph_back",
		"kb:control+downArrow": "moveByParagraph_forward",
		"kb:home": "startOfLine",
		"kb:end": "endOfLine",
		"kb:control+home": "topOfDocument",
		"kb:control+end": "bottomOfDocument",
		"kb:shift+rightArrow": "selectCharacter_forward",
		"kb:shift+leftArrow": "selectCharacter_back",
		"kb:shift+control+rightArrow": "selectWord_forward",
		"kb:shift+control+leftArrow": "selectWord_back",
		"kb:shift+downArrow": "selectLine_forward",
		"kb:shift+upArrow": "selectLine_back",
		"kb:shift+pageDown": "selectPage_forward",
		"kb:shift+pageUp": "selectPage_back",
		"kb:shift+control+downArrow": "selectParagraph_forward",
		"kb:shift+control+upArrow": "selectParagraph_back",
		"kb:shift+end": "selectToEndOfLine",
		"kb:shift+home": "selectToBeginningOfLine",
		"kb:shift+control+end": "selectToBottomOfDocument",
		"kb:shift+control+home": "selectToTopOfDocument",
		"kb:control+a": "selectAll",
		"kb:control+c": "copyToClipboard",
		"kb:NVDA+Control+f": "find",
		"kb:NVDA+f3": "findNext",
		"kb:NVDA+shift+f3": "findPrevious",
	}

class _ReviewCursorManagerTextInfo(textInfos.TextInfo):
	"""For use with L{ReviewCursorManager}.
	Overrides L{updateCaret} and L{updateSelection} to use the selection property on the underlying object.
	"""

	def updateCaret(self):
		self.obj.selection = self

	def updateSelection(self):
		self.obj.selection = self

class ReviewCursorManager(CursorManager):
	"""
	A cursor manager used for review.
	This cursor manager maintains its own caret and selection information.
	Thus, the underlying text range need not support updating the caret or selection.
	"""

	def initCursorManager(self):
		super(ReviewCursorManager, self).initCursorManager()
		realTI = self.TextInfo
		self.TextInfo = type("ReviewCursorManager_%s" % realTI.__name__, (_ReviewCursorManagerTextInfo, realTI), {})
		self._selection = self.makeTextInfo(textInfos.POSITION_FIRST)

	def makeTextInfo(self, position):
		if position == textInfos.POSITION_SELECTION:
			return self.selection
		elif position == textInfos.POSITION_CARET:
			sel = self.selection
			sel.collapse()
			return sel
		return super(ReviewCursorManager, self).makeTextInfo(position)

	def _get_selection(self):
		return self._selection.copy()

	def _set_selection(self, info):
		self._selection = info.copy()
		braille.handler.handleCaretMove(self)
