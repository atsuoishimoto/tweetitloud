#synthDrivers/silence.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2008 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

from collections import OrderedDict
import synthDriverHandler
from synthDriverHandler import SynthDriver, VoiceInfo

class SynthDriver(synthDriverHandler.SynthDriver):
	"""A dummy synth driver used to disable speech in NVDA.
	"""
	supportedSettings=(SynthDriver.VoiceSetting(),)
	name="silence2"
	description="silence2"

	@classmethod
	def check(cls):
		return True

	def _get_voice(self):
		return "S1"

	def _set_voice(self,value):
		pass

	def _getAvailableVoices(self):
		voices=OrderedDict()
		voices['S1']=VoiceInfo('S1','silence','ja_JP')
		return voices
