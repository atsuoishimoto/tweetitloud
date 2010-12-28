# _nvdajp_jtalk.py 
# -*- coding: utf-8 -*-
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.

# speech engine nvdajp_jtalk
# since 2010-08-31 by Takuya Nishimoto
# based on Open JTalk (bin/open_jtalk.c) http://github.com/nishimotz/libopenjtalk/
# based on NVDA (synthDrivers/_espeak.py)

from logHandler import log
import time
import threading
import Queue
import os
import codecs
import re
import string
#import unicodedata

import nvwave
#import nvdajp_dic

from _jtalk_core import *

_jtalk_voice_m001 = {"id": "V1", "name": "m001", "samp_rate": 16000, "fperiod":  80, "alpha": 0.42, "dir": r"synthDrivers\jtalk\voice"}
_jtalk_voice_mei  = {"id": "V2", "name": "mei", "samp_rate": 48000, "fperiod": 240, "alpha": 0.55, "dir": r"synthDrivers\jtalk\mei_normal"}
_jtalk_voices = [_jtalk_voice_m001, _jtalk_voice_mei]
voice_args = _jtalk_voice_m001

# if samp_rate==16000: normal speed = 80samples period
fperiod = 80

DEBUG_INFO = None # 1

CODE = 'shift_jis' # for mecab dic
DIC = r"synthDrivers\jtalk\dic"

#VOICE = voice_args['dir'] 
MECAB_DLL = r"synthDrivers\jtalk\libmecab.dll"
MECABRC = r"synthDrivers\jtalk\mecabrc"
JT_DLL = r"synthDrivers\jtalk\libopenjtalk.dll"

njd = NJD()
jpcommon = JPCommon()
engine = HTS_Engine()
libjt = None
predic = None
engdic = None
logwrite = None

lastIndex = None
currIndex = None

###########################################

def jtalk_refresh():
	libjt_refresh(libjt, engine, jpcommon, njd)
	Mecab_refresh()

def is_speaking_func():
	return isSpeaking

def jtalk_clear():
	libjt_clear(libjt, engine, jpcommon, njd)

def predic_build():
	global predic
	predic = [
# 		[re.compile(u'^ー'), u'チョーオン'],
# 		[re.compile(u'^？'), u'クエッションマーク'],
# 		[re.compile(u'^！'), u'びっくりマーク'],
# 		[re.compile(u'^ッ'), u'コモジノツ'], #カタカナ 
# 		[re.compile(u'^っ'), u'コモジノツ'], #ヒラガナ 
# 		[re.compile(u'^　'), u'ゼンカクスペース'],
# 		[re.compile(u'^。'), u'クテン'],
# 		[re.compile(u'^・'), u'ナカテン'],
# 		[re.compile(u'^、'), u'トウテン'],
# 		[re.compile(u'^．'), u'ピリオド'],
# 		[re.compile(u'^〔'), u'ヒラキキッコー'],

		[re.compile(u'　'), ' '],
		[re.compile(u'。'), ' '],
		[re.compile(u'・'), ' '],
		[re.compile(u'、'), ' '],
		[re.compile(u'：'), ' '],
		[re.compile(u'；'), ' '],
		[re.compile(u'｜'), '|'],
		[re.compile(u'－'), '-'],
		[re.compile(u'～'), u'から'],
		[re.compile(u'~'), ' '],
		[re.compile(u'\u2014'), ' '],
		[re.compile(u'\u2022'), ' '],
		[re.compile(u'≫'), ' '],
		[re.compile(u'「'), ''],
		[re.compile(u'」'), ''],
		[re.compile(u'【'), ''],
		[re.compile(u'】'), ''],
		[re.compile(u'’'), ''],
		[re.compile(u'＜'), ' '],
		[re.compile(u'＞'), ' '],

		[re.compile(u'マイ '), u'マイ'],
		[re.compile(u'コントロール パネル'), u'コントロールパネル'],
		[re.compile(u'タスク バー'), u'タスクバー'],
		
		[re.compile(u'の '), u'の'], # remove space "1の 7" -> "1の7"
		[re.compile(u'読み込み中'), u'ヨミコミチュー'],
		[re.compile(u'一行'), u'イチギョー'],
		[re.compile(u'1行'), u'イチギョー'],
		[re.compile(u'2行'), u'ニギョー'],
		[re.compile(u'3行'), u'サンギョー'],
		[re.compile(u'空行'), u'クーギョー'],
		[re.compile(u'行末'), u'ギョーマツ'],
		[re.compile(u'複数行'), u'フクスーギョー'],
		[re.compile(u'→'), u'ミギヤジルシ'],
		[re.compile(u'←'), u'ヒダリヤジルシ'],
		[re.compile(u'↑'), u'ウエヤジルシ'],
		[re.compile(u'↓'), u'シタヤジルシ'],
		[re.compile('\.\.\.'), u' テンテンテン '],
		[re.compile(u'孫正義'), u'ソンマサヨシ'],
		[re.compile(u'既読'), u'キドク'],
		[re.compile(u'新家'), u'シンケ'],
		[re.compile(u'障がい'), u'ショーガイ'],
		[re.compile(u'聾'), u'ロー'],
		[re.compile(u'盲'), u'モー'],

		[re.compile('\-'), ' '],
		[re.compile('\:'), 'コロン'],
		[re.compile('\/'), ' '],
		[re.compile('\\\\'), ' '],
		[re.compile('\+'), u'プラス'],
		[re.compile('\.'), u'ドット'],
		[re.compile('\_'), u'アンダースコア'],
		[re.compile('\='), u'イコール'],
		[re.compile('\;'), u'セミコロン'],
		[re.compile('\['), u' ダイカッコ '],
		[re.compile('\]'), u' '],
		[re.compile('\('), u' カッコ '],
		[re.compile('\)'), u' '],
		[re.compile('\|'), u'タテセン'],
		[re.compile('\#'), u'シャープ'],
		[re.compile('\"'), u'コーテーション'],
		[re.compile('\<'), u'ショーナリ'],
		[re.compile('\>'), u'ダイナリ'],
		[re.compile('\''), ' '],
	]

def predic_load():
	global predic
	if predic == None: predic_build()
	#global engdic
	#if engdic == None: engdic = engdic_load()

############################################
# based on _espeak.py (nvda)

isSpeaking = False
lastIndex = None
bgThread = None
bgQueue = None
player = None

class BgThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
		self.setDaemon(True)

	def run(self):
		global isSpeaking
		while True:
			func, args, kwargs = bgQueue.get()
			if not func:
				break
			try:
				func(*args, **kwargs)
			except:
				pass # log.error("Error running function from queue", exc_info=True)
			bgQueue.task_done()

def _execWhenDone(func, *args, **kwargs):
	global bgQueue
	# This can't be a kwarg in the function definition because it will consume the first non-keywor dargument which is meant for func.
	mustBeAsync = kwargs.pop("mustBeAsync", False)
	if mustBeAsync or bgQueue.unfinished_tasks != 0:
		# Either this operation must be asynchronous or There is still an operation in progress.
		# Therefore, run this asynchronously in the background thread.
		bgQueue.put((func, args, kwargs))
	else:
		func(*args, **kwargs)

# call from BgThread
def _speak(msg, index=None, isCharacter=False):
	global currIndex
	currIndex = index
	MSGLEN = 1000
	buff = create_string_buffer(MSGLEN)
	global isSpeaking
	isSpeaking = True
	# msg = unicodedata.normalize('NFKC', msg)
	# predic_load()
	for p in predic:
		try:
			msg = p[0].sub(p[1], msg)
		except:
			pass
	msg = msg.lower()
	#for p in engdic:
	#	try:
	#		msg = p[0].sub(p[1], msg)
	#	except:
	#		pass
	for m in string.split(msg, ' '):
		# if m == u'~': m = u'から'
		# if m == u'～': m = u'から'
# 		if not re.match('\d+', m):
# 			if nvdajp_dic.dic1.has_key(m):
# 				m = nvdajp_dic.dic1[m][4]
# 		if m == '': continue
		# for p in engdic:
		# 	try:
		# 		m = p[0].sub(p[1], m)
		# 	except:
		# 		pass
		text = m.encode(CODE)
		libjt_text2mecab(libjt, buff, text)
		if not isSpeaking: jtalk_refresh(); return
		str = buff.value
		if DEBUG_INFO: logwrite("_speak(%s) text2mecab(%s)" % (msg, str.decode(CODE)))
		[feature, size] = Mecab_analysis(str)
		if not isSpeaking: jtalk_refresh(); return
		if DEBUG_INFO: Mecab_print(feature, size, logwrite, CODE)
		libjt_synthesis(libjt, engine, jpcommon, njd, feature, size, fperiod, player.feed, is_speaking_func, 128) # player.feed() is called inside
		jtalk_refresh()
	global lastIndex
	lastIndex = currIndex
	currIndex = None
	isSpeaking = False

def speak(msg, index=None, isCharacter=False):
	if msg == '': return
	_execWhenDone(_speak, msg, index, isCharacter, mustBeAsync=True)

def stop():
	global isSpeaking, bgQueue
	# Kill all speech from now.
	# We still want parameter changes to occur, so requeue them.
	params = []
	stop_task_count = 0 # for log.info()
	try:
		while True:
			item = bgQueue.get_nowait() # [func, args, kwargs]
			if item[0] != _speak:
				params.append(item)
			else:
				stop_task_count = stop_task_count + 1
			bgQueue.task_done()
	except Queue.Empty:
		# Let the exception break us out of this loop, as queue.empty() is not reliable anyway.
		pass
	for item in params:
		bgQueue.put(item)
	isSpeaking = False
	if DEBUG_INFO: logwrite("stop: %d task(s) stopping" % stop_task_count)
	player.stop()

def pause(switch):
	player.pause(switch)

def initialize(voice_args_ = _jtalk_voice_m001):
	global bgThread, bgQueue, player, libjt, logwrite, voice_args
	voice_args = voice_args_
	player = nvwave.WavePlayer(channels=1, samplesPerSec=voice_args['samp_rate'], bitsPerSample=16)
	bgQueue = Queue.Queue()
	bgThread = BgThread()
	bgThread.start()
	#
	libjt = libjt_initialize(JT_DLL, njd, jpcommon, engine, **voice_args)
	libjt_load(libjt, voice_args['dir'], engine)
	Mecab_initialize(MECAB_DLL, libjt)
	Mecab_load(DIC, MECABRC)
	predic_load()
	logwrite = log.info
	if DEBUG_INFO: logwrite("jtalk for NVDA started")

def terminate():
	global bgThread, bgQueue, player
	stop()
	bgQueue.put((None, None, None))
	bgThread.join()
	bgThread = None
	bgQueue = None
	player.close()
	player = None
	#
	Mecab_clear()
	jtalk_clear()

def get_rate():
	if voice_args['samp_rate'] == 16000:
		return 160 - 2 * fperiod
	if voice_args['samp_rate'] == 48000:
		return int((240 - fperiod) / 1.5)
	return 0

def set_rate(rate):
	global fperiod
	if voice_args['samp_rate'] == 16000:
		fperiod = int(80 - int(rate) / 2) # 80..30
	if voice_args['samp_rate'] == 48000:
		fperiod = int(240 - 1.5 * rate) # 240..90
