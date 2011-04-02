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
thres_level = 128
thres2_level = 128

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
		### Unicode REPLACEMENT CHARACTER
		[re.compile(u'\ufffd'), u' '],
		### zenkaku space normalize
		[re.compile(u'　'), u' '],
		
		## 人々 昔々 家々 山々 
		## Welcome to NVDA
		## m001 mei
		## tab
 		[re.compile(u'(.)々'), u'\\1\\1'],
		[re.compile('Welcome to'), u'ウェルカムトゥー'],
		[re.compile('^mei$'), u'メイ'],
		[re.compile('\\btab\\b'), u'タブ'],
		## 行操作 行をブックマーク 行を隠す
		[re.compile(u'行操作'), u'ギョーソーサ'],
		[re.compile(u'行をブックマーク'), u'ギョーをブックマーク'],
		[re.compile(u'行を隠す'), u'ギョーを隠す'],
		## 被災された方へ 圏内の方へ 支援をお考えの方へ 少しでも
		[re.compile(u'された方'), u'されたかた'],
		[re.compile(u'圏内の方'), u'圏内のかた'],
		[re.compile(u'お考えの方'), u'お考えのかた'],
		[re.compile(u'少しでも'), u'すこしでも'],
		## 月～日 20:55 ～ 21:00
		[re.compile(u'月～日'), u'ゲツからニチ'],
		## 空要素タグ
		[re.compile(u'空要素'), u'カラ要素'],
		## ニコ生視聴中
		[re.compile(u'ニコ生'), u'ニコナマ'],
		## スリーマイル島原発
		[re.compile(u'スリーマイル島原発'), u'スリーマイルとうゲンパツ'],

		### trim space
		[re.compile(u'マイ '), u'マイ'],
		[re.compile(u'コントロール パネル'), u'コントロールパネル'],
		[re.compile(u'タスク バー'), u'タスクバー'],
		[re.compile(u'の '), u'の'], # remove space "1の 7" -> "1の7"
		[re.compile(u' 側'), u' ガワ'],
		
		## isolated hiragana HA (mecab replaces to WA)
		## は 
		[re.compile(u'^は'), u'ハ'],
		[re.compile(u'\\sは'), u'ハ'],
		
		### zenkaku symbols convert
		## ２０１１．０３．１１
		## １，２３４円
		## １３：３４
		[re.compile(u'．'), u'.'],
		[re.compile(u'，'), u','],
		[re.compile(u'；'), u';'],
		[re.compile(u'：'), u':'],
 		[re.compile(u'？'), u' '],
		[re.compile(u'／'), u'/'],
		[re.compile(u'｜'), u'|'],
		[re.compile(u'－'), u'-'],
		[re.compile(u'＝'), u'='],
		[re.compile(u'＜'), u'>'],
		[re.compile(u'＞'), u'<'],
		[re.compile(u'％'), u'%'],
		[re.compile(u'＊'), u'*'],
		[re.compile(u'（'), u'('],
		[re.compile(u'）'), u')'],
		[re.compile(u'［'), u'['],
		[re.compile(u'］'), u']'],
		[re.compile(u'”'), u'"'],

		### zenkaku alphabet convert
		[re.compile(u'Ａ'), u'A'],
		[re.compile(u'Ｂ'), u'B'],
		[re.compile(u'Ｃ'), u'C'],
		[re.compile(u'Ｄ'), u'D'],
		[re.compile(u'Ｅ'), u'E'],
		[re.compile(u'Ｆ'), u'F'],
		[re.compile(u'Ｇ'), u'G'],
		[re.compile(u'Ｈ'), u'H'],
		[re.compile(u'Ｉ'), u'I'],
		[re.compile(u'Ｊ'), u'J'],
		[re.compile(u'Ｋ'), u'K'],
		[re.compile(u'Ｌ'), u'L'],
		[re.compile(u'Ｍ'), u'M'],
		[re.compile(u'Ｎ'), u'N'],
		[re.compile(u'Ｏ'), u'O'],
		[re.compile(u'Ｐ'), u'P'],
		[re.compile(u'Ｑ'), u'Q'],
		[re.compile(u'Ｒ'), u'R'],
		[re.compile(u'Ｓ'), u'S'],
		[re.compile(u'Ｔ'), u'T'],
		[re.compile(u'Ｕ'), u'U'],
		[re.compile(u'Ｖ'), u'V'],
		[re.compile(u'Ｗ'), u'W'],
		[re.compile(u'Ｘ'), u'X'],
		[re.compile(u'Ｙ'), u'Y'],
		[re.compile(u'Ｚ'), u'Z'],
		
		[re.compile(u'ａ'), u'a'],
		[re.compile(u'ｂ'), u'b'],
		[re.compile(u'ｃ'), u'c'],
		[re.compile(u'ｄ'), u'd'],
		[re.compile(u'ｅ'), u'e'],
		[re.compile(u'ｆ'), u'f'],
		[re.compile(u'ｇ'), u'g'],
		[re.compile(u'ｈ'), u'h'],
		[re.compile(u'ｉ'), u'i'],
		[re.compile(u'ｊ'), u'j'],
		[re.compile(u'ｋ'), u'k'],
		[re.compile(u'ｌ'), u'l'],
		[re.compile(u'ｍ'), u'm'],
		[re.compile(u'ｎ'), u'n'],
		[re.compile(u'ｏ'), u'o'],
		[re.compile(u'ｐ'), u'p'],
		[re.compile(u'ｑ'), u'q'],
		[re.compile(u'ｒ'), u'r'],
		[re.compile(u'ｓ'), u's'],
		[re.compile(u'ｔ'), u't'],
		[re.compile(u'ｕ'), u'u'],
		[re.compile(u'ｖ'), u'v'],
		[re.compile(u'ｗ'), u'w'],
		[re.compile(u'ｘ'), u'x'],
		[re.compile(u'ｙ'), u'y'],
		[re.compile(u'ｚ'), u'z'],
		
		## 無線LAN
		[re.compile(u'無線LAN'), u'無線ラン'],
		
		### zenkaku numbers convert
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
		
		## 4/1・17:30
		[re.compile(u'(\\d{1,2})/(\\d{1,2})・(\\d{1,2}):(\\d{1,2})'), u'\\1ガツ\\2ニチ\\3:\\4'],
		## ０３・１２３４・５６７８
		[re.compile(u'(\\d{2,4})・(\\d{1,4})・(\\d{4})'), u'\\1-\\2-\\3'],
		## ３・１２３４
		[re.compile(u'(\\d+)・(\\d+)'), u'\\1.\\2'],
		
		## 59 名
		[re.compile(u'(\\d) 名'), u'\\1名'],
		
		## 1MB 10MB 1.2MB 0.5MB 321.0MB 123.45MB
		[re.compile(u'(\\d+)MB'), u'\\1メガバイト'],

		## (月) (火) (水) (木) (金) (土) (日)
		[re.compile(u'(\()月(\))'), u' カッコゲツヨー '],
		[re.compile(u'(\()火(\))'), u' カッコカヨー '],
		[re.compile(u'(\()水(\))'), u' カッコスイヨー '],
		[re.compile(u'(\()木(\))'), u' カッコモクヨー '],
		[re.compile(u'(\()金(\))'), u' カッコキンヨー '],
		[re.compile(u'(\()土(\))'), u' カッコドヨー '],
		[re.compile(u'(\()日(\))'), u' カッコニチヨー '],

		## 12:00:00
		[re.compile(u'(\\d{1,2})\\:00\\:00'), u'\\1ジレーフンレービョー'],
		## 12:01:00
		## 12:34:00
		[re.compile(u'(\\d{1,2})\\:(\\d{1,2})\\:00'), u'\\1ジ\\2フンレービョー'],
		## 12:00:59
		[re.compile(u'(\\d{1,2})\\:00\\:(\\d{1,2})'), u'\\1ジレーフン\\2ビョー'],
		## 12:00
		## 19:00 
		[re.compile(u'(\\d{1,2})\\:00'), u'\\1ジレーフン'],
		## 1:02:03
		[re.compile(u'(\\d{1,2})\\:(\\d{1,2})\\:(\\d{1,2})'), u'\\1ジ\\2フン\\3ビョー'],
		
		## 19:05 
		## 19:50
		[re.compile(u'19\\:(\\d{2})'), u'ジュークジ\\1フン'],
		## 9:05分
		[re.compile(u'9\\:(\\d{2})分'), u'クジ\\1フン'],
		## 9:05
		[re.compile(u'9\\:(\\d{2})'), u'クジ\\1フン'],
		## 0:00 0:01 1:01 2:09 
		## 3:18
		## 00:00 00:01 01:01 02:09 03:18 
		## 0:0 0:1 1:1 9:9 (not time)
		[re.compile(u'(\\d{1,2})\\:(\\d{2})'), u'\\1ジ\\2フン'],
		
		## 2000-01-01 2011-03-11 2000-01-10 2000-10-10
		## 9999-99-99
		## 2000/01/01 2011/03/11 2000/01/10 
		## 2000/1/1 2000/01/1 2000/1/01
		## 2000/10/10 9999/99/99
		## 1999.3.11 
		## 1999.1.1 
		## 1999.1.01
		## 1999.03.11
		## 1999.10.11
		## 2011.3.11 
		## 2011.03.11 
		## 2011.10.11 
		[re.compile(u'\\b([1-9]\\d{3})\\-(\\d{2})\\-(\\d{2})\\b'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'\\b([1-9]\\d{3})\\.(\\d)\\.(\\d{1,2})\\b'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'\\b([1-9]\\d{3})\\.0(\\d)\\.(\\d{2})\\b'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'\\b([1-9]\\d{3})\\.(\\d{2})\\.(\\d{2})\\b'), u'\\1ネン\\2ガツ\\3ニチ'],
		[re.compile(u'\\b([1-9]\\d{3})\\/(\\d{1,2})\\/(\\d{1,2})\\b'), u'\\1ネン\\2ガツ\\3ニチ'],
		## 1/1 1/100 500/3 (not date)
		## 3/11 12/1
		## 10/1 10/11 12/31
		## 01/01 03/11 
		## 13/00 99/00 12/32 
		[re.compile(u'\\b(\\d{1})\\/(\\d{2})\\b'), u'\\1ガツ\\2ニチ'],
		[re.compile(u'\\b(\\d{2})\\/(\\d{1})\\b'), u'\\1ガツ\\2ニチ'],
		[re.compile(u'\\b(\\d{2})\\/(\\d{2})\\b'), u'\\1ガツ\\2ニチ'],
		[re.compile(u'\\b(\\d+)\\/(\\d+)\\b'), u'\\1スラッシュ\\2'],

		## 1.2.3
		[re.compile(u'\\b(\\d+)\\.(\\d+)\\.(\\d+)\\b'), u'\\1テン\\2テン\\3'],

		## 1,234
		## 1,234,567
		## 1,234,567,890
		## 1,23 = ichi comma niju san
		## 1,0 = ichi comma zero
		[re.compile(u'(\\d)\\,(\\d{3})'), u'\\1\\2'],
		[re.compile(u'(\\d{2})\\,(\\d{3})'), u'\\1\\2'],
		[re.compile(u'(\\d{3})\\,(\\d{3})'), u'\\1\\2'],
		[re.compile(u'(\\d)\\,(\\d{1,2})'), u'\\1カンマ\\2'],
		
		### normalize phone number
		## 023(4567)0900
		## 0123(4567)0900
		## 01233(4567)0900
		## 023-4567-0900
		## 023-400-0900
		## 03-4567-0100
		## 0123-45-0100
		[re.compile(u'(\\d{1,4})\\((\\d{1,4})\\)(\\d{4})'), u'\\1-\\2-\\3'],
		
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
		
		#[re.compile(u'([^\\.]*)0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), 
		#	u'\\1  ０0 ０\\2 ０\\3ノ  ０\\4 ０\\5 ０\\6ノ  ０\\7 ０\\8 ０\\9 ０\\10 '],
		
		### numbers with dot and zeros
		## 1.0000012345
		## 1.000012345
		## 1.00012345
		## 1.0012345
		## 1.012345
		## 1.12345
		## 1.1234
		## 1.1100
		## 1.110
		## 1.123
		## 1.000001 1.000000
		## 1.00001 1.00000
		## 1.0001 1.0000
		## 1.001 1.000 
		## 1.01 1.00 1.11
		## 1.1 1.0
		## 123.45MB
		## a0123
		## a0001
		## a001
		## a01
		## 0123456789
		## 012345678
		## 01234567
		## 0123456
		## 012345
		## 01234
		## 0123
		## 012
		## 01	
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 ０\\6 ０\\7 ０\\8 ０\\9 ０\\10 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 ０\\6 ０\\7 ０\\8 ０\\9 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 ０\\6 ０\\7 ０\\8 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 ０\\6 ０\\7 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 ０\\6 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 ０\\5 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 ０\\4 '],
		[re.compile(u'(\\d+)\\.(\\d)(\\d)'), u' \\1テン ０\\2 ０\\3 '],
		[re.compile(u'(\\d+)\\.(\\d)'), u' \\1テン ０\\2 '],

		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4  ０\\5  ０\\6  ０\\7  ０\\8  ０\\9 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4  ０\\5  ０\\6  ０\\7  ０\\8 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4  ０\\5  ０\\6  ０\\7 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4  ０\\5  ０\\6 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4  ０\\5 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3  ０\\4 '],
		[re.compile(u'\\b0(\\d)(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2  ０\\3 '],
		[re.compile(u'\\b0(\\d)(\\d)'), u'  ０0  ０\\1  ０\\2 '],
		[re.compile(u'\\b0(\\d)'), u'  ０0  ０\\1 '],

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
		
		### zenkaku symbols: ignore (split engine input)
		### あ…い≫う【え】お●か◎き◆くけこ
		### 阪神・淡路
		[re.compile(u'。'), u'。 '],
		[re.compile(u'、'), u'、 '],
		[re.compile(u'…'), u'… '],
		[re.compile(u'≫'), u'≫ '],
		[re.compile(u'「'), u' 「'],
		[re.compile(u'」'), u'」 '],
		[re.compile(u'【'), u' 【'],
		[re.compile(u'】'), u'】 '],
		[re.compile(u'●'), u'● '],
		[re.compile(u'◎'), u'◎ '],
		[re.compile(u'◆'), u'◆ '],
		[re.compile(u'・'), u'・ '],
		
		### zenkaku symbols: pronunciation
		### → ← ↑ ↓
		[re.compile(u'→'), u'ミギヤジルシ'],
		[re.compile(u'←'), u'ヒダリヤジルシ'],
		[re.compile(u'↑'), u'ウエヤジルシ'],
		[re.compile(u'↓'), u'シタヤジルシ'],
		
		### hankaku symbols: ignore / pronunciation
		### ... .次 a.b
		[re.compile('\.\.\.'), u'テンテンテン '],
		[re.compile(u'\\.次'), u'ドットツギ'],
		[re.compile('\\.'), u'ドット'],
		
		## http://abc.def/file.html
		## 1+1-2=0 
		## @kantei_saigai
		## *important*
		## getchar();
		## a | b
		## 'a'
		## "a"
		[re.compile('\\/'), u'スラッシュ'],
		[re.compile('\\:'), u'コロン'],
		[re.compile('\\+'), u'プラス'],
		[re.compile('\\-'), u'ハイフン'],
		[re.compile('\\_'), u'カセン'],
		[re.compile('\\='), u'イコール'],
		[re.compile('\\%'), u'パーセント'],
		[re.compile('\\*'), u'アスタリスク'],
		[re.compile('\\;'), u'セミコロン'],
		[re.compile('\\|'), u'タテセン'],
		[re.compile('\\#'), u'シャープ'],
		[re.compile('\\"'), u'コーテーション'],
		[re.compile('\\\''), u'アポストロフィ'],
		[re.compile(','), u' カンマ '],

		## [1] (2) <3>
		## ［１］　（２）　＜３＞
		[re.compile('\\['), u' ダイカッコヒラキ '],
		[re.compile('\\]'), u' ダイカッコトジ '],
		[re.compile('\\('), u' カッコヒラキ '],
		[re.compile('\\)'), u' カッコトジ '],
		[re.compile('\\<'), u' ショーナリ '],
		[re.compile('\\>'), u' ダイナリ '],
		
		## １～２　１〜２　1~2
		[re.compile(u'～'), u'から'],
		[re.compile(u'〜'), u'から'],
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
	lw = None
	#if DEBUG_INFO: lw = logwrite
	for m in string.split(msg):
		if len(m) > 0:
			try:
				#if DEBUG_INFO: logwrite("text2mecab(%s)" % m)
				text = m.encode(CODE, 'ignore')
				libjt_text2mecab(libjt, buff, text); str = buff.value
				if not isSpeaking: jtalk_refresh(); return
				#if DEBUG_INFO: logwrite("text2mecab result: %s" % str.decode(CODE, 'ignore'))
				[feature, size] = Mecab_analysis(str)
				#if DEBUG_INFO: logwrite("Mecab_analysis done.")
				if not isSpeaking: jtalk_refresh(); return
				#if DEBUG_INFO: Mecab_print(feature, size, logwrite, CODE)
				libjt_synthesis(libjt, engine, jpcommon, njd, feature, size, 
					fperiod_ = fperiod, 
					feed_func_ = player.feed, # player.feed() is called inside
					is_speaking_func_ = is_speaking_func, 
					thres_ = thres_level,
					thres2_ = thres2_level,
					level_ = max_level,
					logwrite_ = lw)
				#if DEBUG_INFO: logwrite("libjt_synthesis done.")
				jtalk_refresh()
				#if DEBUG_INFO: logwrite("jtalk_refresh done.")
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
	global max_level, thres_level, thres2_level
	max_level = int(326.67 * vol + 100) # 100..32767
	thres_level = 128
	thres2_level = 128
