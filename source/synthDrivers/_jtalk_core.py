# _jtalk_core.py 
# -*- coding: utf-8 -*-
# Japanese speech engine wrapper for Open JTalk
# by Takuya Nishimoto
# http://ja.nishimotz.com/project:libopenjtalk

from ctypes import *
import codecs
import re
import string
import os
import struct

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
			s1 = string_at(node[0].surface, c)
			s2 = string_at(node[0].feature)
			s = s1 + ',' + s2
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

# htsengineapi/include/HTS_engine.h

# size of structure:
# HTS_Global     56
# HTS_ModelSet   76
# HTS_Label      24
# HTS_SStreamSet 24
# HTS_PStreamSet 12
# HTS_GStreamSet 20

class HTS_ModelSet(Structure):
	_fields_ = [
		("_dummy", c_byte * 56),
	]

class HTS_Label(Structure):
	_fields_ = [
		("_dummy", c_byte * 76),
	]
HTS_Label_ptr = POINTER(HTS_Label)

class HTS_SStreamSet(Structure):
	_fields_ = [
		("_dummy", c_byte * 24),
	]

class HTS_PStreamSet(Structure):
	_fields_ = [
		("_dummy", c_byte * 12),
	]

class HTS_GStream(Structure):
	_fields_ = [
		("static_length", c_int), # int static_length;  /* static features length */
		("par", c_double_p_p), # double **par; /* generated parameter */
	]

HTS_GStream_ptr = POINTER(HTS_GStream)

# FIXME: engine.gss.total_nsample is always 0
class HTS_GStreamSet(Structure):
	_fields_ = [
		("total_nsample", c_int), # int total_nsample; /* total sample */
		("total_frame", c_int), # int total_frame; /* total frame */
		("nstream", c_int), # int nstream; /* # of streams */
		("gstream", HTS_GStream_ptr), # HTS_GStream *gstream; /* generated parameter streams */
		("gspeech", c_short_p), # short *gspeech; /* generated speech */
	]
HTS_GStreamSet_ptr = POINTER(HTS_GStreamSet)

class HTS_Global(Structure):
	_fields_ = [
		("state", c_int), 		# /* Gamma=-1/stage : if stage=0 then Gamma=0 */
		("use_log_gain", c_int), 	# HTS_Boolean (TRUE=1) /* log gain flag (for LSP) */
		("sampling_rate", c_int), 	# /* sampling rate */
		("fperiod", c_int),		# /* frame period */
		("alpha", c_double),		# /* all-pass constant */
		("beta", c_double),		# /* postfiltering coefficient */
		("audio_buff_size", c_int),	# /* audio buffer size (for audio device) */
		("msd_threshold", c_double_p),	# /* MSD thresholds */
		("duration_iw", c_double_p),	# /* weights for duration interpolation */
		("parameter_iw", c_double_p_p),	# /* weights for parameter interpolation */
		("gv_iw", c_double_p_p),	# /* weights for GV interpolation */
		("gv_weight", c_double_p),	# /* GV weights */
	]
HTS_Global_ptr = POINTER(HTS_Global)

class HTS_Engine(Structure):
	_fields_ = [
		("global", HTS_Global),
		("ms", HTS_ModelSet),
		("label", HTS_Label),
		("sss", HTS_SStreamSet),
		("pss", HTS_PStreamSet),
		("gss", HTS_GStreamSet),
	]
HTS_Engine_ptr = POINTER(HTS_Engine)

############################################

class NJD(Structure):
	_fields_ = [
		("_dummy", c_byte * 8),
	]
NJD_ptr = POINTER(NJD)

class JPCommonNode(Structure):
	pass
JPCommonNode_ptr = POINTER(JPCommonNode)

class JPCommonLabel(Structure):
	pass
JPCommonLabel_ptr = POINTER(JPCommonLabel)

class JPCommon(Structure):
	_fields_ = [
		("head", JPCommonNode_ptr),
		("tail", JPCommonNode_ptr),
		("label", JPCommonLabel_ptr),
	]
JPCommon_ptr = POINTER(JPCommon)

# for debug
def JPC_label_print(feature, size, logwrite_):
	if logwrite_ == None: return
	if feature == None or size == None: 
		logwrite_( "JPC_label_print size: 0" )
		return
	s2 = "JPC_label_print size: %d\n" % size
	for i in xrange(0, size):
		s = string_at(feature[i])
		if s:
			s2 += "%s\n" % s
		else:
			s2 += "[None]"
	logwrite_(s2)

#############################################

FNLEN = 1000
FILENAME = c_char * FNLEN
FILENAME_ptr = POINTER(FILENAME)
FILENAME_ptr_ptr = POINTER(FILENAME_ptr)
FILENAME_ptr_x3 = FILENAME_ptr * 3
FILENAME_ptr_x3_ptr = POINTER(FILENAME_ptr_x3)

def libjt_initialize(JT_DLL, njd, jpcommon, engine, **args):
	libjt = cdll.LoadLibrary(JT_DLL)

	libjt.NJD_initialize.argtypes = [NJD_ptr]
	libjt.NJD_initialize(njd)

	libjt.JPCommon_initialize.argtypes = [JPCommon_ptr]
	libjt.JPCommon_initialize(jpcommon)

	libjt.HTS_Engine_initialize.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_initialize(engine, 2)
	
	libjt.HTS_Engine_set_sampling_rate.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_set_sampling_rate(engine, args['samp_rate']) # 16000
	
	libjt.HTS_Engine_set_fperiod.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_set_fperiod(engine, args['fperiod']) # if samping-rate is 16000: 80(point=5ms) frame period

	libjt.HTS_Engine_set_alpha.argtypes = [HTS_Engine_ptr, c_double]
	libjt.HTS_Engine_set_alpha(engine, args['alpha']) # 0.42

	libjt.HTS_Engine_set_gamma.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_set_gamma(engine, 0)
	
	libjt.HTS_Engine_set_log_gain.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_set_log_gain(engine, 0)
	
	libjt.HTS_Engine_set_beta.argtypes = [HTS_Engine_ptr, c_double]
	libjt.HTS_Engine_set_beta(engine, 0.0)
	
	libjt.HTS_Engine_set_audio_buff_size.argtypes = [HTS_Engine_ptr, c_int]
	libjt.HTS_Engine_set_audio_buff_size(engine, 1600)
	
	libjt.HTS_Engine_set_msd_threshold.argtypes = [HTS_Engine_ptr, c_int, c_double]
	libjt.HTS_Engine_set_msd_threshold(engine, 1, 0.5)
	
	libjt.HTS_Engine_set_gv_weight.argtypes = [HTS_Engine_ptr, c_int, c_double]
	libjt.HTS_Engine_set_gv_weight(engine, 0, 1.0)
	libjt.HTS_Engine_set_gv_weight(engine, 1, 0.7)
	
	# for libjt_synthesis()
	libjt.mecab2njd.argtypes = [NJD_ptr, FEATURE_ptr_array_ptr, c_int]
	libjt.njd_set_pronunciation.argtypes = [NJD_ptr]
	libjt.njd_set_digit.argtypes = [NJD_ptr]
	libjt.njd_set_accent_phrase.argtypes = [NJD_ptr]
	libjt.njd_set_accent_type.argtypes = [NJD_ptr]
	libjt.njd_set_unvoiced_vowel.argtypes = [NJD_ptr]
	libjt.njd_set_long_vowel.argtypes = [NJD_ptr]
	libjt.njd2jpcommon.argtypes = [JPCommon_ptr, NJD_ptr]
	libjt.JPCommon_make_label.argtypes = [JPCommon_ptr]
	libjt.JPCommon_get_label_size.argtypes = [JPCommon_ptr]
	libjt.JPCommon_get_label_size.argtypes = [JPCommon_ptr]
	libjt.JPCommon_get_label_feature.argtypes = [JPCommon_ptr]

	libjt.JPCommon_get_label_feature.restype = c_char_p_p
	libjt.JPCommon_get_label_size.argtypes = [JPCommon_ptr]
	libjt.HTS_Engine_load_label_from_string_list.argtypes = [
		HTS_Engine_ptr, c_char_p_p, c_int]

	libjt.HTS_Engine_create_sstream.argtypes = [HTS_Engine_ptr]
	libjt.HTS_Engine_create_pstream.argtypes = [HTS_Engine_ptr]
	libjt.HTS_Engine_create_gstream.argtypes = [HTS_Engine_ptr]
	libjt.HTS_Engine_refresh.argtypes = [HTS_Engine_ptr]
	libjt.JPCommon_refresh.argtypes = [JPCommon_ptr]
	libjt.NJD_refresh.argtypes = [NJD_ptr]
	libjt.HTS_GStreamSet_get_total_nsample.argtypes = [HTS_GStreamSet_ptr]
	libjt.HTS_GStreamSet_get_speech.argtypes = [HTS_GStreamSet_ptr, c_int]
	libjt.NJD_print.argtypes = [NJD_ptr]
	libjt.JPCommon_print.argtypes = [JPCommon_ptr]
	libjt.JPCommonLabel_print.argtypes = [JPCommonLabel_ptr]

	libjt.jt_total_nsample.argtypes = [HTS_Engine_ptr]
	libjt.jt_speech_ptr.argtypes = [HTS_Engine_ptr]
	libjt.jt_speech_ptr.restype = c_short_p
	libjt.jt_save_logs.argtypes = [c_char_p, HTS_Engine_ptr, NJD_ptr]
	libjt.jt_save_riff.argtypes = [c_char_p, HTS_Engine_ptr]
	libjt.jt_speech_normalize.argtypes = [HTS_Engine_ptr, c_short]
	libjt.jt_trim_silence.argtypes = [HTS_Engine_ptr, c_short, c_short]
	libjt.jt_trim_silence.restype = c_int

	libjt.NJD_clear.argtypes = [NJD_ptr]
	libjt.JPCommon_clear.argtypes = [JPCommon_ptr]
	libjt.HTS_Engine_clear.argtypes = [HTS_Engine_ptr]
	return libjt

def libjt_load(libjt, VOICE, engine):
	libjt.HTS_Engine_load_duration_from_fn.argtypes = [
		HTS_Engine_ptr, FILENAME_ptr_ptr, FILENAME_ptr_ptr, c_int]
	
	fn_ms_dur_buf = create_string_buffer(VOICE + os.sep + "dur.pdf")
	fn_ms_dur_buf_ptr = cast(byref(fn_ms_dur_buf), FILENAME_ptr)
	fn_ms_dur = cast(byref(fn_ms_dur_buf_ptr), FILENAME_ptr_ptr)
	fn_ts_dur_buf = create_string_buffer(VOICE + os.sep + "tree-dur.inf")
	fn_ts_dur_buf_ptr = cast(byref(fn_ts_dur_buf), FILENAME_ptr)
	fn_ts_dur = cast(byref(fn_ts_dur_buf_ptr), FILENAME_ptr_ptr)
	libjt.HTS_Engine_load_duration_from_fn(engine, fn_ms_dur, fn_ts_dur, 1)
	
	libjt.HTS_Engine_load_parameter_from_fn.argtypes = [
		HTS_Engine_ptr, FILENAME_ptr_ptr, FILENAME_ptr_ptr,
		FILENAME_ptr_x3_ptr, c_int, c_int, c_int, c_int]
	
	fn_ms_mcp_buf = create_string_buffer(VOICE + os.sep + "mgc.pdf")
	fn_ms_mcp_buf_ptr = cast(byref(fn_ms_mcp_buf), FILENAME_ptr)
	fn_ms_mcp = cast(byref(fn_ms_mcp_buf_ptr), FILENAME_ptr_ptr)
	fn_ts_mcp_buf = create_string_buffer(VOICE + os.sep + "tree-mgc.inf")
	fn_ts_mcp_buf_ptr = cast(byref(fn_ts_mcp_buf), FILENAME_ptr)
	fn_ts_mcp = cast(byref(fn_ts_mcp_buf_ptr), FILENAME_ptr_ptr)
	fn_ws_mcp_buf_1 = create_string_buffer(VOICE + os.sep + "mgc.win1")
	fn_ws_mcp_buf_2 = create_string_buffer(VOICE + os.sep + "mgc.win2")
	fn_ws_mcp_buf_3 = create_string_buffer(VOICE + os.sep + "mgc.win3")
	fn_ws_mcp_buf_ptr_x3 = FILENAME_ptr_x3(
		cast(byref(fn_ws_mcp_buf_1), FILENAME_ptr),
		cast(byref(fn_ws_mcp_buf_2), FILENAME_ptr),
		cast(byref(fn_ws_mcp_buf_3), FILENAME_ptr))
	fn_ws_mcp = cast(byref(fn_ws_mcp_buf_ptr_x3), FILENAME_ptr_x3_ptr)
	libjt.HTS_Engine_load_parameter_from_fn(
		engine, fn_ms_mcp, fn_ts_mcp, fn_ws_mcp, 
		0, 0, 3, 1)
	
	fn_ms_lf0_buf = create_string_buffer(VOICE + os.sep + "lf0.pdf")
	fn_ms_lf0_buf_ptr = cast(byref(fn_ms_lf0_buf), FILENAME_ptr)
	fn_ms_lf0 = cast(byref(fn_ms_lf0_buf_ptr), FILENAME_ptr_ptr)
	fn_ts_lf0_buf = create_string_buffer(VOICE + os.sep + "tree-lf0.inf")
	fn_ts_lf0_buf_ptr = cast(byref(fn_ts_lf0_buf), FILENAME_ptr)
	fn_ts_lf0 = cast(byref(fn_ts_lf0_buf_ptr), FILENAME_ptr_ptr)
	fn_ws_lf0_buf_1 = create_string_buffer(VOICE + os.sep + "lf0.win1")
	fn_ws_lf0_buf_2 = create_string_buffer(VOICE + os.sep + "lf0.win2")
	fn_ws_lf0_buf_3 = create_string_buffer(VOICE + os.sep + "lf0.win3")
	fn_ws_lf0_buf_ptr_x3 = FILENAME_ptr_x3(
		cast(byref(fn_ws_lf0_buf_1), FILENAME_ptr),
		cast(byref(fn_ws_lf0_buf_2), FILENAME_ptr),
		cast(byref(fn_ws_lf0_buf_3), FILENAME_ptr))
	fn_ws_lf0 = cast(byref(fn_ws_lf0_buf_ptr_x3), FILENAME_ptr_x3_ptr)
	libjt.HTS_Engine_load_parameter_from_fn(
		engine, fn_ms_lf0, fn_ts_lf0, fn_ws_lf0, 
		1, 1, 3, 1)
	
	libjt.HTS_Engine_load_gv_from_fn.argtypes = [
		HTS_Engine_ptr, FILENAME_ptr_ptr, FILENAME_ptr_ptr, 
		c_int, c_int]

	fn_ms_gvm_buf = create_string_buffer(VOICE + os.sep + "gv-mgc.pdf")
	fn_ms_gvm_buf_ptr = cast(byref(fn_ms_gvm_buf), FILENAME_ptr)
	fn_ms_gvm = cast(byref(fn_ms_gvm_buf_ptr), FILENAME_ptr_ptr)
	fn_ts_gvm_buf = create_string_buffer(VOICE + os.sep + "tree-gv-mgc.inf")
	fn_ts_gvm_buf_ptr = cast(byref(fn_ts_gvm_buf), FILENAME_ptr)
	fn_ts_gvm = cast(byref(fn_ts_gvm_buf_ptr), FILENAME_ptr_ptr)
	libjt.HTS_Engine_load_gv_from_fn(
		engine, fn_ms_gvm, fn_ts_gvm, 0, 1)

	fn_ms_gvl_buf = create_string_buffer(VOICE + os.sep + "gv-lf0.pdf")
	fn_ms_gvl_buf_ptr = cast(byref(fn_ms_gvl_buf), FILENAME_ptr)
	fn_ms_gvl = cast(byref(fn_ms_gvl_buf_ptr), FILENAME_ptr_ptr)
	fn_ts_gvl_buf = create_string_buffer(VOICE + os.sep + "tree-gv-lf0.inf")
	fn_ts_gvl_buf_ptr = cast(byref(fn_ts_gvl_buf), FILENAME_ptr)
	fn_ts_gvl = cast(byref(fn_ts_gvl_buf_ptr), FILENAME_ptr_ptr)
	libjt.HTS_Engine_load_gv_from_fn(
		engine, fn_ms_gvl, fn_ts_gvl, 1, 1)

	libjt.HTS_Engine_load_gv_switch_from_fn.argtypes = [
		HTS_Engine_ptr, FILENAME_ptr]

	fn_gv_switch_buf = create_string_buffer(VOICE + os.sep + "gv-switch.inf")
	fn_gv_switch = cast(byref(fn_gv_switch_buf), FILENAME_ptr)
	libjt.HTS_Engine_load_gv_switch_from_fn(
		engine, fn_gv_switch)

def libjt_refresh(libjt, engine, jpcommon, njd):
	libjt.HTS_Engine_refresh(engine)
	libjt.JPCommon_refresh(jpcommon)
	libjt.NJD_refresh(njd)

def libjt_clear(libjt, engine, jpcommon, njd):
	libjt.NJD_clear(njd)
	libjt.JPCommon_clear(jpcommon)
	libjt.HTS_Engine_clear(engine)

def libjt_synthesis(libjt, engine, jpcommon, njd, feature, size, fperiod_=80, feed_func_=None, is_speaking_func_=None, thres_=32, thres2_=32, level_=32767, logwrite_=None):
	if feature == None or size == None: return None
	libjt.HTS_Engine_set_fperiod(engine, fperiod_) # 80(point=5ms) frame period
	libjt.mecab2njd(njd, feature, size)
	libjt.njd_set_pronunciation(njd)
	libjt.njd_set_digit(njd)
	libjt.njd_set_accent_phrase(njd)
	# exception: access violation reading 0x00000000
	# https://github.com/nishimotz/libopenjtalk/commit/10d3abda6835e0547846fb5e12a36c1425561aaa#diff-66
	try:
		libjt.njd_set_accent_type(njd)
	except:
		if logwrite_ != None: logwrite_('libjt_synthesis njd_set_accent_type() error ' + e)
	libjt.njd_set_unvoiced_vowel(njd)
	libjt.njd_set_long_vowel(njd)
	libjt.njd2jpcommon(jpcommon, njd)
	libjt.JPCommon_make_label(jpcommon)
	if is_speaking_func_ and not is_speaking_func_() :
		libjt_refresh(libjt, engine, jpcommon, njd)
		Mecab_refresh()
		return None
	s = libjt.JPCommon_get_label_size(jpcommon)
	buf = None
	if s > 2:
		f = libjt.JPCommon_get_label_feature(jpcommon)
		libjt.HTS_Engine_load_label_from_string_list(engine, f, s)
		libjt.HTS_Engine_create_sstream(engine)
		libjt.HTS_Engine_create_pstream(engine)
		libjt.HTS_Engine_create_gstream(engine)
		if is_speaking_func_ and not is_speaking_func_() :
			libjt_refresh(libjt, engine, jpcommon, njd)
			Mecab_refresh()
			return None
		libjt.jt_speech_normalize(engine, level_)
		total_nsample = libjt.jt_trim_silence(engine, thres_, thres2_)
		speech_ptr = libjt.jt_speech_ptr(engine)
		byte_count = total_nsample * sizeof(c_short)
		buf = string_at(speech_ptr, byte_count)
		if feed_func_: feed_func_(buf)
		#libjt.jt_save_logs("_logfile", engine, njd)
	return buf

def libjt_text2mecab(libjt, buff, txt):
	libjt.text2mecab.argtypes = [c_char_p, c_char_p] # (char *output, char *input);
	libjt.text2mecab(buff, txt)

def pa_play(data, samp_rate = 16000):
	# requires pyaudio (PortAudio wrapper)
	# http://people.csail.mit.edu/hubert/pyaudio/
	import time
	import pyaudio
	p = pyaudio.PyAudio()
	stream = p.open(format = p.get_format_from_width(2),
		channels = 1, rate = samp_rate, output = True)
	size = len(data)
	pos = 0 # byte count
	while pos < size:
		a = stream.get_write_available() * 2
		o = data[pos:pos+a]
		stream.write(o)
		pos += a
	time.sleep(float(size) / 2 / samp_rate)
	stream.close()
	p.terminate()

def __print(s): print s

if __name__ == '__main__':
	CODE = 'cp932' #'shift_jis' # for mecab dic
	DIC = "jtalk" + os.sep + "dic"
	# DIC = "../../../../jtalk/dic"
	VOICES_DIR = "jtalk"
	M001_VOICE_DIR = VOICES_DIR + os.sep + "voice"
	MEI_VOICE_DIR = VOICES_DIR + os.sep + "mei_normal"
	MECABRC = "jtalk" + os.sep + "mecabrc"
	MECAB_DLL = "jtalk" + os.sep + "libmecab.dll"
	JT_DLL = "jtalk" + os.sep + "libopenjtalk.dll"
	# MECAB_DLL = "/usr/lib/libmecab.so.1"
	# JT_DLL = "../../../../github/libopenjtalk/lib/.libs/libopenjtalk.so"
	njd = NJD()
	jpcommon = JPCommon()
	engine = HTS_Engine()
	voice_m001 = {"samp_rate": 16000, "fperiod":  80, "alpha": 0.42, "voicedir": M001_VOICE_DIR}
	voice_mei  = {"samp_rate": 48000, "fperiod": 240, "alpha": 0.55, "voicedir": MEI_VOICE_DIR}
	voice_args = voice_m001
	libjt = libjt_initialize(JT_DLL, njd, jpcommon, engine, **voice_args)
	libjt_load(libjt, voice_args['voicedir'], engine)
	Mecab_initialize(MECAB_DLL, libjt)
	Mecab_load(DIC, MECABRC)
	#
	msg = u'ウェルカムトゥー nvda テンキーのinsertキーとメインのinsertキーの両方がnvdaキーとして動作します'
	MSGLEN = 1000
	text = msg.encode(CODE)
	buff = create_string_buffer(MSGLEN)
	libjt_text2mecab(libjt, buff, text); s = buff.value
	[feature, size] = Mecab_analysis(s)
	Mecab_print(feature, size, __print)
	fperiod = voice_args['fperiod']
	data = libjt_synthesis(libjt, engine, jpcommon, njd, feature, size, fperiod)
	if data != None: 
		pa_play(data, voice_args['samp_rate'])
		import wave
		w = wave.Wave_write("_test.wav")
		w.setparams( (1, 2, voice_args['samp_rate'], len(data)/2, 'NONE', 'not compressed') )
		w.writeframes(data)
		w.close()
	Mecab_clear()
	libjt_clear(libjt, engine, jpcommon, njd)
