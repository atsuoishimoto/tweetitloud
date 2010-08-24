#keyCommandsDoc.py
#A part of NonVisual Desktop Access (NVDA)
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#Copyright (C) 2010 James Teh <jamie@jantrid.net>

"""Utilities related to NVDA Key Commands documents.
"""

import os
import codecs
import re
import txt2tags

KEY_COMMANDS_FILENAME = "keyCommands.t2t"
LINE_END = u"\r\n"

class KeyCommandsError(Exception):
	"""Raised due to an error encountered in the User Guide related to generation of the Key Commands document.
	"""

class KeyCommandsMaker(object):
	"""Generates the Key Commands document from the User Guide.
	To generate a Key Commands document, create an instance and then call L{make} on it.
	
	Generation of the Key Commands document requires certain commands to be included in the user guide.
	These commands must begin at the start of the line and take the form::
		%kc:command: arg
	
	The kc:title command must appear first and specifies the title of the Key Commands document. For example::
		%kc:title: NVDA Key Commands
	
	The kc:includeconf command allows you to insert a txt2tags includeconf command in the Key Commands document. For example::
		%kc:includeconf: ../ar.t2tconf
	You may use multiple kc:includeconf commands, but they must appear before any of the other commands below.
	
	The rest of these commands are used to include key commands into the document.
	Appropriate headings from the User Guide will be included implicitly.
	
	The kc:beginInclude command begins a block of text which should be included verbatim.
	The block ends at the kc:endInclude command.
	For example::
		%kc:beginInclude
		|| Name | Desktop command | Laptop command | Description |
		...
		%kc:endInclude
	
	The kc:settingsSection command indicates the beginning of a section documenting individual settings.
	It specifies the header row for a table summarising the settings indicated by the kc:setting command (see below).
	In order, it must consist of a name column, a column for each keyboard layout and a description column.
	For example::
		%kc:settingsSection: || Name | Desktop command | Laptop command | Description |
	
	The kc:setting command indicates a section for an individual setting.
	It must be followed by:
		* A heading containing the name of the setting;
		* A table row for each keyboard layout, or if the key is common to all layouts, a single line of text specifying the key after a colon;
		* A blank line; and
		* A line describing the setting.
	For example::
		%kc:setting
		==== Braille Tethered To ====
		| Desktop command | NVDA+control+t |
		| Laptop Command | NVDA+control+t |
		This option allows you to choose whether the braille display will follow the system focus, or whether it follows the navigator object / review cursor.
	"""

	t2tRe = None
	RE_COMMAND = re.compile(r"^%kc:(?P<cmd>[^:\s]+)(?:: (?P<arg>.*))?$")
	KCSECT_HEADER = 0
	KCSECT_CONFIG = 1
	KCSECT_BODY = 2

	@classmethod
	def _initClass(cls):
		if cls.t2tRe:
			return
		# Only fetch this once.
		cls.t2tRe = txt2tags.getRegexes()

	def __init__(self, userGuideFilename):
		"""Constructor.
		@param userGuideFilename: The file name of the User Guide to be used as input.
		@type userGuideFilename: str
		"""
		self._initClass()
		self.ugFn = userGuideFilename
		#: The file name of the Key Commands document that will be generated.
		#: This will be in the same directory as the User Guide.
		self.kcFn = os.path.join(os.path.dirname(userGuideFilename), KEY_COMMANDS_FILENAME)
		#: The current section of the key commands file.
		self._kcSect = self.KCSECT_HEADER
		#: The current stack of headings.
		self._headings = []
		#: The 0 based level of the last heading in L{_headings} written to the key commands file.
		self._kcLastHeadingLevel = -1
		#: Whether lines which aren't commands should be written to the key commands file as is.
		self._kcInclude = False
		#: The header row for settings sections.
		self._settingsHeaderRow = None
		#: The number of layouts for settings in a settings section.
		self._settingsNumLayouts = 0

	def make(self):
		"""Generate the Key Commands document.
		@postcondition: If the User Guide contains appropriate commands, the Key Commands document will be generated and saved as L{kcFn}.
			Otherwise, no file will be generated.
		@return: C{True} if a document was generated, C{False} otherwise.
		@rtype: bool
		@raise IOError:
		@raise KeyCommandsError:
		"""
		self._ug = codecs.open(self.ugFn, "r", "utf-8-sig")
		self._kc = codecs.open(self.kcFn, "w", "utf-8-sig")

		with self._ug, self._kc:
			self._make()
			return self._kc.tell() > 0

	def _make(self):
		for line in self._ug:
			line = line.rstrip()
			m = self.RE_COMMAND.match(line)
			if m:
				self._command(**m.groupdict())
				continue

			m = self.t2tRe["numtitle"].match(line)
			if m:
				self._heading(m)
				continue

			if self._kcInclude:
				self._kc.write(line + LINE_END)

	def _command(self, cmd=None, arg=None):
		# Handle header commands.
		if cmd == "title":
			if self._kcSect > self.KCSECT_HEADER:
				raise KeyCommandsError("title command is not valid here")
			# Write the title and two blank lines to complete the txt2tags header section.
			self._kc.write(arg + LINE_END * 3)
			self._kcSect = self.KCSECT_CONFIG
			self._kc.write("%%!includeconf: ../global.t2tconf%s" % LINE_END)
			return
		elif self._kcSect == self.KCSECT_HEADER:
			raise KeyCommandsError("title must be the first command")
		elif cmd == "includeconf":
			if self._kcSect > self.KCSECT_CONFIG:
				raise KeyCommandsError("includeconf command is not valid here")
			self._kc.write("%%!includeconf: %s%s" % (arg, LINE_END))
			return
		elif self._kcSect == self.KCSECT_CONFIG:
			self._kc.write(LINE_END)
			self._kcSect = self.KCSECT_BODY

		if cmd == "beginInclude":
			self._writeHeadings()
			self._kcInclude = True
		elif cmd == "endInclude":
			self._kcInclude = False
			self._kc.write(LINE_END)

		elif cmd == "settingsSection":
			# The argument is the table header row for the settings section.
			self._settingsHeaderRow = arg
			# There are name and description columns.
			# Each of the remaining columns provides keystrokes for one layout.
			# There's one less delimiter than there are columns, hence subtracting 1 instead of 2.
			self._settingsNumLayouts = arg.strip("|").count("|") - 1
		elif cmd == "setting":
			self._handleSetting()

		else:
			raise KeyCommandsError("Invalid command %s" % cmd)

	def _areHeadingsPending(self):
		return self._kcLastHeadingLevel < len(self._headings) - 1

	def _writeHeadings(self):
		level = self._kcLastHeadingLevel + 1
		# Only write headings we haven't yet written.
		for level, heading in enumerate(self._headings[level:], level):
			# We don't want numbered headings in the output.
			label=heading.group("label")
			headingText = u"{id}{txt}{id}{label}".format(
				id="=" * len(heading.group("id")),
				txt=heading.group("txt"),
				label="[%s]" % label if label else "")
			# Write the heading and a blank line.
			self._kc.write(headingText + LINE_END * 2)
		self._kcLastHeadingLevel = level

	def _heading(self, m):
		# We work with 0 based heading levels.
		level = len(m.group("id")) - 1
		try:
			del self._headings[level:]
		except IndexError:
			pass
		self._headings.append(m)
		self._kcLastHeadingLevel = min(self._kcLastHeadingLevel, level - 1)

	def _handleSetting(self):
		if not self._settingsHeaderRow:
			raise KeyCommandsError("setting command cannot be used before settingsSection command")

		if self._areHeadingsPending():
			# There are new headings to write.
			# If there was a previous settings table, it ends here, so write a blank line.
			self._kc.write(LINE_END)
			self._writeHeadings()
			# New headings were written, so we need to output the header row.
			self._kc.write(self._settingsHeaderRow + LINE_END)

		# The next line should be a heading which is the name of the setting.
		line = next(self._ug)
		m = self.t2tRe["title"].match(line)
		if not m:
			raise KeyCommandsError("setting command must be followed by heading")
		name = m.group("txt")

		# The next few lines should be table rows for each layout.
		# Alternatively, if the key is common to all layouts, there will be a single line of text specifying the key after a colon.
		keys = []
		for layout in xrange(self._settingsNumLayouts):
			line = next(self._ug).strip()
			if ":" in line:
				keys.append(line.split(":", 1)[1].strip())
				break
			elif not self.t2tRe["table"].match(line):
				raise KeyCommandsError("setting command: There must be one table row for each keyboard layout")
			# This is a table row.
			# The key will be the second column.
			# TODO: Error checking.
			key = line.strip("|").split("|")[1].strip()
			keys.append(key)
		if 1 == len(keys) < self._settingsNumLayouts:
			# The key has only been specified once, so it is the same in all layouts.
			key = keys[0]
			keys[1:] = (key for layout in xrange(self._settingsNumLayouts - 1))

		# There should now be a blank line.
		line = next(self._ug).strip()
		if line:
			raise KeyCommandsError("setting command: The keyboard shortcuts must be followed by a blank line")

		# Finally, the next line should be the description.
		desc = next(self._ug).strip()

		self._kc.write(u"| {name} | {keys} | {desc} |{lineEnd}".format(
			name=name,
			keys=u" | ".join(keys),
			desc=desc, lineEnd=LINE_END))

	def remove(self):
		"""Remove the generated Key Commands document.
		"""
		try:
			os.remove(self.kcFn)
		except OSError:
			pass
