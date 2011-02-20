/*
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajpime
# by Masataka Shinke
*/

// nvdajpime.cpp : DLL アプリケーション用にエクスポートされる関数を定義します。
//

#include "nvdajpime.h"
#include "tls.h"
#include "tsf.h"

#ifdef NVDAJPIME_RPC
	#include <string>
	#include <sstream>
	#include <windows.h>
	#include "nvdajpimeRPC.h"
	#include <common/winIPCUtils.h>
	#include <iostream>
#endif

using namespace std;

void* __RPC_USER midl_user_allocate(size_t size) {
	return malloc(size);
}

void __RPC_USER midl_user_free(void* p) {
	free(p);
}




HMODULE				g_hModule;

Cnvdajpime*			g_Cnvdajpime;

TLS					g_TLS;
DWORD				TLS::dwTLSIndex = TLS_OUT_OF_INDEXES;

CnvdajpimeSharedMem	g_SharedMemory;


//
//
//
WCHAR* Diff(WCHAR* pOld,WCHAR* pNew,UINT pFirstCode,UINT pLastCode)
{

	std::wstring Old(pOld);
	std::wstring New(pNew);
	std::wstring Dif(L"");
	WCHAR Ret[256]={NULL};

	if(!New.empty())
	{
		switch(pLastCode)
		{
		case 28:
		case 32:
		case 38:
		case 40:
		case 117:
		case 118:
		case 119:
		case 120:
		case 121:
			if(New!=Old)
				wsprintf(Ret,L"%s",New.c_str());
			else if(pFirstCode!=pLastCode)			//@@
				wsprintf(Ret,L"%s",New.c_str());	//@@
			else
				wsprintf(Ret,L"%s",L"");
			return &Ret[0];
			break;
		default:
			break;
		}
	}

	for(int i=(UINT)Old.length()-1,j=(UINT)New.length()-1;(i>=0)*(j>=0);i--,j--)	//@@
	{
		if(Old[i]!=New[j])
		{
			Dif = New[j];
			wsprintf(Ret,L"%s",Dif.c_str());


			if((i>0)&(j>0))
			{
				if(Old[i-1]!=New[j-1])
				{

					if( Dif.compare(std::wstring(L"ゃ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ゅ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ょ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ぁ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ぃ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ぉ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());


					else if (Dif.compare(std::wstring(L"ャ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ュ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ョ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ァ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ィ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ォ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());


					else if (Dif.compare(std::wstring(L"ャ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ュ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ョ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ァ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ィ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());
					else if (Dif.compare(std::wstring(L"ォ")) == 0 )
						wsprintf(Ret,L"%s",New.substr(j-1,2).c_str());


				}
			}


			break;
		}
		
	}
	if(Dif.empty() & (Old.length()<New.length()) )
	{
		Dif = New[New.length()-1];
		wsprintf(Ret,L"%s",Dif.c_str());
	}

	return &Ret[0];
}

void GetIMMOpenStatus()
{
    HWND hwnd = NULL;
    HIMC himc = NULL;

    hwnd = GetFocus();
    if (!hwnd)
        return;

    himc = ImmGetContext(hwnd);
    if (himc)
    {
		GetSharedMemory()->ImeOpenStatus = ImmGetOpenStatus(himc);
        ImmReleaseContext(hwnd, himc);
    }

}

// Cnvdajpimeクラス

UINT WINAPI Cnvdajpime::Thread(void *p_this)
{
	Cnvdajpime*	m_this = reinterpret_cast<Cnvdajpime*>(p_this);

	HANDLE hEvent = CreateEvent(NULL, TRUE, FALSE, EVENT_NAME);





	while(m_this->m_RunFlag)
	{

		WaitForSingleObject(hEvent, INFINITE);
		ResetEvent(hEvent);
		//Sleep(1);

		m_this->m_Result.ImeOpenStatus=GetSharedMemory()->ImeOpenStatus;

		wsprintf(m_this->m_Result.OldValue,L"%s",m_this->m_Result.NewValue);
		wsprintf(m_this->m_Result.NewValue,L"%s",GetSharedMemory()->TextValue);
		wsprintf(m_this->m_Result.DiffValue,L"%s",Diff(m_this->m_Result.OldValue,m_this->m_Result.NewValue,m_this->m_Result.LastKeyCode,GetSharedMemory()->LastKeyCode));

		m_this->m_Result.LastKeyCode=GetSharedMemory()->LastKeyCode;

		if(m_this->m_CallBack!=NULL)
		{
			m_this->m_CallBack(
				m_this->m_Result.LastKeyCode,
				m_this->m_Result.DiffValue,
				m_this->m_Result.ImeOpenStatus,
				m_this->m_Result.OldValue,
				m_this->m_Result.NewValue
			);
		}
		/////////////////////////////////////////////////////////////
		#ifdef NVDAJPIME_RPC
			if(m_this->m_Result.DiffValue[0]!=0)
			{
					wchar_t desktopSpecificNamespace[64];
					generateDesktopSpecificNamespace(desktopSpecificNamespace,ARRAYSIZE(desktopSpecificNamespace));
					wstringstream s;
					s<<L"ncalrpc:[NvdaCtlr."<<desktopSpecificNamespace<<L"]";
					RpcBindingFromStringBinding((RPC_WSTR)(s.str().c_str()),&nvdaControllerBindingHandle);

					if(nvdajpimeRPC_testIfRunning()==0)
					{
						nvdajpimeRPC_speakText(m_this->m_Result.DiffValue);
					}
					RpcBindingFree(&nvdaControllerBindingHandle);
			}	
		#else
			//
		#endif


	}

	CloseHandle(hEvent);


	return 0;
}

void UpdateIMMCompositionString()
{
    HWND hwnd = NULL;
    HIMC himc = NULL;
    WCHAR szComposition[256];
    DWORD dwRet = 0;

	GetIMMOpenStatus();

	if(GetSharedMemory()->TsfMode==FALSE)
	{

		hwnd = GetFocus();
		if (!hwnd)
			return;

		himc = ImmGetContext(hwnd);
		if (himc)
		{
			dwRet = ImmGetCompositionStringW(himc, 
											 GCS_COMPSTR, 
											 szComposition, 
											 sizeof(szComposition));
			ImmReleaseContext(hwnd, himc);
		}
		szComposition[dwRet/sizeof(WCHAR)] = L'\0';
		wsprintf(GetSharedMemory()->TextValue,L"%s",szComposition);
	}
	HANDLE hEvent = OpenEvent(EVENT_ALL_ACCESS, FALSE, EVENT_NAME);		//@@ Msataka.Shinke
	SetEvent(hEvent);													//@@ Msataka.Shinke
	CloseHandle(hEvent);												//@@ Msataka.Shinke

}



//+---------------------------------------------------------------------------
// _SysGetMsgProc
//+---------------------------------------------------------------------------

UINT _SysGetMsgProc(WPARAM wParam, LPARAM lParam)
{
    MSG *pmsg;
    UINT uMsg;

    pmsg = (MSG *)lParam;
    uMsg = pmsg->message;


    switch (uMsg)
    {
        //case WM_IME_STARTCOMPOSITION:
		//	GetSharedMemory()->ImeComposition = true;
		//	break;
        //case WM_IME_ENDCOMPOSITION:
		//	GetSharedMemory()->ImeComposition = false;
		//	break;
        //case WM_IME_COMPOSITION:
		//	break;
		case WM_KEYDOWN:
			//GetIMMOpenStatus();
			if(GetSharedMemory()->ImeOpenStatus)
				CnvdajpimeTSF::Init();
			break;
		case WM_KEYUP:
			UpdateIMMCompositionString();
			break;
        default:
            break;
    }

    return 1;
}

//+---------------------------------------------------------------------------
// SysGetMsgProc
//+---------------------------------------------------------------------------

LRESULT CALLBACK SysGetMsgProc(int nCode, WPARAM wParam, LPARAM lParam)
{
    HHOOK hHook;

    hHook = GetSharedMemory()->hSysGetMsgHook;

    if (nCode == HC_ACTION && (wParam & PM_REMOVE))
    {
        _SysGetMsgProc(wParam, lParam);
    }
    return CallNextHookEx(hHook, nCode, wParam, lParam);
}

//+---------------------------------------------------------------------------
//
// SysGetMsgProc2
//
//+---------------------------------------------------------------------------

LRESULT CALLBACK SysGetMsgProc2(int nCode, WPARAM wParam, LPARAM lParam)
{
    HHOOK hHook;
    hHook = GetSharedMemory()->hSysGetMsgHook2;

	GetSharedMemory()->LastKeyCode = (UINT)wParam;

	HANDLE hEvent = OpenEvent(EVENT_ALL_ACCESS, FALSE, EVENT_NAME);

	switch(GetSharedMemory()->LastKeyCode)
	{
	//case 28:
	//	break;
	case 242:
	case 243:
	case 244:
		SetEvent(hEvent);
		break;
	}
	CloseHandle(hEvent);

	return CallNextHookEx(hHook, nCode, wParam, lParam);
}




// コンストラクタ
Cnvdajpime::Cnvdajpime()
{


    HHOOK hSysGetMsgHook = SetWindowsHookEx(WH_GETMESSAGE, 
                                            SysGetMsgProc, 
                                            g_hModule, 
                                            0);
    if (!hSysGetMsgHook)
        return;
    GetSharedMemory()->hSysGetMsgHook = hSysGetMsgHook;



	HHOOK hSysGetMsgHook2 = SetWindowsHookEx(WH_KEYBOARD, 
                                            SysGetMsgProc2, 
                                            g_hModule, 
                                            0);

    if (!hSysGetMsgHook2)
        return ;
    GetSharedMemory()->hSysGetMsgHook2	= hSysGetMsgHook2;	// Masataka.Shinke



	GetSharedMemory()->fReadCompRunning = TRUE;




	//
	this->m_Result.LastKeyCode=0;
	this->m_Result.TsfMode= FALSE;

	wsprintf(this->m_Result.NewValue,L"%s",L"");
	wsprintf(this->m_Result.OldValue,L"%s",L"");
	wsprintf(this->m_Result.DiffValue,L"%s",L"");

	GetSharedMemory()->LastKeyCode=0;
	GetSharedMemory()->TsfMode=FALSE;
	wsprintf(GetSharedMemory()->TextValue,L"%s",L"");

	//
	this->m_RunFlag = true;

	return;
}
// デストラクタ
Cnvdajpime::~Cnvdajpime()
{



	return;
}




//////////////////////////////////////////////////////////////////////////////
// エクスポート関数。
extern "C" NVDAJPIME_API BOOL WINAPI Initialize(CallBackProc p_CallBack)
{

	g_Cnvdajpime	= new Cnvdajpime();

	if(p_CallBack!=NULL)
	{
		g_Cnvdajpime->m_CallBack = p_CallBack;
	}
	else
	{
		g_Cnvdajpime->m_CallBack = NULL;
	} 

	g_Cnvdajpime->m_Thread = (HANDLE)_beginthreadex( NULL, 0, g_Cnvdajpime->Thread, g_Cnvdajpime, 0, NULL );
	GetSharedMemory()->TsfMode=FALSE;
	GetSharedMemory()->fReadCompRunning = TRUE;

	return TRUE; 
}


// エクスポート関数。
extern "C" NVDAJPIME_API void WINAPI Terminate(void)
{
	g_Cnvdajpime->m_RunFlag = false;

	HANDLE hEvent = OpenEvent(EVENT_ALL_ACCESS, FALSE, EVENT_NAME);
	SetEvent(hEvent);
	CloseHandle(hEvent);

	WaitForSingleObject( g_Cnvdajpime->m_Thread, INFINITE );
	CloseHandle( g_Cnvdajpime->m_Thread );
	delete g_Cnvdajpime;


	GetSharedMemory()->fReadCompRunning = FALSE;


    HHOOK hSysGetMsgHook2 = GetSharedMemory()->hSysGetMsgHook2;

    //if (!hSysGetMsgHook2)
    //    return ;

    UnhookWindowsHookEx(hSysGetMsgHook2);


	HHOOK hSysGetMsgHook = GetSharedMemory()->hSysGetMsgHook;
    //if (!hSysGetMsgHook)
    //    return;
    UnhookWindowsHookEx(hSysGetMsgHook);




}



extern "C" NVDAJPIME_API UINT WINAPI Get_LastKeyCode(void)
{
	return g_Cnvdajpime->m_Result.LastKeyCode;
}

extern "C" NVDAJPIME_API WCHAR* WINAPI Get_DiffTextValue(void)
{
	return &g_Cnvdajpime->m_Result.DiffValue[0];
}

extern "C" NVDAJPIME_API BOOL WINAPI Get_ImeOpenStatus(void)
{
	return g_Cnvdajpime->m_Result.ImeOpenStatus;
}
