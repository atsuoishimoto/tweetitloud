#braille.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2008-2011 James Teh <jamie@jantrid.net>, Michael Curran <mick@kulgan.net>

import itertools
import os
import pkgutil
import wx
import louis
import keyboardHandler
import baseObject
import config
from logHandler import log
import controlTypes
import api
import textInfos
import speech
import brailleDisplayDrivers
import inputCore

#: The directory in which liblouis braille tables are located.
TABLES_DIR = r"louis\tables"

#: The table filenames and descriptions.
TABLES = (
	("ar-ar-g1.utb", _("Arabic grade 1")),
	("bg.ctb", _("Bulgarian 8 dot computer braille")),
	("cy-cy-g1.utb", _("Welsh grade 1")),
	("cy-cy-g2.ctb", _("Welsh grade 2")),
	("cz-cz-g1.utb", _("Czech grade 1")),
	("da-dk-g1.utb", _("Danish grade 1")),
	("de-de-comp8.ctb", _("German 8 dot computer braille")),
	("de-de-g0.utb", _("German grade 0")),
	("de-de-g1.ctb", _("German grade 1")),
	("de-de-g2.ctb", _("German grade 2")),
	("en-gb-g1.utb", _("English (U.K.) grade 1")),
	("en-GB-g2.ctb", _("English (U.K.) grade 2")),
	("en-us-comp6.ctb", _("English (U.S.) 6 dot computer braille")),
	("en-us-comp8.ctb", _("English (U.S.) 8 dot computer braille")),
	("en-us-g1.ctb", _("English (U.S.) grade 1")),
	("en-us-g2.ctb", _("English (U.S.) grade 2")),
	("Es-Es-g1.utb", _("Spanish grade 1")),
	("fi-fi-8dot.ctb", _("Finnish 8 dot computer braille")),
	("fr-ca-g1.utb", _("French (Canada) grade 1")),
	("Fr-Ca-g2.ctb", _("French (Canada) grade 2")),
	("fr-bfu-comp6.utb", _("French (unified) 6 dot computer braille")),
	("fr-bfu-comp8.utb", _("French (unified) 8 dot computer braille")),
	("fr-bfu-g2.ctb", _("French (unified) Grade 2")),	("gr-gr-g1.utb", _("Greek (Greece) grade 1")),
	("he.ctb", _("Hebrew 8 dot computer braille")),
	("hi-in-g1.utb", _("Hindi grade 1")),
	("hr.ctb", _("Croatian 8 dot computer braille")),
	("hu1.ctb", _("Hungarian 8 dot computer braille")),
	("it-it-g1.utb2", _("Italian grade 1")),
	("Lv-Lv-g1.utb", _("Latvian grade 1")),
	("nl-be-g1.utb", _("Dutch (Belgium) grade 1")),
	("Nl-Nl-g1.utb", _("Dutch (netherlands) grade 1")),
	("No-No-g0.utb", _("Norwegian grade 0")),
	("No-No-g1.ctb", _("Norwegian grade 1")),
	("No-No-g2.ctb", _("Norwegian grade 2")),
	("No-No-g3.ctb", _("Norwegian grade 3")),
	("Pl-Pl-g1.utb", _("Polish grade 1")),
	("Pt-Pt-g1.utb", _("Portuguese grade 1")),
	("ru-ru-g1.utb", _("Russian grade 1")),
	("Se-Se-g1.utb", _("Swedish grade 1")),
	("sk-sk-g1.utb", _("Slovak")),
	("UEBC-g1.utb", _("Unified English Braille Code grade 1")),
	("UEBC-g2.ctb", _("Unified English Braille Code grade 2")),
	("zh-hk.ctb", _("Chinese (Hong Kong, Cantonese)")),
	("zh-tw.ctb", _("Chinese (Taiwan, Mandarin)")),
)

roleLabels = {
	controlTypes.ROLE_EDITABLETEXT: _("edt"),
	controlTypes.ROLE_LIST: _("lst"),
	controlTypes.ROLE_MENUBAR: _("mnubar"),
	controlTypes.ROLE_POPUPMENU: _("mnu"),
	controlTypes.ROLE_BUTTON: _("btn"),
	controlTypes.ROLE_CHECKBOX: _("chk"),
	controlTypes.ROLE_RADIOBUTTON: _("rbtn"),
	controlTypes.ROLE_COMBOBOX: _("cbo"),
	controlTypes.ROLE_LINK: _("lnk"),
	controlTypes.ROLE_DIALOG: _("dlg"),
	controlTypes.ROLE_TREEVIEW: _("tv"),
	controlTypes.ROLE_TABLE: _("tb"),
}

positiveStateLabels = {
	controlTypes.STATE_CHECKED: _("(x)"),
	controlTypes.STATE_SELECTED: _("sel"),
	controlTypes.STATE_HASPOPUP: _("submnu"),
}
negativeStateLabels = {
	controlTypes.STATE_CHECKED: _("( )"),
}

def _getDisplayDriver(name):
	return __import__("brailleDisplayDrivers.%s" % name, globals(), locals(), ("brailleDisplayDrivers",)).BrailleDisplayDriver

def getDisplayList():
	displayList = []
	for loader, name, isPkg in pkgutil.iter_modules(brailleDisplayDrivers.__path__):
		if name.startswith('_'):
			continue
		try:
			display = _getDisplayDriver(name)
			if display.check():
				displayList.append((display.name, display.description))
		except:
			pass
	return displayList

class Region(object):
	"""A region of braille to be displayed.
	Each portion of braille to be displayed is represented by a region.
	The region is responsible for retrieving its text and cursor position, translating it into braille cells and handling cursor routing requests relative to its braille cells.
	The L{BrailleBuffer} containing this region will call L{update} and expect that L{brailleCells} and L{brailleCursorPos} will be set appropriately.
	L{routeTo} will be called to handle a cursor routing request.
	"""

	def __init__(self):
		#: The original, raw text of this region.
		self.rawText = ""
		#: The position of the cursor in L{rawText}, C{None} if the cursor is not in this region.
		#: @type: int
		self.cursorPos = None
		#: The translated braille representation of this region.
		#: @type: [int, ...]
		self.brailleCells = []
		#: A list mapping positions in L{rawText} to positions in L{brailleCells}.
		#: @type: [int, ...]
		self.rawToBraillePos = []
		#: A list mapping positions in L{brailleCells} to positions in L{rawText}.
		#: @type: [int, ...]
		self.brailleToRawPos = []
		#: The position of the cursor in L{brailleCells}, C{None} if the cursor is not in this region.
		#: @type: int
		self.brailleCursorPos = None
		#: Whether to hide all previous regions.
		#: @type: bool
		self.hidePreviousRegions = False
		#: Whether this region should be positioned at the absolute left of the display when focused.
		#: @type: bool
		self.focusToHardLeft = False

	def update(self):
		"""Update this region.
		Subclasses should extend this to update L{rawText} and L{cursorPos} if necessary.
		The base class method handles translation of L{rawText} into braille, placing the result in L{brailleCells}. L{rawToBraillePos} and L{brailleToRawPos} are updated according to the translation.
		L{brailleCursorPos} is similarly updated based on L{cursorPos}.
		@postcondition: L{brailleCells} and L{brailleCursorPos} are updated and ready for rendering.
		"""
		mode = louis.dotsIO | louis.pass1Only
		if config.conf["braille"]["expandAtCursor"] and self.cursorPos is not None:
			mode |= louis.compbrlAtCursor
		text=unicode(self.rawText).replace('\0','')
		braille, self.brailleToRawPos, self.rawToBraillePos, brailleCursorPos = louis.translate([os.path.join(TABLES_DIR, config.conf["braille"]["translationTable"])], text, mode=mode, cursorPos=self.cursorPos or 0)
		# liblouis gives us back a character string of cells, so convert it to a list of ints.
		# For some reason, the highest bit is set, so only grab the lower 8 bits.
		self.brailleCells = [ord(cell) & 255 for cell in braille]
		# HACK: Work around a liblouis bug whereby an empty braille translation is returned.
		if not self.brailleCells:
			# Just provide a space.
			self.brailleCells.append(0)
			self.brailleToRawPos.append(0)
		if self.cursorPos is not None:
			# HACK: Work around a liblouis bug whereby the returned cursor position is not within the braille cells returned.
			if brailleCursorPos >= len(self.brailleCells):
				brailleCursorPos = len(self.brailleCells) - 1
			self.brailleCursorPos = brailleCursorPos

	def routeTo(self, braillePos):
		"""Handle a cursor routing request.
		For example, this might activate an object or move the cursor to the requested position.
		@param braillePos: The routing position in L{brailleCells}.
		@type braillePos: int
		@note: If routing the cursor, L{brailleToRawPos} can be used to translate L{braillePos} into a position in L{rawText}.
		"""
		pass

	def nextLine(self):
		"""Move to the next line if possible.
		"""
		pass

	def previousLine(self, start=False):
		"""Move to the previous line if possible.
		@param start: C{True} to move to the start of the line, C{False} to move to the end.
		@type start: bool
		"""

class TextRegion(Region):
	"""A simple region containing a string of text.
	"""

	def __init__(self, text):
		super(TextRegion, self).__init__()
		self.rawText = text

def getBrailleTextForProperties(**propertyValues):
	# TODO: Don't use speech functions.
	textList = []
	name = propertyValues.get("name")
	if name:
		textList.append(name)
	role = propertyValues.get("role")
	if role is not None:
		if name and role in speech.silentRolesOnFocus:
			roleText = None
		else:
			roleText = roleLabels.get(role, controlTypes.speechRoleLabels[role])
	else:
		role = propertyValues.get("_role")
		roleText = None
	value = propertyValues.get("value")
	if value and role not in speech.silentValuesForRoles:
		textList.append(value)
	states = propertyValues.get("states")
	if states:
		positiveStates = speech.processPositiveStates(role, states, speech.REASON_FOCUS, states)
		textList.extend(positiveStateLabels.get(state, controlTypes.speechStateLabels[state]) for state in positiveStates)
		negativeStates = speech.processNegativeStates(role, states, speech.REASON_FOCUS, None)
		textList.extend(negativeStateLabels.get(state, _("not %s") % controlTypes.speechStateLabels[state]) for state in negativeStates)
	if roleText:
		textList.append(roleText)
	description = propertyValues.get("description")
	if description:
		textList.append(description)
	keyboardShortcut = propertyValues.get("keyboardShortcut")
	if keyboardShortcut:
		textList.append(keyboardShortcut)
	positionInfo = propertyValues.get("positionInfo")
	if positionInfo:
		if 'indexInGroup' in positionInfo and 'similarItemsInGroup' in positionInfo:
			textList.append(_("%s of %s")%(positionInfo['indexInGroup'],positionInfo['similarItemsInGroup']))
		if 'level' in positionInfo:
			textList.append(_('level %s')%positionInfo['level'])
	return " ".join([x for x in textList if x])

class NVDAObjectRegion(Region):
	"""A region to provide a braille representation of an NVDAObject.
	This region will update based on the current state of the associated NVDAObject.
	A cursor routing request will activate the object's default action.
	"""

	def __init__(self, obj, appendText=""):
		"""Constructor.
		@param obj: The associated NVDAObject.
		@type obj: L{NVDAObjects.NVDAObject}
		@param appendText: Text which should always be appended to the NVDAObject text, useful if this region will always precede other regions.
		@type appendText: str
		"""
		super(NVDAObjectRegion, self).__init__()
		self.obj = obj
		self.appendText = appendText

	def update(self):
		obj = self.obj
		text = getBrailleTextForProperties(name=obj.name, role=obj.role, value=obj.value, states=obj.states, description=obj.description, keyboardShortcut=obj.keyboardShortcut, positionInfo=obj.positionInfo)
		self.rawText = text + self.appendText
		super(NVDAObjectRegion, self).update()

	def routeTo(self, braillePos):
		try:
			self.obj.doAction()
		except NotImplementedError:
			pass

class ReviewNVDAObjectRegion(NVDAObjectRegion):

	def routeTo(self, braillePos):
		pass

class TextInfoRegion(Region):

	def __init__(self, obj):
		super(TextInfoRegion, self).__init__()
		self.obj = obj

	def _isMultiline(self):
		# A region's object can either be an NVDAObject or a tree interceptor.
		# Tree interceptors should always be multiline.
		from treeInterceptorHandler import TreeInterceptor
		if isinstance(self.obj, TreeInterceptor):
			return True
		# Terminals are inherently multiline, so they don't have the multiline state.
		return (self.obj.role == controlTypes.ROLE_TERMINAL or controlTypes.STATE_MULTILINE in self.obj.states)

	def _getSelection(self):
		"""Retrieve the selection.
		@return: The selection.
		@rtype: L{textInfos.TextInfo}
		"""
		try:
			return self.obj.makeTextInfo(textInfos.POSITION_SELECTION)
		except:
			return self.obj.makeTextInfo(textInfos.POSITION_FIRST)

	def _setCursor(self, info):
		"""Set the cursor.
		@param info: The range to which the cursor should be moved.
		@type info: L{textInfos.TextInfo}
		"""
		try:
			info.updateCaret()
		except NotImplementedError:
			log.debugWarning("", exc_info=True)

	def update(self):
		# HACK: Some TextInfos only support UNIT_LINE properly if they are based on POSITION_CARET,
		# so use the original caret TextInfo for line and copy for caret.
		self._line = line = self._getSelection()
		line.collapse()
		caret = line.copy()
		# Get the line at the caret.
		line.expand(textInfos.UNIT_LINE)
		# Not all text APIs support offsets, so we can't always get the offset of the caret relative to the start of the line.
		# Therefore, grab the line in two parts.
		# First, the chunk from the start of the line up to the caret.
		chunk = line.copy()
		chunk.collapse()
		chunk.setEndPoint(caret, "endToEnd")
		self.rawText = chunk.text or ""
		# The cursor position is the length of this chunk, as its end is the caret.
		self.cursorPos = len(self.rawText)
		# Now, get the chunk from the caret to the end of the line.
		chunk.setEndPoint(line, "endToEnd")
		chunk.setEndPoint(caret, "startToStart")
		# Strip line ending characters, but add a space in case the caret is at the end of the line.
		self.rawText += (chunk.text or "").rstrip("\r\n\0\v\f") + " "
		# If this is not the first line, hide all previous regions.
		start = caret.obj.makeTextInfo(textInfos.POSITION_FIRST)
		self.hidePreviousRegions = (start.compareEndPoints(line, "startToStart") < 0)
		# If this is a multiline control, position it at the absolute left of the display when focused.
		self.focusToHardLeft = self._isMultiline()
		super(TextInfoRegion, self).update()

	def routeTo(self, braillePos):
		pos = self.brailleToRawPos[braillePos]
		# pos is relative to the start of the line.
		# Therefore, get the start of the line...
		dest = self._line.copy()
		dest.collapse()
		# and move pos characters from there.
		dest.move(textInfos.UNIT_CHARACTER, pos)
		self._setCursor(dest)

	def nextLine(self):
		dest = self._line.copy()
		moved = dest.move(textInfos.UNIT_LINE, 1)
		if not moved:
			return
		dest.collapse()
		self._setCursor(dest)

	def previousLine(self, start=False):
		dest = self._line.copy()
		dest.collapse()
		# If the end of the line is desired, move to the last character.
		moved = dest.move(textInfos.UNIT_LINE if start else textInfos.UNIT_CHARACTER, -1)
		if not moved:
			return
		dest.collapse()
		self._setCursor(dest)

class CursorManagerRegion(TextInfoRegion):

	def _isMultiline(self):
		return True

	def _getSelection(self):
		return self.obj.selection

	def _setCursor(self, info):
		self.obj.selection = info

class ReviewTextInfoRegion(TextInfoRegion):

	def _getSelection(self):
		return api.getReviewPosition().copy()

	def _setCursor(self, info):
		api.setReviewPosition(info)

class BrailleBuffer(baseObject.AutoPropertyObject):

	def __init__(self, handler):
		self.handler = handler
		#: The regions in this buffer.
		#: @type: [L{Region}, ...]
		self.regions = []
		#: The position of the cursor in L{brailleCells}, C{None} if no region contains the cursor.
		#: @type: int
		self.cursorPos = None
		#: The translated braille representation of the entire buffer.
		#: @type: [int, ...]
		self.brailleCells = []
		#: The position in L{brailleCells} where the display window starts (inclusive).
		#: @type: int
		self.windowStartPos = 0

	def clear(self):
		"""Clear the entire buffer.
		This removes all regions and resets the window position to 0.
		"""
		self.regions = []
		self.cursorPos = None
		self.brailleCursorPos = None
		self.brailleCells = []
		self.windowStartPos = 0

	def _get_visibleRegions(self):
		if not self.regions:
			return
		if self.regions[-1].hidePreviousRegions:
			yield self.regions[-1]
			return
		for region in self.regions:
			yield region

	def _get_regionsWithPositions(self):
		start = 0
		for region in self.visibleRegions:
			end = start + len(region.brailleCells)
			yield region, start, end
			start = end

	def bufferPosToRegionPos(self, bufferPos):
		for region, start, end in self.regionsWithPositions:
			if end > bufferPos:
				return region, bufferPos - start
		raise LookupError("No such position")

	def regionPosToBufferPos(self, region, pos):
		for testRegion, start, end in self.regionsWithPositions:
			if region == testRegion:
				if pos < end:
					return start + pos
		raise LookupError("No such position")

	def bufferPosToWindowPos(self, bufferPos):
		if not (self.windowStartPos <= bufferPos < self.windowEndPos):
			raise LookupError("Buffer position not in window")
		return bufferPos - self.windowStartPos

	def _get_windowEndPos(self):
		try:
			lineEnd = self.brailleCells.index(-1, self.windowStartPos)
		except ValueError:
			lineEnd = len(self.brailleCells)
		return min(lineEnd, self.windowStartPos + self.handler.displaySize)

	def _set_windowEndPos(self, endPos):
		lineStart = endPos - 1
		# Find the end of the previous line.
		while lineStart >= 0:
			if self.brailleCells[lineStart] == -1:
				break
			lineStart -= 1
		lineStart += 1
		self.windowStartPos = max(endPos - self.handler.displaySize, lineStart)

	def scrollForward(self):
		oldStart = self.windowStartPos
		end = self.windowEndPos
		if end < len(self.brailleCells):
			self.windowStartPos = end
		if self.windowStartPos == oldStart:
			# The window could not be scrolled, so try moving to the next line.
			if self.regions:
				self.regions[-1].nextLine()
		else:
			# Scrolling succeeded.
			self.updateDisplay()

	def scrollBack(self):
		start = self.windowStartPos
		if start > 0:
			self.windowEndPos = start
		if self.windowStartPos == start:
			# The window could not be scrolled, so try moving to the previous line.
			if self.regions:
				self.regions[-1].previousLine()
		else:
			# Scrolling succeeded.
			self.updateDisplay()

	def scrollTo(self, region, pos):
		pos = self.regionPosToBufferPos(region, pos)
		if pos >= self.windowEndPos:
			self.windowEndPos = pos + 1
		elif pos < self.windowStartPos:
			self.windowStartPos = pos
		self.updateDisplay()

	def focus(self, region):
		"""Bring the specified region into focus.
		The region is placed at the start of the display.
		However, if the region has not set L{Region.focusToHardLeft} and there is extra space at the end of the display, the display is scrolled left so that as much as possible is displayed.
		@param region: The region to focus.
		@type region: L{Region}
		"""
		pos = self.regionPosToBufferPos(region, 0)
		self.windowStartPos = pos
		if region.focusToHardLeft:
			return
		end = self.windowEndPos
		if end - pos < self.handler.displaySize:
			# We can fit more on the display while still keeping pos visible.
			# Force windowStartPos to be recalculated based on windowEndPos.
			self.windowEndPos = end

	def update(self):
		self.brailleCells = []
		self.cursorPos = None
		start = 0
		for region in self.visibleRegions:
			cells = region.brailleCells
			self.brailleCells.extend(cells)
			if region.brailleCursorPos is not None:
				self.cursorPos = start + region.brailleCursorPos
			start += len(cells)

	def updateDisplay(self):
		if self is self.handler.buffer:
			self.handler.update()

	def _get_cursorWindowPos(self):
		if self.cursorPos is None:
			return None
		try:
			return self.bufferPosToWindowPos(self.cursorPos)
		except LookupError:
			return None

	def _get_windowBrailleCells(self):
		return self.brailleCells[self.windowStartPos:self.windowEndPos]

	def routeTo(self, windowPos):
		pos = self.windowStartPos + windowPos
		if pos >= self.windowEndPos:
			return
		region, pos = self.bufferPosToRegionPos(pos)
		region.routeTo(pos)

	def saveWindow(self):
		"""Save the current window so that it can be restored after the buffer is updated.
		The window start position is saved as a position relative to a region.
		This allows it to be restored even after other regions are added, removed or updated.
		It can be restored with L{restoreWindow}.
		@postcondition: The window is saved and can be restored with L{restoreWindow}.
		"""
		self._savedWindow = self.bufferPosToRegionPos(self.windowStartPos)

	def restoreWindow(self, ignoreErrors=False):
		"""Restore the window saved by L{saveWindow}.
		@param ignoreErrors: Whether to ignore errors.
		@type ignoreErrors: bool
		@precondition: L{saveWindow} has been called.
		@postcondition: If the saved position is valid, the window is restored.
		@raise LookupError: If C{ignoreErrors} is C{False} and the saved region position is invalid.
		"""
		try:
			self.windowStartPos = self.regionPosToBufferPos(*self._savedWindow)
		except LookupError:
			if not ignoreErrors:
				raise

_cachedFocusAncestorsEnd = 0
def invalidateCachedFocusAncestors(index):
	"""Invalidate cached focus ancestors from a given index.
	This will cause regions to be generated for the focus ancestors >= index next time L{getFocusContextRegions} is called,
	rather than using cached regions for those ancestors.
	@param index: The index from which cached focus ancestors should be invalidated.
	@type index: int
	"""
	global _cachedFocusAncestorsEnd
	# There could be multiple calls to this function before getFocusContextRegions() is called.
	_cachedFocusAncestorsEnd = min(_cachedFocusAncestorsEnd, index)

def getFocusContextRegions(obj, oldFocusRegions=None):
	global _cachedFocusAncestorsEnd
	# Late import to avoid circular import.
	from treeInterceptorHandler import TreeInterceptor
	ancestors = api.getFocusAncestors()

	ancestorsEnd = len(ancestors)
	if isinstance(obj, TreeInterceptor):
		obj = obj.rootNVDAObject
		# We only want the ancestors of the buffer's root NVDAObject.
		if obj != api.getFocusObject():
			# Search backwards through the focus ancestors to find the index of obj.
			for index, ancestor in itertools.izip(xrange(len(ancestors) - 1, 0, -1), reversed(ancestors)):
				if obj == ancestor:
					ancestorsEnd = index
					break

	if oldFocusRegions:
		# We have the regions from the previous focus, so use them as a cache to avoid rebuilding regions which are the same.
		# We need to generate new regions from _cachedFocusAncestorsEnd onwards.
		# However, we must ensure that it is not beyond the last ancestor we wish to consider.
		# Also, we don't ever want to fetch ancestor 0 (the desktop).
		newAncestorsStart = max(min(_cachedFocusAncestorsEnd, ancestorsEnd), 1)
		# Search backwards through the old regions to find the last common region.
		for index, region in itertools.izip(xrange(len(oldFocusRegions) - 1, -1, -1), reversed(oldFocusRegions)):
			ancestorIndex = getattr(region, "_focusAncestorIndex", None)
			if ancestorIndex is None:
				continue
			if ancestorIndex < newAncestorsStart:
				# This is the last common region.
				# An ancestor may have been skipped and not have a region, which means that we need to grab new ancestors from this point.
				newAncestorsStart = ancestorIndex + 1
				commonRegionsEnd = index + 1
				break
		else:
			# No common regions were found.
			commonRegionsEnd = 0
			newAncestorsStart = 1
		# Yield the common regions.
		for region in oldFocusRegions[0:commonRegionsEnd]:
			yield region
	else:
		# Fetch all ancestors.
		newAncestorsStart = 1

	for index, parent in enumerate(ancestors[newAncestorsStart:ancestorsEnd], newAncestorsStart):
		if not parent.isPresentableFocusAncestor:
			continue
		region = NVDAObjectRegion(parent, appendText=" ")
		region._focusAncestorIndex = index
		region.update()
		yield region

	_cachedFocusAncestorsEnd = ancestorsEnd

def getFocusRegions(obj, review=False):
	# Late import to avoid circular import.
	from treeInterceptorHandler import TreeInterceptor
	from cursorManager import CursorManager
	if isinstance(obj, CursorManager):
		region2 = (ReviewTextInfoRegion if review else CursorManagerRegion)(obj)
	elif isinstance(obj, TreeInterceptor) or obj.role in (controlTypes.ROLE_EDITABLETEXT, controlTypes.ROLE_TERMINAL) or controlTypes.STATE_EDITABLE in obj.states:
		region2 = (ReviewTextInfoRegion if review else TextInfoRegion)(obj)
	else:
		region2 = None
	if isinstance(obj, TreeInterceptor):
		obj = obj.rootNVDAObject
	region = (ReviewNVDAObjectRegion if review else NVDAObjectRegion)(obj, appendText=" " if region2 else "")
	region.update()
	yield region
	if region2:
		region2.update()
		yield region2

class BrailleHandler(baseObject.AutoPropertyObject):
	TETHER_FOCUS = "focus"
	TETHER_REVIEW = "review"

	cursorShape = 0xc0

	def __init__(self):
		self.display = None
		self.displaySize = 0
		self.mainBuffer = BrailleBuffer(self)
		self.messageBuffer = BrailleBuffer(self)
		self._messageCallLater = None
		self.buffer = self.mainBuffer
		#: Whether braille is enabled.
		#: @type: bool
		self.enabled = False
		self._keyCountForLastMessage=0
		self._cursorPos = None
		self._cursorBlinkUp = True
		self._cells = []
		self._cursorBlinkTimer = None

	def _get_tether(self):
		return config.conf["braille"]["tetherTo"]

	def _set_tether(self, tether):
		if tether == config.conf["braille"]["tetherTo"]:
			return
		config.conf["braille"]["tetherTo"] = tether
		self.mainBuffer.clear()
		if tether == self.TETHER_REVIEW:
			self.handleReviewMove()
		else:
			self.handleGainFocus(api.getFocusObject())

	def setDisplayByName(self, name):
		if not name:
			self.display = None
			self.displaySize = 0
			return
		try:
			newDisplay = _getDisplayDriver(name)
			if newDisplay == self.display.__class__:
				# This is the same driver as was already set, so just re-initialise it.
				self.display.terminate()
				newDisplay = self.display
				newDisplay.__init__()
			else:
				newDisplay = newDisplay()
				if self.display:
					try:
						self.display.terminate()
					except:
						log.error("Error terminating previous display driver", exc_info=True)
				self.display = newDisplay
			self.displaySize = newDisplay.numCells
			self.enabled = bool(self.displaySize)
			config.conf["braille"]["display"] = name
			log.info("Loaded braille display driver %s" % name)
			return True
		except:
			log.error("Error initializing display driver", exc_info=True)
			self.setDisplayByName("noBraille")
			return False

	def _updateDisplay(self):
		if self._cursorBlinkTimer:
			self._cursorBlinkTimer.Stop()
			self._cursorBlinkTimer = None
		self._cursorBlinkUp = True
		self._displayWithCursor()
		blinkRate = config.conf["braille"]["cursorBlinkRate"]
		if blinkRate and self._cursorPos is not None:
			self._cursorBlinkTimer = wx.PyTimer(self._blink)
			self._cursorBlinkTimer.Start(blinkRate)

	def _displayWithCursor(self):
		if not self._cells:
			return
		cells = list(self._cells)
		if self._cursorPos is not None and self._cursorBlinkUp:
			cells[self._cursorPos] |= self.cursorShape
		self.display.display(cells)

	def _blink(self):
		self._cursorBlinkUp = not self._cursorBlinkUp
		self._displayWithCursor()

	def update(self):
		cells = self.buffer.windowBrailleCells
		# cells might not be the full length of the display.
		# Therefore, pad it with spaces to fill the display.
		self._cells = cells + [0] * (self.displaySize - len(cells))
		self._cursorPos = self.buffer.cursorWindowPos
		self._updateDisplay()

	def scrollForward(self):
		self.buffer.scrollForward()
		if self.buffer is self.messageBuffer:
			self._resetMessageTimer()

	def scrollBack(self):
		self.buffer.scrollBack()
		if self.buffer is self.messageBuffer:
			self._resetMessageTimer()

	def routeTo(self, windowPos):
		self.buffer.routeTo(windowPos)
		if self.buffer is self.messageBuffer:
			self._dismissMessage()

	def message(self, text):
		"""Display a message to the user which times out after a configured interval.
		The timeout will be reset if the user scrolls the display.
		The message will be dismissed immediately if the user presses a cursor routing key.
		If a key is pressed the message will be dismissed by the next text being written to the display
		@postcondition: The message is displayed.
		"""
		if not self.enabled:
			return
		if self.buffer is self.messageBuffer:
			self.buffer.clear()
		else:
			self.buffer = self.messageBuffer
		region = TextRegion(text)
		region.update()
		self.buffer.regions.append(region)
		self.buffer.update()
		self.update()
		self._resetMessageTimer()
		self._keyCountForLastMessage=keyboardHandler.keyCounter

	def _resetMessageTimer(self):
		"""Reset the message timeout.
		@precondition: A message is currently being displayed.
		"""
		# Configured timeout is in seconds.
		timeout = config.conf["braille"]["messageTimeout"] * 1000
		if self._messageCallLater:
			self._messageCallLater.Restart(timeout)
		else:
			self._messageCallLater = wx.CallLater(timeout, self._dismissMessage)

	def _dismissMessage(self):
		"""Dismiss the current message.
		@precondition: A message is currently being displayed.
		@postcondition: The display returns to the main buffer.
		"""
		self.buffer.clear()
		self.buffer = self.mainBuffer
		self._messageCallLater.Stop()
		self._messageCallLater = None
		self.update()

	def handleGainFocus(self, obj):
		if not self.enabled:
			return
		if self.tether != self.TETHER_FOCUS:
			return
		self._doNewObject(itertools.chain(getFocusContextRegions(obj, oldFocusRegions=self.mainBuffer.regions), getFocusRegions(obj)))

	def _doNewObject(self, regions):
		self.mainBuffer.clear()
		for region in regions:
			self.mainBuffer.regions.append(region)
		self.mainBuffer.update()
		# Last region should receive focus.
		self.mainBuffer.focus(region)
		if region.brailleCursorPos is not None:
			self.mainBuffer.scrollTo(region, region.brailleCursorPos)
		if self.buffer is self.mainBuffer:
			self.update()
		elif self.buffer is self.messageBuffer and keyboardHandler.keyCounter>self._keyCountForLastMessage:
			self._dismissMessage()

	def handleCaretMove(self, obj):
		if not self.enabled:
			return
		if self.tether != self.TETHER_FOCUS:
			return
		if not self.mainBuffer.regions:
			return
		region = self.mainBuffer.regions[-1]
		if region.obj is not obj:
			return
		self._doCursorMove(region)

	def _doCursorMove(self, region):
		self.mainBuffer.saveWindow()
		region.update()
		self.mainBuffer.update()
		self.mainBuffer.restoreWindow(ignoreErrors=True)
		if region.brailleCursorPos is not None:
			self.mainBuffer.scrollTo(region, region.brailleCursorPos)
		if self.buffer is self.mainBuffer:
			self.update()
		elif self.buffer is self.messageBuffer and keyboardHandler.keyCounter>self._keyCountForLastMessage:
			self._dismissMessage()

	def handleUpdate(self, obj):
		if not self.enabled:
			return
		# Optimisation: It is very likely that it is the focus object that is being updated.
		# If the focus object is in the braille buffer, it will be the last region, so scan the regions backwards.
		for region in reversed(list(self.mainBuffer.visibleRegions)):
			if hasattr(region, "obj") and region.obj == obj:
				break
		else:
			# No region for this object.
			return
		self.mainBuffer.saveWindow()
		region.update()
		self.mainBuffer.update()
		self.mainBuffer.restoreWindow(ignoreErrors=True)
		if self.buffer is self.mainBuffer:
			self.update()
		elif self.buffer is self.messageBuffer and keyboardHandler.keyCounter>self._keyCountForLastMessage:
			self._dismissMessage()

	def handleReviewMove(self):
		if not self.enabled:
			return
		if self.tether != self.TETHER_REVIEW:
			return
		reviewPos = api.getReviewPosition()
		region = self.mainBuffer.regions[-1] if self.mainBuffer.regions else None
		if region and region.obj == reviewPos.obj:
			self._doCursorMove(region)
		else:
			# We're reviewing a different object.
			self._doNewObject(getFocusRegions(reviewPos.obj, review=True))

def initialize():
	global handler
	config.addConfigDirsToPythonPackagePath(brailleDisplayDrivers)
	log.info("Using liblouis version %s" % louis.version())
	handler = BrailleHandler()
	handler.setDisplayByName(config.conf["braille"]["display"])

def terminate():
	global handler
	if handler.display:
		handler.display.terminate()
	handler = None

class BrailleDisplayDriver(baseObject.AutoPropertyObject):
	"""Abstract base braille display driver.
	Each braille display driver should be a separate Python module in the root brailleDisplayDrivers directory containing a BrailleDisplayDriver class which inherits from this base class.
	
	At a minimum, drivers must set L{name} and L{description} and override the L{check} method.
	To display braille, L{numCells} and L{display} must be implemented.
	
	Drivers should dispatch input such as presses of buttons, wheels or other controls using the L{inputCore} framework.
	They should subclass L{BrailleDisplayGesture} and execute instances of those gestures using L{inputCore.manager.executeGesture}.
	These gestures can be mapped in L{gestureMap}.
	A driver can also inherit L{baseObject.ScriptableObject} to provide display specific scripts.
	"""
	#: The name of the braille display; must be the original module file name.
	#: @type: str
	name = ""
	#: A description of the braille display.
	#: @type: str
	description = ""

	@classmethod
	def check(cls):
		"""Determine whether this braille display is available.
		The display will be excluded from the list of available displays if this method returns C{False}.
		For example, if this display is not present, C{False} should be returned.
		@return: C{True} if this display is available, C{False} if not.
		@rtype: bool
		"""
		return False

	def terminate(self):
		"""Terminate this display driver.
		This will be called when NVDA is finished with this display driver.
		It should close any open connections, perform cleanup, etc.
		Subclasses should call the superclass method first.
		@postcondition: This instance can no longer be used unless it is constructed again.
		"""
		# Clear the display.
		try:
			self.display([0] * self.numCells)
		except:
			# The display driver seems to be failing, but we're terminating anyway, so just ignore it.
			pass

	def _get_numCells(self):
		"""Obtain the number of braille cells on this  display.
		@note: 0 indicates that braille should be disabled.
		@return: The number of cells.
		@rtype: int
		"""
		return 0

	def display(self, cells):
		"""Display the given braille cells.
		@param cells: The braille cells to display.
		@type cells: [int, ...]
		"""

	#: Global input gesture map for this display driver.
	#: @type: L{inputCore.GlobalGestureMap}
	gestureMap = None

class BrailleDisplayGesture(inputCore.InputGesture):
	"""A button, wheel or other control pressed on a braille display.
	Subclasses must provide L{source} and L{id}.
	L{routingIndex} should be provided for routing buttons.
	If the braille display driver is a L{baseObject.ScriptableObject}, it can provide scripts specific to input gestures from this display.
	"""

	def _get_source(self):
		"""The string used to identify all gestures from this display.
		This should generally be the driver name.
		This string will be included in the source portion of gesture identifiers.
		For example, if this was C{alvaBC6},
		a display specific gesture identifier might be C{br(alvaBC6):etouch1}.
		@rtype: str
		"""
		raise NotImplementedError

	def _get_id(self):
		"""The unique, display specific id for this gesture.
		@rtype: str
		"""
		raise NotImplementedError

	#: The index of the routing key or C{None} if this is not a routing key.
	#: @type: int
	routingIndex = None

	def _get_identifiers(self):
		return (u"br({source}):{id}".format(source=self.source, id=self.id).lower(),)

	def _get_displayName(self):
		return self.id

	def _get_scriptableObject(self):
		display = handler.display
		if isinstance(display, baseObject.ScriptableObject):
			return display
		return super(BrailleDisplayGesture, self).scriptableObject
