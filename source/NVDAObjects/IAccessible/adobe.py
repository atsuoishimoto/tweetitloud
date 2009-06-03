import eventHandler
import winUser
from . import IAccessible, getNVDAObjectFromEvent
from NVDAObjects import NVDAObjectTextInfo

class AcrobatNode(IAccessible):

	def _get_IAccessibleFocusEventNeedsFocusedState(self):
		#Acrobat document root objects do not have their focused state set when they have the focus.
		if self.event_childID==0:
			return False
		return super(AcrobatNode,self).IAccessibleFocusEventNeedsFocusedState

	def event_valueChange(self):
		if self.event_childID==0 and winUser.isDescendantWindow(winUser.getForegroundWindow(),self.windowHandle):
			# This page may die and be replaced by another with the same event params, so always grab a new one.
			obj = getNVDAObjectFromEvent(self.windowHandle, -4, 0)
			if not obj:
				return
			eventHandler.queueEvent("gainFocus",obj)

class AcrobatTextInfo(NVDAObjectTextInfo):

	def _getStoryText(self):
		return self.obj.value or ""

	def _getCaretOffset(self):
		caret = getNVDAObjectFromEvent(self.obj.windowHandle, winUser.OBJID_CARET, 0)
		if not caret:
			raise RuntimeError("No caret")
		try:
			return int(caret.description)
		except (ValueError, TypeError):
			raise RuntimeError("Bad caret index")

class AcrobatTextNode(AcrobatNode):
	TextInfo = AcrobatTextInfo

[AcrobatTextNode.bindKey(keyName,scriptName) for keyName,scriptName in [
	("ExtendedUp","moveByLine"),
	("ExtendedDown","moveByLine"),
	("ExtendedLeft","moveByCharacter"),
	("ExtendedRight","moveByCharacter"),
	("ExtendedPrior","moveByLine"),
	("ExtendedNext","moveByLine"),
	("Control+ExtendedLeft","moveByWord"),
	("Control+ExtendedRight","moveByWord"),
	("control+extendedDown","moveByParagraph"),
	("control+extendedUp","moveByParagraph"),
	("ExtendedHome","moveByCharacter"),
	("ExtendedEnd","moveByCharacter"),
	("control+extendedHome","moveByLine"),
	("control+extendedEnd","moveByLine"),
	("ExtendedDelete","delete"),
	("Back","backspace"),
]]

class AcrobatSDIWindowClient(IAccessible):

	def __init__(self, **kwargs):
		super(AcrobatSDIWindowClient, self).__init__(**kwargs)
		if not self.name and self.parent:
			# There are two client objects, one with a name and one without.
			# The unnamed object (probably manufactured by Acrobat) has broken next and previous relationships.
			# The unnamed object's parent is the named object, but when descending into the named object, the unnamed object is skipped.
			# Given the brokenness of the unnamed object, just skip it completely and use the parent when it is encountered.
			self.IAccessibleObject = self.IAccessibleObject.accParent
