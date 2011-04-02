#!/usr/bin/python
# coding: UTF-8
#nvdajp_ime.py
#A part of NonVisual Desktop Access (NVDA)
# Masataka.Shinke
import time
import nvdajp_dic			# Masataka Shinke
import config				# NVDA
import winUser				# NVDA
import ui					# NVDA
import queueHandler			# NVDA
from logHandler import log	# NVDA
from ctypes import *
lib = windll.LoadLibrary("lib/nvdajpime.dll");
_last_ime_status = 0 ## 2011-02-10 by nishimotz
# callback
def py_cmp_func(LastKeyCode,DiffValue,ImeOpenStatus,OldValue,NewValue):
	global _last_ime_status
	if c_wchar_p(DiffValue).value!="":
		if LastKeyCode in (winUser.VK_SPACE,
			winUser.VK_CONVERT,
			winUser.VK_UP,
			winUser.VK_DOWN,
			winUser.VK_F6,
			winUser.VK_F7,
			winUser.VK_F8,
			winUser.VK_F9,
			winUser.VK_F10):
			for i in DiffValue:
				if nvdajp_dic.dic1.has_key(i) & (config.conf["keyboard"]["nvdajp2Key"]==True):
					if (nvdajp_dic.dic1.get(i)[0]==3) + (config.conf["keyboard"]["nvdajp3Key"]==True):
						queueHandler.queueFunction(queueHandler.eventQueue,ui.message,nvdajp_dic.dic1.get(i)[2]) # 詳細、フォネティック読み
					else:
						queueHandler.queueFunction(queueHandler.eventQueue,ui.message,i)
				elif nvdajp_dic.dic1.has_key(i):
					if (nvdajp_dic.dic1.get(i)[0]!=3) & (config.conf["keyboard"]["nvdajp3Key"]==True):
						queueHandler.queueFunction(queueHandler.eventQueue,ui.message,nvdajp_dic.dic1.get(i)[2]) # 詳細、フォネティック読み
					else:
						queueHandler.queueFunction(queueHandler.eventQueue,ui.message,i)
				else:
					queueHandler.queueFunction(queueHandler.eventQueue,ui.message,i)
		elif LastKeyCode in (winUser.VK_BACK,winUser.VK_DELETE):
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message, c_wchar_p(OldValue[-1]).value)
		else:
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message,c_wchar_p(DiffValue).value)
	elif (LastKeyCode==winUser.VK_RETURN) & (c_wchar_p(OldValue).value!="") & (config.conf["keyboard"]["nvdajp1Key"]==True):
			queueHandler.queueFunction(queueHandler.eventQueue,ui.message,c_wchar_p(OldValue).value)
	## 2011-02-10 by nishimotz
	# elif (LastKeyCode==242) & (ImeOpenStatus==0):
	#	queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＮ")
	# elif (LastKeyCode==244) & (ImeOpenStatus==0):
	#	queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＮ")
	# elif (LastKeyCode==243) & (ImeOpenStatus==1):
	#	queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＦＦ")
	elif (LastKeyCode==242) & (_last_ime_status==0):
		queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＮ")
		_last_ime_status = 1
	elif (LastKeyCode==244) & (_last_ime_status==0):
		queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＮ")
		_last_ime_status = 1
	elif (LastKeyCode==243) & (_last_ime_status==1):
		queueHandler.queueFunction(queueHandler.eventQueue,ui.message,u"にほんごＯＦＦ")
		_last_ime_status = 0
WINFUNC = WINFUNCTYPE(c_void_p,c_uint,c_wchar_p,c_uint,c_wchar_p,c_wchar_p)
cmp_func = WINFUNC(py_cmp_func)

# initialize
def initialize():
	try:
		lib.Initialize(cmp_func)
	except:
		pass

# terminate
def terminate():
	try:
		lib.Terminate()
	except:
		pass
