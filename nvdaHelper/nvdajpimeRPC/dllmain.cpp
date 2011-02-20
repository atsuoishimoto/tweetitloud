/*
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajpime
# by Masataka Shinke
*/

// dllmain.cpp : DLL アプリケーションのエントリ ポイントを定義します。
#include "nvdajpime.h"	//@@
#include "tls.h"		//@@
#include "tsf.h"		//@@

//@@
BOOL Process_Attach(HMODULE hModule)
{
	g_hModule		= hModule;

    g_SharedMemory.BaseInit();
    if (!g_SharedMemory.Start())
        return FALSE;

    if (!TLS::Initialize())
        return FALSE;


    return TRUE;
}

//@@
void Process_Dettach(HMODULE hModule)
{
    TLS::DestroyTLS();
    TLS::Uninitialize();
	g_hModule = NULL;
}

BOOL APIENTRY DllMain( HMODULE hModule,
                       DWORD  ul_reason_for_call,
                       LPVOID lpReserved
					 )
{
	switch (ul_reason_for_call)
	{
	case DLL_PROCESS_ATTACH:
		if(!Process_Attach(hModule))
		{
			Process_Dettach(hModule);
			return FALSE;
		}
		break;
	case DLL_THREAD_ATTACH:
		break;
	case DLL_THREAD_DETACH:
		break;
	case DLL_PROCESS_DETACH:
		Process_Dettach(hModule);
		break;
	}
	return TRUE;
}

