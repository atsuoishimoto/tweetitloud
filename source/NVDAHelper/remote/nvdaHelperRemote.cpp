//nvdaHelper.cpp
//Copyright (c) 2007 Michael Curran <mick@kulgan.net>
//This file is covered by the GNU General Public Licence
//See the file Copying for details.
 
#include <cstdio>
#include <cassert>
#include <list>
#include <set>
#include <map>
#include <windows.h>
#include "rpcSrv.h"
#include "inputLangChange.h"
#include "typedCharacter.h"
#include "IA2Support.h"
#include "hookRegistration.h"
#include "nvdaHelperRemote.h"

using namespace std;

typedef map<WINEVENTPROC,size_t> winEventHookRegistry_t;
typedef map<HOOKPROC,size_t> windowsHookRegistry_t;

HINSTANCE moduleHandle;
BOOL isInitialized=false;
BOOL inProcess_isInitialized=false;
winEventHookRegistry_t inProcess_registeredWinEventHooks;
windowsHookRegistry_t inProcess_registeredCallWndProcWindowsHooks;
windowsHookRegistry_t inProcess_registeredGetMessageWindowsHooks;
HHOOK getMessageHookID=0;
HHOOK callWndProcHookID=0;
HWINEVENTHOOK winEventHookID=0; 
DWORD desktopProcessID=0;

void inProcess_initialize() {
	Beep(220,35);
	assert(!inProcess_isInitialized);
	rpcSrv_inProcess_initialize();
	IA2Support_inProcess_initialize();
	typedCharacter_inProcess_initialize();
	inputLangChange_inProcess_initialize();
	inProcess_isInitialized=true;
}

void inProcess_terminate() {
	assert(inProcess_isInitialized);
	inputLangChange_inProcess_terminate();
	typedCharacter_inProcess_terminate();
	IA2Support_inProcess_terminate();
	rpcSrv_inProcess_terminate();
	inProcess_isInitialized=false;
	Beep(440,35);
}

bool registerWinEventHook(WINEVENTPROC hookProc) {
	inProcess_registeredWinEventHooks[hookProc]+=1;
	return true;
}

bool unregisterWinEventHook(WINEVENTPROC hookProc) {
	winEventHookRegistry_t::iterator i=inProcess_registeredWinEventHooks.find(hookProc);
	if(i==inProcess_registeredWinEventHooks.end()) return false;
	if(i->second>1) {
		i->second-=1;
	} else {
		assert(i->second==1);
		inProcess_registeredWinEventHooks.erase(i);
	}
	return true;
}

bool registerWindowsHook(int hookType, HOOKPROC hookProc) {
	windowsHookRegistry_t* r=NULL;
	if(hookType==WH_GETMESSAGE) {
		r=&inProcess_registeredGetMessageWindowsHooks;
	} else if(hookType==WH_CALLWNDPROC) {
		r=&inProcess_registeredCallWndProcWindowsHooks;
	}
	if(r==NULL) return false;
	(*r)[hookProc]+=1;
	return true;
}

bool unregisterWindowsHook(int hookType, HOOKPROC hookProc) {
	windowsHookRegistry_t* r=NULL;
	if(hookType==WH_GETMESSAGE) {
		r=&inProcess_registeredGetMessageWindowsHooks;
	} else if(hookType==WH_CALLWNDPROC) {
		r=&inProcess_registeredCallWndProcWindowsHooks;
	}
	if(r==NULL) return false;
	windowsHookRegistry_t::iterator i=r->find(hookProc);
	if(i==r->end()) return false;
	if(i->second>1) {
		i->second-=1;
	} else {
		assert(i->second==1);
		r->erase(i);
	}
	return true;
}

#pragma comment(linker,"/entry:_DllMainCRTStartup@12")
BOOL DllMain(HINSTANCE hModule,DWORD reason,LPVOID lpReserved) {
	if((reason==DLL_PROCESS_ATTACH)&&(moduleHandle==NULL)) {
		moduleHandle=hModule;
		GetWindowThreadProcessId(GetDesktopWindow(),&desktopProcessID);
	} else if(reason==DLL_PROCESS_DETACH) {
	if(inProcess_isInitialized) inProcess_terminate();
	}
	return TRUE;
}

//GetMessage hook callback
LRESULT CALLBACK getMessageHook(int code, WPARAM wParam, LPARAM lParam) {
	if(code<0) {
		return CallNextHookEx(0,code,wParam,lParam);
	}
	//Hookprocs may unregister or register hooks themselves, so we must copy the hookprocs before executing
	list<windowsHookRegistry_t::key_type> hookProcList;
	for(windowsHookRegistry_t::iterator i=inProcess_registeredGetMessageWindowsHooks.begin();i!=inProcess_registeredGetMessageWindowsHooks.end();i++) {
		hookProcList.push_back(i->first);
	}
	for(list<windowsHookRegistry_t::key_type>::iterator j=hookProcList.begin();j!=hookProcList.end();j++) {
		(*j)(code,wParam,lParam);
	}
	return CallNextHookEx(0,code,wParam,lParam);
}

//callWndProc hook callback
LRESULT CALLBACK callWndProcHook(int code, WPARAM wParam,LPARAM lParam) {
	if(code<0) {
		return CallNextHookEx(0,code,wParam,lParam);
	}
	//Hookprocs may unregister or register hooks themselves, so we must copy the hookprocs before executing
	list<windowsHookRegistry_t::key_type> hookProcList;
	for(windowsHookRegistry_t::iterator i=inProcess_registeredCallWndProcWindowsHooks.begin();i!=inProcess_registeredCallWndProcWindowsHooks.end();i++) {
		hookProcList.push_back(i->first);
	}
	for(list<windowsHookRegistry_t::key_type>::iterator j=hookProcList.begin();j!=hookProcList.end();j++) {
		(*j)(code,wParam,lParam);
	}
	return CallNextHookEx(0,code,wParam,lParam);
}

//winEvent callback
void winEventHook(HWINEVENTHOOK hookID, DWORD eventID, HWND hwnd, long objectID, long childID, DWORD threadID, DWORD time) {
	DWORD curProcessID=0;
	if(eventID==EVENT_SYSTEM_FOREGROUND||eventID==EVENT_OBJECT_FOCUS) {
		GetWindowThreadProcessId(hwnd,&curProcessID);
		if(curProcessID!=desktopProcessID) {
			if(!inProcess_isInitialized) inProcess_initialize();
		}
	}
	//Hookprocs may unregister or register hooks themselves, so we must copy the hookprocs before executing
	list<winEventHookRegistry_t::key_type> hookProcList;
	for(winEventHookRegistry_t::iterator i=inProcess_registeredWinEventHooks.begin();i!=inProcess_registeredWinEventHooks.end();i++) {
		hookProcList.push_back(i->first);
	}
	for(list<winEventHookRegistry_t::key_type>::iterator j=hookProcList.begin();j!=hookProcList.end();j++) {
		(*j)(hookID, eventID, hwnd, objectID, childID, threadID, time);
	}
}

int nvdaHelper_initialize() {
	if(isInitialized) {
		fprintf(stderr,"Already initialized\n");
		return -1;
	}
	if(!IA2Support_initialize()) {
		fprintf(stderr,"Error initializing IA2 support\n");
		return -1;
	}
	if((getMessageHookID=SetWindowsHookEx(WH_GETMESSAGE,(HOOKPROC)getMessageHook,moduleHandle,0))==0) {
		fprintf(stderr,"Error registering window message hook\n");
		return -1;
	}
	if((callWndProcHookID=SetWindowsHookEx(WH_CALLWNDPROC,(HOOKPROC)callWndProcHook,moduleHandle,0))==0) {
		fprintf(stderr,"Error registering window message hook\n");
		return -1;
	}
	if((winEventHookID=SetWinEventHook(0,0xFFFFFFFF,moduleHandle,(WINEVENTPROC)winEventHook,0,0,WINEVENT_INCONTEXT|WINEVENT_SKIPOWNPROCESS))==0) {
		fprintf(stderr,"Error registering winEvent hook\n");
		return -1;
	}
	isInitialized=TRUE;
	return 0;
}

int nvdaHelper_terminate() {
	if(!isInitialized) {
		fprintf(stderr,"Error: not initialized yet\n");
		return -1;
	}
	if(UnhookWindowsHookEx(getMessageHookID)==0) {
		fprintf(stderr,"Error unhooking getMessage hook\n");
		return -1;
	}
	if(UnhookWindowsHookEx(callWndProcHookID)==0) {
		fprintf(stderr,"Error unhooking callWndProc hook\n");
		return -1;
	}
	if(UnhookWinEvent(winEventHookID)==FALSE) {
		fprintf(stderr,"Error unregistering foreground winEvent\n");
		return -1;
	}
	if(!IA2Support_terminate()) {
		fprintf(stderr,"Error terminating IA2 support");
		return -1;
	}
	isInitialized=FALSE;
	return 0;
}
