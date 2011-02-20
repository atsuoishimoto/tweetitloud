/*
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajpime
# by Masataka Shinke
*/


#include "nvdajpime.h"
#include "tls.h"
#include "tsf.h"


//+---------------------------------------------------------------------------
//
// CnvdajpimeTSF
//
//
// This is a class to trace the composition string.
//
//
//----------------------------------------------------------------------------

//+---------------------------------------------------------------------------
//
// ctor
//
//----------------------------------------------------------------------------

CnvdajpimeTSF::CnvdajpimeTSF()
{
    _dwThreadMgrEventSinkCookie = TF_INVALID_COOKIE;
    _dwTextEditSinkCookie = TF_INVALID_COOKIE;
    _pTextEditSinkContext = NULL;
    _pThreadMgr = NULL;
    _pszCompositionText = NULL;
    _uCompositionText = 0;

    _cRef = 1;
}

//+---------------------------------------------------------------------------
//
// dtor
//
//----------------------------------------------------------------------------

CnvdajpimeTSF::~CnvdajpimeTSF()
{
}

//+---------------------------------------------------------------------------
//
// QueryInterface
//
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::QueryInterface(REFIID riid, void **ppvObj)
{
    if (ppvObj == NULL)
        return E_INVALIDARG;

    *ppvObj = NULL;

    if (IsEqualIID(riid, IID_IUnknown) ||
        IsEqualIID(riid, IID_ITfTextEditSink))
    {
        *ppvObj = (ITfTextEditSink *)this;
    }
    else if (IsEqualIID(riid, IID_ITfThreadMgrEventSink))
    {
        *ppvObj = (ITfThreadMgrEventSink *)this;
    }

    if (*ppvObj)
    {
        AddRef();
        return S_OK;
    }

    return E_NOINTERFACE;
}


//+---------------------------------------------------------------------------
//
// AddRef
//
//----------------------------------------------------------------------------

STDAPI_(ULONG) CnvdajpimeTSF::AddRef()
{
    return ++_cRef;
}

//+---------------------------------------------------------------------------
//
// Release
//
//----------------------------------------------------------------------------

STDAPI_(ULONG) CnvdajpimeTSF::Release()
{
    LONG cr = --_cRef;

    assert(_cRef >= 0);

    if (_cRef == 0)
    {
        delete this;
    }

    return cr;
}

//+---------------------------------------------------------------------------
//
// Init
//
//----------------------------------------------------------------------------

BOOL CnvdajpimeTSF::Init()
{
    TLS *ptls = TLS::GetTLS();

    if (!ptls)
        return FALSE;

    if (ptls->_pReadCompTSF)
        return TRUE;

	ptls->_pReadCompTSF = new CnvdajpimeTSF;
    if (!ptls->_pReadCompTSF)
        return FALSE;

    ITfThreadMgr* ptim;
    HRESULT hr;

    hr = CoCreateInstance(CLSID_TF_ThreadMgr, 
                          NULL, 
                          CLSCTX_INPROC_SERVER, 
                          IID_ITfThreadMgr, 
                          (void**)&ptim);

    if (hr != S_OK)
    {
        ptls->_pReadCompTSF->Release();
        ptls->_pReadCompTSF = NULL;
        return FALSE;
    }

    ptls->_pReadCompTSF->_pThreadMgr = ptim;

    ptls->_pReadCompTSF->_InitThreadMgrSink();

    ITfDocumentMgr *pDocMgr;
    if (SUCCEEDED(ptim->GetFocus(&pDocMgr)))
    {
        if (pDocMgr)
        {
           ptls->_pReadCompTSF->_InitTextEditSink(pDocMgr);
           pDocMgr->Release();
        }
    }


    return TRUE;
}

//+---------------------------------------------------------------------------
//
// OnInitDocumentMgr
//
// Sink called by the framework just before the first context is pushed onto
// a document.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnInitDocumentMgr(ITfDocumentMgr *pDocMgr)
{
    return S_OK;
}

//+---------------------------------------------------------------------------
//
// OnUninitDocumentMgr
//
// Sink called by the framework just after the last context is popped off a
// document.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnUninitDocumentMgr(ITfDocumentMgr *pDocMgr)
{
    return S_OK;
}

//+---------------------------------------------------------------------------
//
// OnSetFocus
//
// Sink called by the framework when focus changes from one document to
// another.  Either document may be NULL, meaning previously there was no
// focus document, or now no document holds the input focus.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnSetFocus(ITfDocumentMgr *pDocMgrFocus, ITfDocumentMgr *pDocMgrPrevFocus)
{
    FlushSharedMemory();
    if (GetSharedMemory()->fReadCompRunning)
    {
        // track text changes on the focus doc
        // we are guarenteed a final OnSetFocus(NULL, ..) which we use for 
        // cleanup
        _InitTextEditSink(pDocMgrFocus);
    }

    return S_OK;
}

//+---------------------------------------------------------------------------
//
// OnPushContext
//
// Sink called by the framework when a context is pushed.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnPushContext(ITfContext *pContext)
{
    return S_OK;
}

//+---------------------------------------------------------------------------
//
// OnPopContext
//
// Sink called by the framework when a context is popped.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnPopContext(ITfContext *pContext)
{
    return S_OK;
}

//+---------------------------------------------------------------------------
//
// _InitThreadMgrSink
//
// Advise our sink.
//----------------------------------------------------------------------------

BOOL CnvdajpimeTSF::_InitThreadMgrSink()
{
    ITfSource *pSource;
    BOOL fRet;

    if (_pThreadMgr->QueryInterface(IID_ITfSource, (void **)&pSource) != S_OK)
        return FALSE;

    fRet = FALSE;

    if (pSource->AdviseSink(IID_ITfThreadMgrEventSink, (ITfThreadMgrEventSink *)this, &_dwThreadMgrEventSinkCookie) != S_OK)
    {
        // make sure we don't try to Unadvise _dwThreadMgrEventSinkCookie later
        _dwThreadMgrEventSinkCookie = TF_INVALID_COOKIE;
        goto Exit;
    }

    fRet = TRUE;

Exit:
    pSource->Release();
    return fRet;
}

//+---------------------------------------------------------------------------
//
// _UninitThreadMgrSink
//
// Unadvise our sink.
//----------------------------------------------------------------------------

void CnvdajpimeTSF::_UninitThreadMgrSink()
{
    ITfSource *pSource;

    if (_dwThreadMgrEventSinkCookie == TF_INVALID_COOKIE)
        return; // never Advised

    if (_pThreadMgr->QueryInterface(IID_ITfSource, (void **)&pSource) == S_OK)
    {
        pSource->UnadviseSink(_dwThreadMgrEventSinkCookie);
        pSource->Release();
    }

    _dwThreadMgrEventSinkCookie = TF_INVALID_COOKIE;
}

//+---------------------------------------------------------------------------
//
// OnEndEdit
//
// Called by the system whenever anyone releases a write-access document lock.
//----------------------------------------------------------------------------

STDAPI CnvdajpimeTSF::OnEndEdit(ITfContext *pContext, TfEditCookie ecReadOnly, ITfEditRecord *pEditRecord)
{

    FlushSharedMemory();
    if (GetSharedMemory()->fReadCompRunning)
        _CheckComposition(pContext, ecReadOnly);

	// if we get here, only property values changed

    return S_OK;
}

//+---------------------------------------------------------------------------
//
// _InitTextEditSink
//
// Init a text edit sink on the topmost context of the document.
// Always release any previous sink.
//----------------------------------------------------------------------------

BOOL CnvdajpimeTSF::_InitTextEditSink(ITfDocumentMgr *pDocMgr)
{
    ITfSource *pSource;
    BOOL fRet;

    // clear out any previous sink first

    if (_dwTextEditSinkCookie != TF_INVALID_COOKIE)
    {
        if (_pTextEditSinkContext->QueryInterface(IID_ITfSource, (void **)&pSource) == S_OK)
        {
            pSource->UnadviseSink(_dwTextEditSinkCookie);
            pSource->Release();
        }

        _pTextEditSinkContext->Release();
        _pTextEditSinkContext = NULL;
        _dwTextEditSinkCookie = TF_INVALID_COOKIE;
    }

    if (pDocMgr == NULL)
        return TRUE; // caller just wanted to clear the previous sink

    // setup a new sink advised to the topmost context of the document

    if (pDocMgr->GetTop(&_pTextEditSinkContext) != S_OK)
        return FALSE;

    if (_pTextEditSinkContext == NULL)
        return TRUE; // empty document, no sink possible

    fRet = FALSE;

    if (_pTextEditSinkContext->QueryInterface(IID_ITfSource, (void **)&pSource) == S_OK)
    {
        if (pSource->AdviseSink(IID_ITfTextEditSink, (ITfTextEditSink *)this, &_dwTextEditSinkCookie) == S_OK)
        {
            fRet = TRUE;
        }
        else
        {
            _dwTextEditSinkCookie = TF_INVALID_COOKIE;
        }
        pSource->Release();
    }

    if (fRet == FALSE)
    {
        _pTextEditSinkContext->Release();
        _pTextEditSinkContext = NULL;
    }


    return fRet;
}

//+---------------------------------------------------------------------------
//
// _AppendCompositionText
//
//----------------------------------------------------------------------------

void CnvdajpimeTSF::_AppendCompositionText(ITfRange *pRange, TfEditCookie ecReadOnly)
{
    BOOL fEmpty;
    while (pRange->IsEmpty(ecReadOnly, &fEmpty) == S_OK && !fEmpty)
    {
        WCHAR *pwstr;
        WCHAR wstr[256 + 1];
        ULONG ulcch = ARRAYSIZE(wstr) - 1;
        ULONG ulcchTotal;
        pRange->GetText(ecReadOnly, TF_TF_MOVESTART, wstr, ulcch, &ulcch);

        ulcchTotal = _uCompositionText + ulcch;
        if (_pszCompositionText)
            pwstr = (WCHAR *)LocalReAlloc(_pszCompositionText, LPTR, (ulcchTotal + 1) * sizeof(WCHAR));
        else
            pwstr = (WCHAR *)LocalAlloc(LPTR, (ulcchTotal + 1)* sizeof(WCHAR));

        if (pwstr)
        {
            memcpy(pwstr+_uCompositionText, wstr,  ulcch * sizeof(WCHAR));
            _pszCompositionText = pwstr;
            _uCompositionText = ulcchTotal;
        }
    }
}

//+---------------------------------------------------------------------------
//
// _ClearCompositionText
//
//----------------------------------------------------------------------------

void CnvdajpimeTSF::_ClearCompositionText()
{
    if (_pszCompositionText)
    {
        LocalFree(_pszCompositionText);
        _pszCompositionText = NULL;
    }
    _uCompositionText = 0;
}

//+---------------------------------------------------------------------------
//
// _CheckComposition
//
//----------------------------------------------------------------------------

BOOL CnvdajpimeTSF::_CheckComposition(ITfContext *pContext, TfEditCookie ecReadOnly)
{
    HRESULT hr;
    ITfContextComposition *pContextComposition;
    WCHAR *pszSavedCompositionText = NULL;
    UINT  uSavedCompositionText = 0;
	LONG  xx =0;

    if (_pszCompositionText)
    {
        pszSavedCompositionText = (WCHAR *)LocalAlloc(LPTR, (_uCompositionText + 1) * sizeof(WCHAR));
        if (!pszSavedCompositionText)
            return FALSE;

        memcpy(pszSavedCompositionText, 
               _pszCompositionText,
               _uCompositionText);

       uSavedCompositionText = _uCompositionText;
    }

    _ClearCompositionText();

    hr = pContext->QueryInterface(IID_ITfContextComposition,
                                  (void **)&pContextComposition);
    if (hr == S_OK)
    {
		IEnumITfCompositionView *pEnumCompositionView;

        hr = pContextComposition->EnumCompositions(&pEnumCompositionView);
        if (hr == S_OK)
        {
            ITfCompositionView *pCompositionView;
			
            while (pEnumCompositionView->Next(1, &pCompositionView, NULL) == S_OK)
            {
                ITfRange *pRange;
                hr = pCompositionView->GetRange(&pRange);
                if (hr == S_OK)
                {
		        	xx = _GetLength(pRange, ecReadOnly);
					_AppendCompositionText(pRange, ecReadOnly);
                    pRange->Release();
                }
                pCompositionView->Release();
            }
            pEnumCompositionView->Release();
        }
        pContextComposition->Release();
    }

    if (!_uCompositionText && _pszCompositionText)
    {
        _pszCompositionText[0] = L'\0';
    }

    if ((uSavedCompositionText != _uCompositionText) ||
        memcmp(pszSavedCompositionText, _pszCompositionText, _uCompositionText * sizeof(WCHAR)))
    {
		wsprintf(GetSharedMemory()->TextValue,L"%s",_pszCompositionText);	//@@ Masataka.Shinke
		GetSharedMemory()->TsfMode=TRUE;									//@@ Masataka.Shinke
		HANDLE hEvent = OpenEvent(EVENT_ALL_ACCESS, FALSE, EVENT_NAME);		//@@ Msataka.Shinke
		SetEvent(hEvent);													//@@ Msataka.Shinke
		CloseHandle(hEvent);												//@@ Msataka.Shinke
	}

    if (pszSavedCompositionText)
        LocalFree(pszSavedCompositionText);

	
	return TRUE;
}

LONG CnvdajpimeTSF::_GetLength(ITfRange *pRange,TfEditCookie ecReadOnly)
{
   LONG cch = 0;

   ITfRange *prangeT;
   TF_HALTCOND hc;

   if (pRange->Clone(&prangeT) == S_OK)
   {
       hc.pHaltRange = pRange;
       hc.aHaltPos = TF_ANCHOR_END;
       //hc.aHaltPos = TF_ANCHOR_START;
       hc.dwFlags = 0;

       prangeT->ShiftStart(ecReadOnly, LONG_MAX, &cch, &hc);
	   //prangeT->ShiftEnd(ecReadOnly, LONG_MAX, &cch, &hc);
       prangeT->Release();
   }

   return cch;
}