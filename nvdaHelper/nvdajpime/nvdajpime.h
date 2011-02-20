/*
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajpime
# by Masataka Shinke
*/

//#pragma once

// 以下の ifdef ブロックは DLL からのエクスポートを容易にするマクロを作成するための 
// 一般的な方法です。この DLL 内のすべてのファイルは、コマンド ラインで定義された NVDAJPIME_EXPORTS
// シンボルでコンパイルされます。このシンボルは、この DLL を使うプロジェクトで定義することはできません。
// ソースファイルがこのファイルを含んでいる他のプロジェクトは、 
// NVDAJPIME_API 関数を DLL からインポートされたと見なすのに対し、この DLL は、このマクロで定義された
// シンボルをエクスポートされたと見なします。

#ifdef NVDAJPIME_EXPORTS
#define NVDAJPIME_API __declspec(dllexport)
#else
#define NVDAJPIME_API __declspec(dllimport)
#endif

#ifdef TARGET_64
#define EVENT_NAME TEXT("Event Object nvdajpime3_64")
#define SHAREDM TEXT("nvdajpimeSharedMem_64")
#else
#define EVENT_NAME TEXT("Event Object nvdajpime3_32")
#define SHAREDM TEXT("nvdajpimeSharedMem_32")
#endif

//#pragma comment( lib, "imm32.lib" )


#ifndef _WIN32_WINNT            // 最低限必要なプラットフォームが Windows Vista であることを指定します。
#define _WIN32_WINNT 0x0600     // これを Windows の他のバージョン向けに適切な値に変更してください。
#endif

#ifndef _WIN32_WINDOWS          // 最低限必要なプラットフォームが Windows 98 であることを指定します。
#define _WIN32_WINDOWS 0x0410 // これを Windows Me またはそれ以降のバージョン向けに適切な値に変更してください。
#endif

#ifndef _WIN32_IE                       // 最低限必要なプラットフォームが Internet Explorer 7.0 であることを指定します。
#define _WIN32_IE 0x0700        // これを IE の他のバージョン向けに適切な値に変更してください。
#endif




#define WIN32_LEAN_AND_MEAN             // Windows ヘッダーから使用されていない部分を除外します。
// Windows ヘッダー ファイル:
#include <windows.h>



// TODO: プログラムに必要な追加ヘッダーをここで参照してください。
#include <process.h>
#include <stdlib.h>
#include <msctf.h>		//@@
#include <string>

#include "assert.h"//デバッグ用



//@@ CallBack用コールバック関数ポインタの型
typedef  void (WINAPI *CallBackProc)(UINT LastKeyCode,WCHAR* DiffValue,BOOL ImeOpenStatus,WCHAR* OldValue,WCHAR* NewValue);	// Masataka.Shinke


struct Results
{
	WCHAR			DiffValue[256];
	UINT			LastKeyCode;
	BOOL			ImeOpenStatus;
	WCHAR			OldValue[256];
	WCHAR			NewValue[256];
	BOOL			TsfMode;
};


// このクラスは nvdajpime.dll からエクスポートされました。
class Cnvdajpime {
public:
	Cnvdajpime(void);
	virtual ~Cnvdajpime(void);

	// TODO: メソッドをここに追加してください。

	CallBackProc	m_CallBack;
	Results			m_Result;
	HANDLE			m_Thread;
	BOOL			m_RunFlag;
	static UINT WINAPI Thread(void *p);


};

//
extern HMODULE				g_hModule;
extern Cnvdajpime*			g_Cnvdajpime;

class	TLS; 
extern	TLS					g_TLS;

/*
extern "C" 
{
	NVDAJPIME_API BOOL WINAPI Initialize(CallBackProc p_CallBack);
	NVDAJPIME_API void WINAPI Terminate(void);
	NVDAJPIME_API UINT WINAPI Get_LastKeyCode(void);
	NVDAJPIME_API WCHAR* WINAPI Get_DiffTextValue(void);
	NVDAJPIME_API BOOL WINAPI Get_ImeOpenStatus(void);

}
*/


//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp
//pppppppppppp




class CReadCompFileMapping
{
public:
    void BaseInit()
    {
        _pv = NULL;
        _hfm = NULL;
    }

    void Init(TCHAR *pszFile)
    {
        _pszFile = pszFile;
        _fCreated = FALSE;
    }

    void Uninit()
    {
    }

    void *Open()
    {
        _hfm = OpenFileMapping(FILE_MAP_ALL_ACCESS, FALSE, _pszFile);

        if (_hfm == NULL)
            return NULL;

        return _Map();
    }

    void *Create(SECURITY_ATTRIBUTES *psa, ULONG cbSize, BOOL *pfAlreadyExists)
    {
        _hfm = CreateFileMapping(INVALID_HANDLE_VALUE, psa, PAGE_READWRITE,
                                 0, cbSize, _pszFile);

        if (pfAlreadyExists != NULL)
        {
            *pfAlreadyExists = (GetLastError() == ERROR_ALREADY_EXISTS);
        }

        if (_hfm == NULL)
            return NULL;

        _fCreated = TRUE;
        return _Map();
    }

    BOOL Flush(UINT cbSize)
    {
        if (!_pv)
            return FALSE;

        return FlushViewOfFile(_pv, cbSize);
    }

    void Close()
    {
        if (_pv)
            UnmapViewOfFile(_pv);

        if (_hfm)
            CloseHandle(_hfm);

        _pv = NULL;
        _hfm = NULL;
        _fCreated = FALSE;
    }

    void SetName(TCHAR *psz) {_pszFile = psz;}


    BOOL IsCreated() { return _fCreated; }

private:
    void *_Map()
    {
        _pv = (void *)MapViewOfFile(_hfm, FILE_MAP_WRITE, 0, 0, 0);
        if (!_pv)
        {
            CloseHandle(_hfm);
            _hfm = NULL;
        }
        return _pv;
    }

protected:
    TCHAR *_pszFile;
    void *_pv;
private:
    HANDLE _hfm;
    BOOL _fCreated;
};



typedef struct
{
    HHOOK hSysGetMsgHook;
    BOOL  fReadCompRunning;

    HHOOK			hSysGetMsgHook2;		//@@ Masataka.Shinke
	WCHAR			TextValue[256];			//@@ Masataka.Shinke
	UINT			LastKeyCode;			//@@ Masataka.Shinke
	BOOL			TsfMode;				//@@ Masataka.Shinke
	BOOL			ImeOpenStatus;			//@@ Masataka.Shinke

	BOOL			RunFlag;				//@@ Masataka.Shinke
	CallBackProc	pProc;					//@@ Masataka.Shinke
	HANDLE			hThread;				//@@ Masataka.Shinke
	UINT			threadID;				//@@ Masataka.Shinke


} SHAREDMEM;

class CnvdajpimeSharedMem : public CReadCompFileMapping
{
public:
    BOOL Start()
    {
        BOOL fAlreadyExists;

        //Init(TEXT("nvdajpimeSharedMem_**"));
        Init(SHAREDM);

        if (Create(NULL, sizeof(SHAREDMEM), &fAlreadyExists) == NULL)
            return FALSE;

        if (!fAlreadyExists)
        {
            // by default, every member initialize to 0
        }

        return TRUE;
    }

    SHAREDMEM *GetPtr() { return (SHAREDMEM *)_pv; }

private:
};

extern CnvdajpimeSharedMem g_SharedMemory;

inline SHAREDMEM *GetSharedMemory() { return g_SharedMemory.GetPtr(); }
inline void FlushSharedMemory() { g_SharedMemory.Flush(0); }

