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

import nvwave
from _jtalk_core import *

_jtalk_voice_m001 = {"id": "V1", "name": "m001", "samp_rate": 16000, "fperiod":  80, "alpha": 0.42, "dir": r"synthDrivers\jtalk\voice"}
_jtalk_voice_mei  = {"id": "V2", "name": "mei", "samp_rate": 48000, "fperiod": 240, "alpha": 0.55, "dir": r"synthDrivers\jtalk\mei_normal"}
_jtalk_voices = [_jtalk_voice_m001, _jtalk_voice_mei]
voice_args = _jtalk_voice_m001

# if samp_rate==16000: normal speed = 80samples period
fperiod = 80

# gain control
max_level = 32767
thres_level = 64
thres2_level = 16

DEBUG_INFO = None # 1 

# for mecab dic
CODE = 'cp932' # shift_jis
DIC = r"synthDrivers\jtalk\dic" 

MECAB_DLL = r"synthDrivers\jtalk\libmecab.dll"
MECABRC = r"synthDrivers\jtalk\mecabrc"
JT_DLL = r"synthDrivers\jtalk\libopenjtalk.dll"

njd = NJD()
jpcommon = JPCommon()
engine = HTS_Engine()
libjt = None
predic = None
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
		[re.compile(u'\ufffd'), u' '],
 		[re.compile(u'(\\?)々'), u'\\1\\1'],
		[re.compile('Welcome to'), u'ウェルカムトゥー'],
		[re.compile('mei'), u'メイ'],

		## zenkaku to hankaku convert
		[re.compile(u'　'), ' '],
		[re.compile(u'．'), '.'],
		[re.compile(u'，'), ','],
		[re.compile(u'；'), ';'],

		[re.compile(u'：'), u':'],
 		[re.compile(u'？'), u' '],
		[re.compile(u'／'), u'/'],
		[re.compile(u'｜'), '|'],
		[re.compile(u'－'), '-'],
		[re.compile(u'＝'), '='],
		[re.compile(u'＜'), '>'],
		[re.compile(u'＞'), '<'],

		## normalize phone number
		[re.compile(u'０'), u'0'],
		[re.compile(u'１'), u'1'],
		[re.compile(u'２'), u'2'],
		[re.compile(u'３'), u'3'],
		[re.compile(u'４'), u'4'],
		[re.compile(u'５'), u'5'],
		[re.compile(u'６'), u'6'],
		[re.compile(u'７'), u'7'],
		[re.compile(u'８'), u'8'],
		[re.compile(u'９'), u'9'],
		[re.compile(u'(\\d+)・(\\d+)'), u'\\1.\\2'],
		[re.compile(u'(\\d+)．(\\d+)'), u'\\1.\\2'],
		[re.compile(u'(\\d+)（(\\d+)'), '\\1(\\2'],
		[re.compile(u'(\\d+)）(\\d+)'), '\\1)\\2'],
		[re.compile(u'(\\d+)\\((\\d+)\\)(\\d+)'), u'\\1-\\2-\\3'],

		[re.compile(u'(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０\\1 ０\\2 ０\\3ノ  ０\\4 ０\\5 ０\\6 ０\\7ノ  ０\\8 ０\\9 ０\\10 ０\\11 '],
		
		[re.compile(u'(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０\\1 ０\\2 ０\\3ノ  ０\\4 ０\\5 ０\\6ノ  ０\\7 ０\\8 ０\\9 ０\\10 '],
		
		[re.compile(u'(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０\\1 ０\\2ノ  ０\\3 ０\\4 ０\\5 ０\\6ノ  ０\\7 ０\\8 ０\\9 ０\\10 '],
		
		[re.compile(u'(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０\\1 ０\\2 ０\\3ノ  ０\\4 ０\\5 ０\\6ノ  ０\\7 ０\\8 ０\\9 ０\\10 '],
		
		[re.compile(u'(\\d)(\\d)(\\d)(\\d)\\-(\\d)(\\d)\\-(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０\\1 ０\\2 ０\\3 ０\\4ノ  ０\\5 ０\\6ノ  ０\\7 ０\\8 ０\\9 ０\\10 '],
		
		[re.compile(u'0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), 
			u'  ０0 ０\\1 ０\\2ノ  ０\\3 ０\\4 ０\\5ノ  ０\\6 ０\\7 ０\\8 ０\\9 '],
		
		[re.compile(u'(\\D)0(\\d)(\\d)(\\d)'), u'\\1  ０0 ０\\2 ０\\3 ０\\4 '],
		[re.compile(u'(\\D)0(\\d)(\\d)'), u'\\1  ０0 ０\\2 ０\\3 '],
		[re.compile(u'(\\D)0(\\d)'), u'\\1  ０0 ０\\2 '],

		[re.compile(u'(\\d+)\\.00000(\\d+)'), u' \\1テンレイレイレイレイレイ\\2 '],
		[re.compile(u'(\\d+)\\.0000(\\d+)'), u' \\1テンレイレイレイレイ\\2 '],
		[re.compile(u'(\\d+)\\.000(\\d+)'), u' \\1テンレイレイレイ\\2 '],
		[re.compile(u'(\\d+)\\.00(\\d+)'), u' \\1テンレイレイ\\2 '],
		[re.compile(u'(\\d+)\\.0(\\d+)'), u' \\1テンレイ\\2 '],
		[re.compile(u'(\\d+)\\.(\\d+)'), u' \\1テン\\2 '],

		[re.compile(u' ０0'), u'ゼロ'],
		[re.compile(u' ０1'), u'イチ'],
		[re.compile(u' ０2'), u'ニイ'],
		[re.compile(u' ０3'), u'サン'],
		[re.compile(u' ０4'), u'ヨン'],
		[re.compile(u' ０5'), u'ゴオ'],
		[re.compile(u' ０6'), u'ロク'],
		[re.compile(u' ０7'), u'ナナ'],
		[re.compile(u' ０8'), u'ハチ'],
		[re.compile(u' ０9'), u'キュウ'],

		[re.compile(u'(（|\()月(）|\))'), u' カッコゲツヨー '],
		[re.compile(u'(（|\()火(）|\))'), u' カッコカヨー '],
		[re.compile(u'(（|\()水(）|\))'), u' カッコスイヨー '],
		[re.compile(u'(（|\()木(）|\))'), u' カッコモクヨー '],
		[re.compile(u'(（|\()金(）|\))'), u' カッコキンヨー '],
		[re.compile(u'(（|\()土(）|\))'), u' カッコドヨー '],
		[re.compile(u'(（|\()日(）|\))'), u' カッコニチヨー '],

		[re.compile(u'(\\d+)\\:00\\:00'), u'\\1ジレーフンレービョウ'],
		[re.compile(u'(\\d+)\\:(\\d+)\\:00'), u'\\1ジ\\2フンレービョウ'],
		[re.compile(u'(\\d+)\\:00\\:(\\d+)'), u'\\1ジレイフン\\2ビョウ'],
		[re.compile(u'(\\d+)\\:00'), u'\\1ジレイフン'],
		[re.compile(u'(\\d+)\\:(\\d+)\\:(\\d+)'), u'\\1ジ\\2フン\\3ビョウ'],
		
		[re.compile(u'19\\:(\\d+)'), u'ジュークジ\\1フン'],
		[re.compile(u'9\\:(\\d+)分'), u'クジ\\1フン'],
		[re.compile(u'9\\:(\\d+)'), u'クジ\\1フン'],
		[re.compile(u'(\\d+)\\:(\\d+)'), u'\\1ジ\\2フン'],
		
		[re.compile(u'(\\d\\d\\d\\d)\\-(\\d\\d)\\-(\\d\\d)'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'(\\d+)\\/(\\d+)\\/(\\d+)'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'(\\d{1,2})\\/(\\d{1,2})'), u'\\1ガツ\\2ニチ'],
		[re.compile(u'(\\d)\\,(\\d\\d\\d)'), u'\\1\\2'],
		[re.compile(u'(\\d\\d)\\,(\\d\\d\\d)'), u'\\1\\2'],
		[re.compile(u'(\\d\\d\\d)\\,(\\d\\d\\d)'), u'\\1\\2'],

		[re.compile(u'(\\d+)MB'), u'\\1メガバイト'],

		## zenkaku
		[re.compile(u'。'), ' '],
		[re.compile(u'、'), ' '],
		[re.compile(u'…'), ' '],
		[re.compile(u'・'), u' '],
		[re.compile(u'’'), ''],
		[re.compile(u'（'), ' '],
		[re.compile(u'）'), ' '],
		[re.compile(u'≫'), ' '],
		[re.compile(u'「'), ' '],
		[re.compile(u'」'), ' '],
		[re.compile(u'【'), ' '],
		[re.compile(u'】'), ' '],
		[re.compile(u'●'), ' '],
		[re.compile(u'◎'), ' '],
		[re.compile(u'◆'), ' '],
		
		## hankaku
		[re.compile(u'>'), ' '],
		[re.compile(u'<'), ' '],
		[re.compile(u'='), ' = '],

		# trim space
		[re.compile(u'マイ '), u'マイ'],
		[re.compile(u'コントロール パネル'), u'コントロールパネル'],
		[re.compile(u'タスク バー'), u'タスクバー'],
		[re.compile(u'の '), u'の'], # remove space "1の 7" -> "1の7"
		[re.compile(u' 側'), u' ガワ'],
		
		[re.compile(u'→'), u'ミギヤジルシ'],
		[re.compile(u'←'), u'ヒダリヤジルシ'],
		[re.compile(u'↑'), u'ウエヤジルシ'],
		[re.compile(u'↓'), u'シタヤジルシ'],
		[re.compile('\.\.\.'), u' テンテンテン '],

		[re.compile('\\/'), ' '],
		[re.compile('\\\\'), ' '],
		[re.compile('\\:'), u' コロン '],
		[re.compile('\\+'), u'プラス'],
		[re.compile('\\.'), u'ドット'],
		[re.compile('\\_'), u' アンダースコア '],
		[re.compile('\\='), u'イコール'],
		[re.compile('\\;'), u'セミコロン'],
		[re.compile('\\['), u' ダイカッコ '],
		[re.compile('\\]'), u' '],
		[re.compile('\\('), u' カッコ '],
		[re.compile('\\)'), u' '],
		[re.compile('\\|'), u'タテセン'],
		[re.compile('\\#'), u' シャープ '],
		[re.compile('\\"'), u'コーテーション'],
		[re.compile('\\<'), u'ショーナリ'],
		[re.compile('\\>'), u'ダイナリ'],
		[re.compile('\\\''), ' '],
		
		[re.compile(u'～'), u'から'],
		[re.compile(u'\~'), u'から'],
	]

def predic_load():
	global predic
	if predic == None: predic_build()

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
				log.error("Error running function from queue", exc_info=True) # pass 
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
	for p in predic:
		try:
			msg = re.sub(p[0], p[1], msg) #msg = p[0].sub(p[1], msg)
		except:
			pass
	msg = msg.lower()
	if DEBUG_INFO: logwrite("_speak(%s)" % msg)
	for m in string.split(msg):
		if len(m) > 0:
			try:
				if DEBUG_INFO: logwrite("text2mecab(%s)" % m)
				text = m.encode(CODE, 'ignore')
				libjt_text2mecab(libjt, buff, text); str = buff.value
				if not isSpeaking: jtalk_refresh(); return
				if DEBUG_INFO: logwrite("text2mecab result: %s" % str.decode(CODE, 'ignore'))
				[feature, size] = Mecab_analysis(str)
				if DEBUG_INFO: logwrite("Mecab_analysis done.")
				if not isSpeaking: jtalk_refresh(); return
				if DEBUG_INFO: Mecab_print(feature, size, logwrite, CODE)
				libjt_synthesis(libjt, engine, jpcommon, njd, feature, size, 
					fperiod_ = fperiod, 
					feed_func_ = player.feed, # player.feed() is called inside
					is_speaking_func_ = is_speaking_func, 
					thres_ = thres_level,
					thres2_ = thres2_level,
					level_ = max_level,
					logwrite_ = logwrite)
				if DEBUG_INFO: logwrite("libjt_synthesis done.")
				jtalk_refresh()
				if DEBUG_INFO: logwrite("jtalk_refresh done.")
			except Exception, e:
				if DEBUG_INFO: logwrite(e)
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

def get_rate():
	if voice_args['samp_rate'] == 16000:
		return 160 - 2 * fperiod
	if voice_args['samp_rate'] == 48000:
		return int((240 - fperiod) / 1.5)
	return 0

def set_volume(vol):
	global max_level, thres_level
	max_level = int(326.67 * vol + 100) # 100..32767
	thres_level = 64
	thres2_level = 16
