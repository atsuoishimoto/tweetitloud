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
// tls.h: TLS declaration
//
////////////////////////////////////////////////////////////////////// 

#ifndef _TLS_H_
#define _TLS_H_


class CnvdajpimeTSF;

class TLS
{
public:
    static inline BOOL Initialize()
    {
        dwTLSIndex = TlsAlloc();
        if (dwTLSIndex == TLS_OUT_OF_INDEXES)
            return FALSE;

        return TRUE;
    }

    static inline void Uninitialize()
    {
        if (dwTLSIndex != TLS_OUT_OF_INDEXES)
        {
            TlsFree(dwTLSIndex);
            dwTLSIndex = TLS_OUT_OF_INDEXES;
        }
    }

    static inline TLS* GetTLS()
    {
        //
        // Should allocate TLS data if doesn't exist.
        //
        return InternalAllocateTLS();
    }

    static inline TLS* ReferenceTLS()
    {
        //
        // Shouldn't allocate TLS data even TLS data doesn't exist.
        //
        return (TLS*)TlsGetValue(dwTLSIndex);
    }

    static inline BOOL DestroyTLS()
    {
        return InternalDestroyTLS();
    }



private:
    static inline TLS* InternalAllocateTLS()
    {
        TLS* ptls = (TLS*)TlsGetValue(dwTLSIndex);
        if (ptls == NULL)
        {
            if ((ptls = (TLS*)LocalAlloc(LPTR, sizeof(TLS))) == NULL)
                return NULL;

            if (! TlsSetValue(dwTLSIndex, ptls))
            {
                LocalFree(ptls);
                return NULL;
            }

            //
            // Set Inital value
            //
            ptls->_pReadCompTSF = NULL;
        }
        return ptls;
    }

    static BOOL InternalDestroyTLS();

private:
    static DWORD dwTLSIndex;

public:
    CnvdajpimeTSF *_pReadCompTSF;
};

#endif // _TLS_H_
