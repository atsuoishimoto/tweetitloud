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
//  tls.cpp: TLS implementation
//
////////////////////////////////////////////////////////////////////// 
#include "nvdajpime.h"

#include "tls.h"
#include "tsf.h"


// static
BOOL TLS::InternalDestroyTLS()
{
    if (dwTLSIndex == TLS_OUT_OF_INDEXES)
        return FALSE;

    TLS* ptls = (TLS*)TlsGetValue(dwTLSIndex);
    if (ptls != NULL)
    {
        if (ptls->_pReadCompTSF)
        {
            ptls->_pReadCompTSF->Release();
            ptls->_pReadCompTSF = NULL;
        }


        LocalFree(ptls);
        TlsSetValue(dwTLSIndex, NULL);
        return TRUE;
    }
    return FALSE;
}
