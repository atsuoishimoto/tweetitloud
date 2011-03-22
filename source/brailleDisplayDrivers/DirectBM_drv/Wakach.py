# coding: UTF-8
#brailleDisplayDrivers/Wakach.py
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2009 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
# Masataka.Shinke

from ctypes import *
import codecs
import re
import string
import os
import struct
import unicodedata

c_double_p = POINTER(c_double)
c_double_p_p = POINTER(c_double_p) 
c_short_p = POINTER(c_short)
c_char_p_p = POINTER(c_char_p) 

##############################################

# http://mecab.sourceforge.net/libmecab.html
# c:/mecab/sdk/mecab.h
MECAB_NOR_NODE = 0
MECAB_UNK_NODE = 1
MECAB_BOS_NODE = 2
MECAB_EOS_NODE = 3
class mecab_token_t(Structure):
	pass
mecab_token_t_ptr = POINTER(mecab_token_t)

class mecab_path_t(Structure):
	pass
mecab_path_t_ptr = POINTER(mecab_path_t)

class mecab_node_t(Structure):
	pass
mecab_node_t_ptr = POINTER(mecab_node_t)
mecab_node_t_ptr_ptr = POINTER(mecab_node_t_ptr)
mecab_node_t._fields_ = [
		("prev", mecab_node_t_ptr),
		("next", mecab_node_t_ptr),
		("enext", mecab_node_t_ptr),
		("bnext", mecab_node_t_ptr),
		("rpath", mecab_path_t_ptr),
		("lpath", mecab_path_t_ptr),
		("begin_node_list", mecab_node_t_ptr_ptr),
		("end_node_list", mecab_node_t_ptr_ptr),
		("surface", c_char_p),
		("feature", c_char_p),
		("id", c_uint),
		("length", c_ushort),
		("rlength", c_ushort),
		("rcAttr", c_ushort),
		("lcAttr", c_ushort),
		("posid", c_ushort),
		("char_type", c_ubyte),
		("stat", c_ubyte),
		("isbest", c_ubyte),
		("sentence_length", c_uint),
		("alpha", c_float),
		("beta", c_float),
		("prob", c_float),
		("wcost", c_short),
		("cost", c_long),
		("token", mecab_token_t_ptr),
	]

############################################

# typedef struct _Mecab{
#    char **feature;
#    int size;
#    mecab_t *mecab;
# } Mecab;

FELEN   = 1000 # string len
FECOUNT = 1000
FEATURE = c_char * FELEN
FEATURE_ptr = POINTER(FEATURE)
FEATURE_ptr_array = FEATURE_ptr * FECOUNT
FEATURE_ptr_array_ptr = POINTER(FEATURE_ptr_array)

mecab = None
libmc = None
mecab_feature = None
mecab_size = None

def Mecab_initialize(MECAB_DLL, libjt):
	global libmc
	global mecab_feature, mecab_size
	libmc = cdll.LoadLibrary(MECAB_DLL)
	libmc.mecab_sparse_tonode.restype = mecab_node_t_ptr
	mecab_size = 0
	mecab_feature = FEATURE_ptr_array()
	if libjt == None: return
	for i in xrange(0, FECOUNT):
		buf = libjt.jt_malloc(FELEN)
		mecab_feature[i] = cast(buf, FEATURE_ptr)

def Mecab_load(DIC, MECABRC):
	global mecab
	mecab = libmc.mecab_new2(r"mecab -d " + DIC + " -r " + MECABRC)

def Mecab_analysis(str):
	global mecab_size
	if len(str) == 0: return [None, None]
	head = libmc.mecab_sparse_tonode(mecab, str)
	if head == None: return [None, None]
	mecab_size = 0

	# make array of features
	node = head
	i = 0
	while node:
		s = node[0].stat
		if s != MECAB_BOS_NODE and s != MECAB_EOS_NODE:
			c = node[0].length
			s = string_at(node[0].surface, c) + "," + string_at(node[0].feature)
			#print s.decode(CODE) # for debug
			buf = create_string_buffer(s)
			dst_ptr = mecab_feature[i]
			src_ptr = byref(buf)
			memmove(dst_ptr, src_ptr, len(s)+1)
			i += 1
		node = node[0].next
		mecab_size = i
		if i > FECOUNT: return [mecab_feature, mecab_size]
	return [mecab_feature, mecab_size]

def Mecab_refresh():
	global mecab_size
	mecab_size = 0
	pass

def Mecab_clear():
	libmc.mecab_destroy(mecab)

# for debug
def Mecab_print(feature, size, logwrite_, CODE_ = None):
	if logwrite_ == None: return
	if feature == None or size == None: 
		logwrite_( "Mecab_print size: 0" )
		return
	s2 = "Mecab_print size: %d\n" % size
	for i in xrange(0, size):
		s = string_at(feature[i])
		if s:
			if CODE_ == None:
				s2 += "%d %s\n" % (i, s)
			else:
				s2 += "%d %s\n" % (i, s.decode(CODE_))
		else:
			s2 += "[None]\n"
	logwrite_(s2)

############################################

def libjt_initialize(JT_DLL):
	libjt = cdll.LoadLibrary(JT_DLL)
	return libjt

def libjt_text2mecab(libjt, buff, txt):
	libjt.text2mecab.argtypes = [c_char_p, c_char_p] # (char *output, char *input);
	libjt.text2mecab(buff, txt)

def __print(s): print s


def Mecab_split(feature, size, CODE_ = None):
    if feature == None or size == None: 
        return
    s2 = ''
    for i in xrange(0, size):
        s = string_at(feature[i])
        if s:
            if CODE_ == None:
                try:

                    sp=u'空白'
                    sp1=sp.encode(CODE)

                    sp=u'数'
                    sp2=sp.encode(CODE)

                    sp=u'記号'
                    sp3=sp.encode(CODE)

                    rr=s.split(",")[1]
                    ss=s.split(",")[2]

                    # 空白の場合
                    if(ss==sp1):
                        s2 += ' '
                    # 数値の場合
                    elif(ss==sp2):
                        aa=unicode(s.split(",")[0],"cp932")
                        bb=unicodedata.normalize('NFKC',aa)
                        if(aa==bb):
                            s2 += s.split(",")[9]
                            s2 += ' '
                        else:
                            s2 += s.split(",")[0]
                    # 記号の場合    
                    #elif(rr==sp3):
                    #    aa=unicode(s.split(",")[0],"cp932")
                    #    bb=unicodedata.normalize('NFKC',aa)
                    #    if(aa==bb):
                    #        s2 += s.split(",")[9]
                    #        s2 += ' '
                    #    else:
                    #        s2 += s.split(",")[0]
                    else:
                        aa=unicode(s.split(",")[0],"cp932")
                        bb=unicodedata.normalize('NFKC',aa)
                        if(aa==bb):
                            s2 += s.split(",")[9]
                            s2 += ' ' 
                        else:
                            s2 += s.split(",")[0]
                except:
                    s2 += s.split(",")[0]
                    s2 += ' ' 
                    
    return re.sub("  ", " ", unicodedata.normalize('NFKC',unicode(s2.strip(),"cp932")) )


CODE = 'shift_jis' # for mecab dic
DIC = "synthDrivers" + os.sep + "jtalk" + os.sep + "dic"
MECABRC = "synthDrivers" + os.sep + "jtalk" + os.sep + "mecabrc"
MECAB_DLL = "synthDrivers" + os.sep + "jtalk" + os.sep + "libmecab.dll"
JT_DLL = "synthDrivers" + os.sep + "jtalk" + os.sep + "libopenjtalk.dll"
MSGLEN = 1000

############################################

def initialize():
    global libjt
    libjt = libjt_initialize(JT_DLL)
    Mecab_initialize(MECAB_DLL, libjt)
    Mecab_load(DIC, MECABRC)

def terminate():
    try:
        Mecab_clear()
    except:
        pass

def Mecab_wakach(msg1):
    global libjt
    msg=unicodedata.normalize('NFKC',msg1)
    text = msg.encode(CODE)
    buff = create_string_buffer(MSGLEN)
    try:
        libjt_text2mecab(libjt, buff, text)
    except:
        initialize()
        libjt_text2mecab(libjt, buff, text)
    [feature, size] = Mecab_analysis(buff.value)
    #Mecab_print(feature, size,__print)
    return Mecab_split(feature, size)

def main():
    initialize()
    print Mecab_wakach(u"Masataka Shinke")

    terminate()	

if __name__ == "__main__":
	main()


