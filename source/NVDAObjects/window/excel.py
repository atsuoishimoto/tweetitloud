#NVDAObjects/excel.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2007 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

import time
import re
import ctypes
from comtypes import COMError
import comtypes.automation
import wx
import oleacc
import textInfos.offsets
import eventHandler
import gui
import gui.scriptUI
import winUser
import controlTypes
import speech
from . import Window
from .. import NVDAObjectTextInfo
import appModuleHandler
from logHandler import log

re_dollaredAddress=re.compile(r"^\$?([a-zA-Z]+)\$?([0-9]+)")

class CellEditDialog(gui.scriptUI.ModalDialog):

	def __init__(self,cell):
		super(CellEditDialog,self).__init__(None)
		self._cell=cell

	def onCellTextChar(self,evt):
		if evt.GetKeyCode() == wx.WXK_RETURN:
			if evt.AltDown():
				i=self._cellText.GetInsertionPoint()
				self._cellText.Replace(i,i,"\n")
			else:
				self.onOk(None)
			return
		evt.Skip(True)

	def onOk(self,evt):
		self._cell.formulaLocal=self._cellText.GetValue()
		self.dialog.EndModal(wx.ID_OK)

	def makeDialog(self):
		d=wx.Dialog(gui.mainFrame, wx.ID_ANY, title=_("NVDA Excel Cell Editor"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		mainSizer.Add(wx.StaticText(d,wx.ID_ANY, label=_("Enter cell contents")))
		self._cellText=wx.TextCtrl(d, wx.ID_ANY, size=(300, 200), style=wx.TE_RICH|wx.TE_MULTILINE)
		self._cellText.Bind(wx.EVT_KEY_DOWN, self.onCellTextChar)
		self._cellText.SetValue(self._cell.formulaLocal)
		mainSizer.Add(self._cellText)
		mainSizer.Add(d.CreateButtonSizer(wx.OK|wx.CANCEL))
		d.Bind(wx.EVT_BUTTON,self.onOk,id=wx.ID_OK)
		d.SetSizer(mainSizer)
		self._cellText.SetFocus()
		return d

class ExcelWindow(Window):
	"""A base that all Excel NVDAObjects inherit from, which contains some useful static methods."""

	@staticmethod
	def excelWindowObjectFromWindow(windowHandle):
		try:
			pDispatch=oleacc.AccessibleObjectFromWindow(windowHandle,winUser.OBJID_NATIVEOM,interface=comtypes.automation.IDispatch)
		except (COMError,WindowsError):
			return None
		return comtypes.client.dynamic.Dispatch(pDispatch)

	@staticmethod
	def getCellAddress(cell):
		return re_dollaredAddress.sub(r"\1\2",cell.Address())

class Excel7Window(ExcelWindow):
	"""An overlay class for Window for the EXCEL7 window class, which simply bounces focus to the active excel cell."""

	def _get_excelWindowObject(self):
		return self.excelWindowObjectFromWindow(self.windowHandle)

	def event_gainFocus(self):
		selection=self.excelWindowObject.Selection
		if selection.Count>1:
			obj=ExcelSelection(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelRangeObject=selection)
		else:
			obj=ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=selection)
		eventHandler.executeEvent("gainFocus",obj)

class ExcelWorksheet(ExcelWindow):

	role=controlTypes.ROLE_TABLE

	def __init__(self,windowHandle=None,excelWindowObject=None,excelWorksheetObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelWorksheetObject=excelWorksheetObject
		super(ExcelWorksheet,self).__init__(windowHandle=windowHandle)
		self.initOverlayClass()

	def _get_name(self):
		return self.excelWorksheetObject.name

	def _get_firstChild(self):
		cell=self.excelWorksheetObject.cells(1,1)
		return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=cell)

	def script_changeSelection(self,gesture):
		gesture.send()
		selection=self.excelWindowObject.Selection
		if selection.Count>1:
			obj=ExcelSelection(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelRangeObject=selection)
		else:
			obj=ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=selection)
		eventHandler.executeEvent("gainFocus",obj)
	script_changeSelection.__doc__=_("Extends the selection and speaks the last selected cell")
	script_changeSelection.canPropagate=True

	__changeSelectionGestures = (
		"kb:tab",
		"kb:shift+tab",
		"kb:upArrow",
		"kb:downArrow",
		"kb:leftArrow",
		"kb:rightArrow",
		"kb:control+upArrow",
		"kb:control+downArrow",
		"kb:control+leftArrow",
		"kb:control+rightArrow",
		"kb:home",
		"kb:end",
		"kb:control+home",
		"kb:control+end",
		"kb:shift+upArrow",
		"kb:shift+downArrow",
		"kb:shift+leftArrow",
		"kb:shift+rightArrow",
		"kb:shift+control+upArrow",
		"kb:shift+control+downArrow",
		"kb:shift+control+leftArrow",
		"kb:shift+control+rightArrow",
		"kb:shift+home",
		"kb:shift+end",
		"kb:shift+control+home",
		"kb:shift+control+end",
		"kb:shift+space",
		"kb:control+space",
	)

	def initOverlayClass(self):
		for gesture in self.__changeSelectionGestures:
			self.bindGesture(gesture, "changeSelection")

class ExcelCellTextInfo(NVDAObjectTextInfo):

	def _getFormatFieldAndOffsets(self,offset,formatConfig,calculateOffsets=True):
		formatField=textInfos.FormatField()
		fontObj=self.obj.excelCellObject.font
		if formatConfig['reportFontName']:
			formatField['font-name']=fontObj.name
		if formatConfig['reportFontSize']:
			formatField['font-size']=str(fontObj.size)
		if formatConfig['reportFontAttributes']:
			formatField['bold']=fontObj.bold
			formatField['italic']=fontObj.italic
			formatField['underline']=fontObj.underline
		return formatField,(self._startOffset,self._endOffset)

class ExcelCell(ExcelWindow):

	@classmethod
	def kwargsFromSuper(cls,kwargs,relation=None):
		windowHandle=kwargs['windowHandle']
		excelWindowObject=cls.excelWindowObjectFromWindow(windowHandle)
		if not excelWindowObject:
			return False
		if isinstance(relation,tuple):
			excelCellObject=excelWindowObject.rangeFromPoint(relation[0],relation[1])
		else:
			excelCellObject=excelWindowObject.ActiveCell
		if not excelCellObject:
			return False
		kwargs['excelWindowObject']=excelWindowObject
		kwargs['excelCellObject']=excelCellObject
		return True

	def __init__(self,windowHandle=None,excelWindowObject=None,excelCellObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelCellObject=excelCellObject
		super(ExcelCell,self).__init__(windowHandle=windowHandle)

	role=controlTypes.ROLE_TABLECELL

	TextInfo=ExcelCellTextInfo

	def _isEqual(self,other):
		if not super(ExcelCell,self)._isEqual(other):
			return False
		thisAddr=self.getCellAddress(self.excelCellObject)
		otherAddr=self.getCellAddress(other.excelCellObject)
		return thisAddr==otherAddr

	def _get_name(self):
		return self.getCellAddress(self.excelCellObject)

	def _get_value(self):
		return self.excelCellObject.Text

	def _get_description(self):
		return _("has formula") if self.excelCellObject.HasFormula else ""

	def _get_parent(self):
		worksheet=self.excelCellObject.Worksheet
		return ExcelWorksheet(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelWorksheetObject=worksheet)

	def _get_next(self):
		try:
			next=self.excelCellObject.next
		except COMError:
			next=None
		if next:
			return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=next)

	def _get_previous(self):
		try:
			previous=self.excelCellObject.previous
		except COMError:
			previous=None
		if previous:
			return ExcelCell(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelCellObject=previous)

	def script_editCell(self,gesture):
		cellEditDialog=CellEditDialog(self.excelWindowObject.ActiveCell)
		cellEditDialog.run()

	def initOverlayClass(self):
		self.bindGesture("kb:f2", "editCell")

class ExcelSelection(ExcelWindow):

	role=controlTypes.ROLE_GROUPING

	def __init__(self,windowHandle=None,excelWindowObject=None,excelRangeObject=None):
		self.excelWindowObject=excelWindowObject
		self.excelRangeObject=excelRangeObject
		super(ExcelSelection,self).__init__(windowHandle=windowHandle)

	def _get_name(self):
		return _("selection")

	def _get_value(self):
		firstCell=self.excelRangeObject.Item(1)
		lastCell=self.excelRangeObject.Item(self.excelRangeObject.Count)
		return _("%s %s through %s %s")%(self.getCellAddress(firstCell),firstCell.Text,self.getCellAddress(lastCell),lastCell.Text)

	def _get_parent(self):
		worksheet=self.excelRangeObject.Worksheet
		return ExcelWorksheet(windowHandle=self.windowHandle,excelWindowObject=self.excelWindowObject,excelWorksheetObject=worksheet)

