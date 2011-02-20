# encoding: utf-8
import time
import sys
from ctypes import *

global lib

# CallBack
def py_cmp_func(LastKeyCode,DiffValue,ImeOpenStatus):
	global exts	
	if LastKeyCode!=0:	
		print LastKeyCode,ImeOpenStatus,c_wchar_p(DiffValue).value
		if (LastKeyCode==244) & (ImeOpenStatus==0) :
			print(u"[日本語オン]")
		elif (LastKeyCode==242) & (ImeOpenStatus==0) :
			print(u"[日本語オン]")
		elif (LastKeyCode==243) & (ImeOpenStatus==1) :
			print(u"[日本語オフ]")
		if LastKeyCode==9:
			exts=0


WINFUNC = WINFUNCTYPE(c_void_p,c_uint,c_wchar_p,c_uint)
cmp_func = WINFUNC(py_cmp_func)


# Initialize
def initialize(ModuleName):
	print ModuleName
	global lib
	try:
		lib = windll.LoadLibrary(ModuleName)
	except:
		print("Err:LoadLibrary")
	try:
		lib.Initialize(cmp_func)
		#lib.Initialize(None)
	except:
		print("Err:CallBack")

#
def terminate():
    try:
        dll.Terminate()
    except:
        pass

#
def Event():
	try:
		lib.Event()
	except:
		print("Err:Event")
#


def DiffTextValue():
    return c_wchar_p(lib.Get_DiffTextValue()).value
def LastKeyCode():
    return lib.Get_LastKeyCode()

if __name__ == '__main__':
	global exts	
	exts=1
	if len(sys.argv) < 2:
		sys.exit()
	initialize(sys.argv[1])
	#initialize(u'nvdajpime3_32.dll')
	while(exts):
		time.sleep(.5)
		#if DiffTextValue()!="":
		#	print DiffTextValue()
	terminate()
		
	#Event()
	#time.sleep(.01)

	
