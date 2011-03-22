# coding: UTF-8
#brailleDisplayDrivers/DirectBM.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2009 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
# Masataka.Shinke

import braille              # NVDA
import ui					# NVDA
import queueHandler			# NVDA
from logHandler import log	# NVDA
from ctypes import *
from ctypes.wintypes import *
from brailleDisplayDrivers.DirectBM_drv import DirectBM_drv     # Masataka.Shinke

class BrailleDisplayDriver(braille.BrailleDisplayDriver):
	"""A DirectBM used to disable braille in NVDA.
	"""
	name = "DirectBM"
	description = _(u"DirectBM")

	global Flag
	Flag = False
	global CFlag
	CFlag= False
	
	@classmethod
	def check(cls):
		global CFlag
		if(CFlag==False):
			try:
				DirectBM_drv.check()
			except:
				pass    
		CFlag=True
		return True		

	def __init__(self):
		global Flag
		if(Flag==False):
			try:
				DirectBM_drv.f_init()       # 初期化
			except:
				pass
			Flag=True

	def terminate(self):
		global Flag
		if(Flag==True):
			try:
				DirectBM_drv.f_terminate()   # 開放
			except:
				pass
			Flag=False
			