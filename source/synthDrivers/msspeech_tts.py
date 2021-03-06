#synthDrivers/msspeech_tts.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2009 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

# since 2011-2-2 by Masataka Shinke
# based on NVDA (synthDrivers/sapi5.py)

import locale
from collections import OrderedDict
import time
import os
import comtypes.client
from comtypes import COMError
import _winreg
import globalVars
from synthDriverHandler import SynthDriver,VoiceInfo
import config
import nvwave
from logHandler import log

class constants:
	SVSFlagsAsync = 1
	SVSFPurgeBeforeSpeak = 2
	SVSFIsXML = 8

COM_CLASS = "Speech.SpVoice"

class SynthDriver(SynthDriver):
	supportedSettings=(SynthDriver.VoiceSetting(),SynthDriver.RateSetting(),SynthDriver.PitchSetting(),SynthDriver.VolumeSetting())

	name="msspeech_tts"
	description="Microsoft Speech Platform"

	@classmethod
	def check(cls):
		try:
			r=_winreg.OpenKey(_winreg.HKEY_CLASSES_ROOT,COM_CLASS)
			r.Close()
			return True
		except:
			return False

	def __init__(self):
		self._pitch=50
		self._initTts()

	def terminate(self):
		del self.tts

	def _getAvailableVoices(self):
		voices=OrderedDict()
		v=self.tts.GetVoices()
		for i in range(len(v)):
			try:
				ID=v[i].Id
				name=v[i].GetDescription()
				try:
					language=locale.windows_locale[int(v[i].getattribute('language').split(';')[0],16)]
				except KeyError:
					language=None
			except COMError:
				log.warning("Could not get the voice info. Skipping...")
			voices[ID]=VoiceInfo(ID,name,language)
		return voices

	def _get_rate(self):
		return (self.tts.rate*5)+50

	def _get_pitch(self):
		return self._pitch

	def _get_volume(self):
		return self.tts.volume

	def _get_voice(self):
		return self.tts.voice.Id
 
	def _get_lastIndex(self):
		bookmark=self.tts.status.LastBookmark
		if bookmark!="" and bookmark is not None:
			return int(bookmark)
		else:
			return -1

	def _set_rate(self,rate):
		self.tts.Rate = (rate-50)/5

	def _set_pitch(self,value):
		#pitch is really controled with xml around speak commands
		self._pitch=value

	def _set_volume(self,value):
		self.tts.Volume = value

	def _initTts(self):
		self.tts=comtypes.client.CreateObject(COM_CLASS)
		outputDeviceID=nvwave.outputDeviceNameToID(config.conf["speech"]["outputDevice"], True)
		if outputDeviceID>=0:
			self.tts.audioOutput=self.tts.getAudioOutputs()[outputDeviceID]

	def _set_voice(self,value):
		v=self.tts.GetVoices()
		for i in range(len(v)):
			if value==v[i].Id:
				break
		else:
			# Voice not found.
			return
		self._initTts()
		self.tts.voice=v[i]

	def performSpeak(self,text,index=None,isCharacter=False):
		flags=constants.SVSFIsXML
		text=text.replace(u"\u2022", '') # bullet
		text=text.replace(u"\uf0b7", '') # bullet
		text=text.replace("<","&lt;")
		pitch=(self._pitch/2)-25
		if isinstance(index,int):
			bookmarkXML="<Bookmark Mark=\"%d\" />"%index
		else:
			bookmarkXML=""
		flags=constants.SVSFIsXML|constants.SVSFlagsAsync
		if isCharacter: text = "<spell>%s</spell>."%text
		self.tts.Speak("<pitch absmiddle=\"%s\">%s%s</pitch>"%(pitch,bookmarkXML,text),flags)

	def speakText(self,text,index=None):
		self.performSpeak(text,index)

	def speakCharacter(self,text,index=None):
		self.performSpeak(text,index,True)

	def cancel(self):
		#if self.tts.Status.RunningState == 2:
		self.tts.Speak(None, 1|constants.SVSFPurgeBeforeSpeak)

	def pause(self,switch):
		if switch:
			self.cancel()
