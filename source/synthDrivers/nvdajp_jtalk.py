#synthDrivers/nvdajp_jtalk.py
# -*- coding: utf-8 -*-
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajp_jtalk (based on Open JTalk and libopenjtalk)
# by Takuya Nishimoto

import _nvdajp_jtalk
from synthDriverHandler import SynthDriver,VoiceInfo
import synthDriverHandler
from collections import OrderedDict

# _LANGUAGE = 1041 # locale.windows_locale[1041] = 'ja_JP'

class SynthDriver(SynthDriver):
	"""A Japanese synth driver for NVDAjp.
	"""
	name = "nvdajp_jtalk"
	description = "JTalk"
	supportedSettings=(SynthDriver.VoiceSetting(),SynthDriver.RateSetting(),SynthDriver.PitchSetting(),SynthDriver.InflectionSetting(),SynthDriver.VolumeSetting())

	@classmethod
	def check(cls):
		return True

	def __init__(self):
		_nvdajp_jtalk.initialize()
		self.voice_id = 'V1'

	def speakText(self,text,index=None):
		_nvdajp_jtalk.speak(text, index=index)

	def speakCharacter(self,character,index=None):
		_nvdajp_jtalk.speak(character, index=index, isCharacter=True)

	def cancel(self):
		_nvdajp_jtalk.stop()

	def pause(self,switch):
		_nvdajp_jtalk.pause(switch)

	def terminate(self):
		_nvdajp_jtalk.terminate()

	# The current rate; ranges between 0 and 100
	def _get_rate(self):
		return _nvdajp_jtalk.get_rate()

	def _set_rate(self,rate):
		_nvdajp_jtalk.set_rate(rate)

	def _get_pitch(self):
		return 50

	def _set_pitch(self,pitch):
		return

	def _get_volume(self):
		return 100

	def _set_volume(self,volume):
		return

	def _get_inflection(self):
		return 50

	def _set_inflection(self,val):
		return

	def _getAvailableVoices(self):
		_nvdajp_jtalk.log.info("_getAvailableVoices called")
		voices = OrderedDict() # []
		for v in _nvdajp_jtalk._jtalk_voices:
			#voices.append(VoiceInfo(v['id'], v['name']))
			voices[v['id']] = VoiceInfo(v['id'], v['name'], 'ja_JP')
		return voices

	def _get_voice(self):
		_nvdajp_jtalk.log.info("_get_voice called")
		return self.voice_id # "V1"

	def _set_voice(self, identifier):
		_nvdajp_jtalk.log.info("_set_voice %s" % (identifier))
		rate = _nvdajp_jtalk.get_rate()
		for v in _nvdajp_jtalk._jtalk_voices:
			if v['id'] == identifier:
				self.voice_id = identifier
				_nvdajp_jtalk.terminate()
				_nvdajp_jtalk.initialize(v)
				_nvdajp_jtalk.set_rate(rate)
				return
		return

	def _get_lastIndex(self):
		return _nvdajp_jtalk.lastIndex
