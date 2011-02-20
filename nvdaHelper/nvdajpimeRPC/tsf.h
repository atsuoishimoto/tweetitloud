/*
#A part of NonVisual Desktop Access (NVDA)
#Copyright (C) 2006-2010 NVDA Contributors <http://www.nvda-project.org/>
#This file is covered by the GNU General Public License.
#See the file COPYING for more details.
#
# nvdajpime
# by Masataka Shinke
*/

////////////////////////////////////////////////////////////////////// 
//
// tsf.h: CnvdajpimeTSF declaration
//
////////////////////////////////////////////////////////////////////// 

#ifndef TSF_H
#define TSF_H


class CnvdajpimeTSF : public ITfThreadMgrEventSink, 
                     public ITfTextEditSink
{
public:
    CnvdajpimeTSF();
    ~CnvdajpimeTSF();

    // IUnknown
    STDMETHODIMP QueryInterface(REFIID riid, void **ppvObj);
    STDMETHODIMP_(ULONG) AddRef(void);
    STDMETHODIMP_(ULONG) Release(void);

    // ITfThreadMgrEventSink
    STDMETHODIMP OnInitDocumentMgr(ITfDocumentMgr *pDocMgr);
    STDMETHODIMP OnUninitDocumentMgr(ITfDocumentMgr *pDocMgr);
    STDMETHODIMP OnSetFocus(ITfDocumentMgr *pDocMgrFocus, ITfDocumentMgr *pDocMgrPrevFocus);
    STDMETHODIMP OnPushContext(ITfContext *pContext);
    STDMETHODIMP OnPopContext(ITfContext *pContext);

    // ITfTextEditSink
    STDMETHODIMP OnEndEdit(ITfContext *pContext, TfEditCookie ecReadOnly, ITfEditRecord *pEditRecord);

    static BOOL Init();
    BOOL _InitThreadMgrSink();
    void _UninitThreadMgrSink();
    BOOL _InitTextEditSink(ITfDocumentMgr *pDocMgr);

    void _AppendCompositionText(ITfRange *pRange, TfEditCookie ecReadOnly);
    void _ClearCompositionText();
    BOOL _CheckComposition(ITfContext *pContext, TfEditCookie ecReadOnly);

	LONG _GetLength(ITfRange *pRange,TfEditCookie ecReadOnly);

private:
    DWORD _dwThreadMgrEventSinkCookie;
    DWORD _dwTextEditSinkCookie;
    ITfContext *_pTextEditSinkContext;
    ITfThreadMgr* _pThreadMgr;

    WCHAR *_pszCompositionText;
    ULONG _uCompositionText;

    LONG _cRef;



	WCHAR m_text[128];
	volatile DWORD      m_lock_flags;

};


#endif TSF_H
