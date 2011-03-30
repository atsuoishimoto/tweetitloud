# coding: UTF-8
#brailleDisplayDrivers/DirectBM.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2009 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
# Masataka.Shinke
import time
import binascii

import DirectBM_dic         # Masataka.Shinke

try:
	import ui					# NVDA
	import config			# NVDA
	import queueHandler			# NVDA
	from logHandler import log	# NVDA
except:
	pass

from ctypes import *
from ctypes.wintypes import *

keybd_event = windll.user32.keybd_event
KEYEVENTF_KEYDOWN = 0 
KEYEVENTF_KEYUP = 2
VK_BACK=8
VK_TAB=9
VK_RETURN = 13
VK_SPACE  = 32
VK_LEFT   = 37
VK_UP     = 38
VK_RIGHT  = 39
VK_DOWN   = 40
VK_SELECT=41
VK_F1=0x70
VK_F2=0x71
VK_F3=0x72
VK_F4=0x73
VK_CONTROL=0x11
VK_MENU=0x12 
VK_LWIN=0x5B
VK_KANJI=0x19

global gnEquipment
gnEquipment = 0

global gnDispMode
gnDispMode = 0x0002

global WINFUNC1
global py_bmStartInProcess
global WINFUNC2
global py_bmStartDisplayMode2
global DLL

global DispSize
DispSize=0

global RunFlag
RunFlag = True

global WFlag
WFlag = False

global SFlag
SFlag = False


global dll
try:
    dll = windll.LoadLibrary("lib\DirectBM.dll")
except ImportError:
    pass

def f_terminate():
	# ディスプレイモード終了
	#dll.bmEndDisplayMode()
	#time.sleep(1)
	# リリース
	#dll.bmEnd()
	global WFlag
	WFlag=False

def check():
	global WINFUNC1
	global py_bmStartInProcess
	global WINFUNC2
	global py_bmStartDisplayMode2
	global SFlag

	global RunFlag
	RunFlag = True

	if(SFlag==False):
		dll.IsKbdcInstalled("SOFTWARE\\KGS\\KBDC110")
		# ステータス取得コールバック
		WINFUNC1 = WINFUNCTYPE(c_void_p,c_int, c_int)
		py_bmStartInProcess = WINFUNC1(bmStartInProcess)

		# ディスプレイモード
		WINFUNC2 = WINFUNCTYPE(c_void_p,POINTER(c_uint32))
		py_bmStartDisplayMode2 = WINFUNC2(bmStartDisplayMode2)

		text=u"BMシリーズ機器"
		#for i in range(0,7):
		#	if(dll.bmStartInProcess("nvdajp",text.encode('shift-jis'),i,3,py_bmStartInProcess,False)):
		#		j=0
		#		while RunFlag:
		#			j+=1;
		#			if(j>5):
		#				break
		#			time.sleep(1)
		#		if(SFlag==True):
		#			break

		if(dll.bmStartInProcess("nvdajp",text.encode('shift-jis'),config.conf["braille"]["nvdajpComPort"]-1,3,py_bmStartInProcess,False)):
			time.sleep(1)
		
		if(SFlag==True):
			dll.bmStartDisplayMode2(gnDispMode,py_bmStartDisplayMode2)

	return SFlag


def f_init():
	global WFlag
	if(SFlag==False):
		WFlag=False
		return
	WFlag=True

def sp(Values):
	if(WFlag == True):
		# ディスプレイ出力
		Value=u''
		try:
			Value=DirectBM_dic.Ret2(DirectBM_dic.wakach(Values))
		except:
			Value=u''
		buff1=create_string_buffer(Value[:DispSize],80)
		buff2=create_string_buffer('',80)
		try:
			dll.bmDisplayData(buff1,buff2,DispSize)
		except:
			pass
def wakach(Values):
    return DirectBM_dic.wakach(Values)

def disp(Values):
	if(WFlag == True):
		# ディスプレイ出力
		buff1=create_string_buffer(DirectBM_dic.Ret2(Values),80)
		buff2=create_string_buffer('',80)
		try:
			dll.bmDisplayData(buff1,buff2,DispSize)
		except:
			pass
		try:
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message,Values)
		except:
			pass
		

#　ステータス取得コールバック
def bmStartInProcess(nStatus, nDispSize):
	global RunFlag
	global SFlag

	global DispSize
	DispSize=nDispSize

	# 定数
	BMDRVS_DISCONNECTED = 0
	BMDRVS_CONNECTED = 1
	BMDRVS_DRIVER_CANNOT_OPEN = 2
	BMDRVS_INVALID_DRIVER = 3
	BMDRVS_OPEN_PORT_FAILED = 4
	BMDRVS_CREATE_THREAD_FAILED = 5
	BMDRVS_CHECKING_EQUIPMENT = 6
	BMDRVS_UNKNOWN_EQUIPMENT = 7
	BMDRVS_PORT_RELEASED = 8
	BMDRVS_MAX = 9

	if nStatus == BMDRVS_DRIVER_CANNOT_OPEN:
		disp(u"対応するドライバが起動できませんでした。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_INVALID_DRIVER:
		disp(u"不適切なドライバがインストールされています。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_OPEN_PORT_FAILED:
		disp(u"通信ポートが開けませんでした。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_CREATE_THREAD_FAILED:
		disp(u"通信スレッドの起動に失敗しました。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_OPEN_PORT_FAILED:
		disp(u"通信ポートが開けませんでした。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_CREATE_THREAD_FAILED:
		disp(u"通信スレッドの起動に失敗しました。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_UNKNOWN_EQUIPMENT:
		disp(u"ＢＭシリーズ機器が正しく接続されていません。接続をもう一度確認してください。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_CONNECTED:
		#print "StatusChanged: BMDRVS_CONNECTED (接続しました(点字表示部: ",nDispSize,"マス)。)"
		disp(u"接続しました")
		RunFlag = False
		SFlag = True
	elif nStatus == BMDRVS_DISCONNECTED:
		disp(u"切断しました。")
		RunFlag = False
		SFlag = False
	elif nStatus == BMDRVS_PORT_RELEASED:
		disp(u"ＣＯＭＭポートを解放しました。")
		RunFlag = False
		SFlag = False

# ディスプレイモードコールバック
global LastKey
LastKey =0x00
def bmStartDisplayMode2(lpKeys):
	global gnEquipment
	global LastKey
	if(gnEquipment == 0):
		#print "KeyEvent:",lpKeys[0],lpKeys[1],lpKeys[2]
		if((lpKeys[0]&0x0000000f)==0x00000000):
			if((lpKeys[0]&0x00010000)!=0):
				#disp(u'コントロール')
				keybd_event(VK_LWIN,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_LWIN,0,KEYEVENTF_KEYUP,0)
				#print u"[CTRL]",
			if((lpKeys[0]&0x00400000)!=0):
				#disp(u'セレクト')
				keybd_event(VK_MENU,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_MENU,0,KEYEVENTF_KEYUP,0)
				#keybd_event(VK_SELECT,0,KEYEVENTF_KEYDOWN,0)
				#print u"[SEL]",
			if((lpKeys[0]&0x00800000)!=0):
				#disp(u'リード')
				keybd_event(VK_TAB,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_TAB,0,KEYEVENTF_KEYUP,0)
				#print u"[READ]",
			if((lpKeys[0]&0x00020000)!=0):
				#disp(u'オルト')
				keybd_event(VK_KANJI,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_KANJI,0,KEYEVENTF_KEYUP,0)
				#print u"[ALT]",
			if((lpKeys[0]&0x00040000)!=0):
				#disp(u'ファンクション１')
				#keybd_event(VK_F1,0,KEYEVENTF_KEYDOWN,0)
				#keybd_event(VK_F1,0,KEYEVENTF_KEYUP,0)
				keybd_event(VK_BACK,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_BACK,0,KEYEVENTF_KEYUP,0)
				#print u"[F1]",
			if((lpKeys[0]&0x00100000)!=0):
				#disp(u'ファンクション２')
				#keybd_event(VK_F2,0,KEYEVENTF_KEYDOWN,0)
				#keybd_event(VK_F2,0,KEYEVENTF_KEYUP,0)
				#print u"[F2]",
				pass
			if((lpKeys[0]&0x00200000)!=0):
				#disp(u'ファンクション３')
				#keybd_event(VK_F3,0,KEYEVENTF_KEYDOWN,0)
				#keybd_event(VK_F3,0,KEYEVENTF_KEYUP,0)
				#print u"[F3]",
				pass
			if((lpKeys[0]&0x00080000)!=0):
				#disp(u'ファンクション４')
				#keybd_event(VK_F4,0,KEYEVENTF_KEYDOWN,0)
				#keybd_event(VK_F4,0,KEYEVENTF_KEYUP,0)
				#print u"[F4]",
				pass
		elif((lpKeys[0]&0x0000000f)==0x00000001):
			if((lpKeys[0]&0x00001000)!=0):
				#disp(u'リターン')
				keybd_event(VK_RETURN,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_RETURN,0,KEYEVENTF_KEYUP,0)
				
			elif((lpKeys[0]&0x00000100)!=0):
				#disp(u'スペース')
				keybd_event(VK_SPACE,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_SPACE,0,KEYEVENTF_KEYUP,0)
			else:
				#disp(chr(((lpKeys[0]>>8)&0xff)))
				z2=create_string_buffer(chr(((lpKeys[0]>>8)&0xff)),80)
				z3=create_string_buffer('',80)
				try:
					dll.bmDisplayData(z2,z3,DispSize)
				except:
					pass
				if(DirectBM_dic.dic7.get((lpKeys[0]>>8)&0xff)):
					try:
						LastKey=((lpKeys[0]>>8)&0xff)
						disp(DirectBM_dic.dic7.get(LastKey)[0])
					except:
						LasstKry=0x00
				else:
					if(LastKey==0x00):
						try:
							for Vc in DirectBM_dic.dic6.get(chr((lpKeys[0]>>8)&0xff))[1]:
								keybd_event(ord(Vc),0,KEYEVENTF_KEYDOWN,0)
								keybd_event(ord(Vc),0,KEYEVENTF_KEYUP,0)
						except:
							pass
					else:
						try:
							for Vc in DirectBM_dic.dic6.get(chr(LastKey)+chr((lpKeys[0]>>8)&0xff))[1]:
								keybd_event(ord(Vc),0,KEYEVENTF_KEYDOWN,0)
								keybd_event(ord(Vc),0,KEYEVENTF_KEYUP,0)
						except:
							disp(u'失敗')
							pass
					LastKey=0x00
					
				
		elif((lpKeys[0]&0x0000000f)==0x00000003):
			if((lpKeys[0]&0x00000800)!=0):
				#disp(u'ミギヤジルシ')
				keybd_event(VK_RIGHT,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_RIGHT,0,KEYEVENTF_KEYUP,0)
				#print u"→",
			if((lpKeys[0]&0x00000400)!=0):
				#disp(u'ヒダリヤジルシ')
				keybd_event(VK_LEFT,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_LEFT,0,KEYEVENTF_KEYUP,0)
				#print u"←",
			if((lpKeys[0]&0x00000200)!=0):
				#disp(u'シタヤジルシ')
				keybd_event(VK_DOWN,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_DOWN,0,KEYEVENTF_KEYUP,0)
				#print u"↓",
			if((lpKeys[0]&0x00000100)!=0):
				#disp(u'ウエヤジルシ')
				keybd_event(VK_UP,0,KEYEVENTF_KEYDOWN,0)
				keybd_event(VK_UP,0,KEYEVENTF_KEYUP,0)
				#print u"↑",
		elif((lpKeys[0]&0x0000000f)==0x00000004):
			disp(u'タッチカーソル')	
	elif(gnEquipment == 3):
		#print "KeyEvent:",lpKeys[0],lpKeys[1]
		pass
	else:
		#print "KeyEvent:",lpKeys[0]
		pass        
	return True

# エントリーポイント
if __name__ == '__main__':
	Values=u'12345abcdABCD漢字アイウエオ'
	print DirectBM_dic.Ret2(Values)
	print DirectBM_dic.wakach(Values)
	print DirectBM_dic.dic5.get('\xee')[0]

	#for i in range(1,2):
	#    time.sleep(2)

	print check()
	f_init()
	sp(u'テスト')
	time.sleep(1)
	sp(u'')
	time.sleep(1)
	f_terminate()
	sp(u'テスト')

	time.sleep(1)

	#check()
	f_init()
	sp(u'テスト')
	time.sleep(1)
	sp(u'意味')
	time.sleep(1)
	f_terminate()


	pass		
	