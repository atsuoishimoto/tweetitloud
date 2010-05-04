import _default
import re
import controlTypes
import oleacc
import NVDAObjects.IAccessible

class AppModule(_default.AppModule):

	def event_NVDAObject_init(self,obj):
		if isinstance(obj,NVDAObjects.IAccessible.IAccessible):
			obj.shouldAllowIAccessibleFocusEvent=True
			if obj.IAccessibleRole==oleacc.ROLE_SYSTEM_WINDOW and obj.windowClassName=="WebViewWindowClass":
				#Disable a safety mechonism in our IAccessible support as in iTunes it causes an infinit ancestry.
				obj.parentUsesSuperOnWindowRootIAccessible=False

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		windowClassName=obj.windowClassName
		role=obj.role
		if ((windowClassName=="iTunesSources" and role==controlTypes.ROLE_TREEVIEWITEM)
			or (windowClassName=="iTunesTrackList" and role==controlTypes.ROLE_LISTITEM)
		):
			clsList.insert(0, ITunesItem)

class ITunesItem(NVDAObjects.IAccessible.IAccessible):
	"""Retreaves position information encoded in the accDescription"""

	RE_POSITION_INFO = re.compile(r"L(?P<level>\d+), (?P<indexInGroup>\d+) of (?P<similarItemsInGroup>\d+)")

	# The description and value should not be user visible.
	description = None
	value = None

	def _get_positionInfo(self):
		# iTunes encodes the position info in the accDescription.
		try:
			desc = self.IAccessibleObject.accDescription(self.IAccessibleChildID)
		except COMError:
			return super(ITunesItem, self).positionInfo

		if desc:
			m = self.RE_POSITION_INFO.match(desc)
			if m:
				return m.groupdict()
