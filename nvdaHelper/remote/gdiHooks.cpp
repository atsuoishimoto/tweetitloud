/*
This file is a part of the NVDA project.
URL: http://www.nvda-project.org/
Copyright 2006-2010 NVDA contributers.
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License version 2.0, as published by
    the Free Software Foundation.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
This license can be found at:
http://www.gnu.org/licenses/old-licenses/gpl-2.0.html
*/

#include <cassert>
#include <map>
#include <list>
#include <windows.h>
#include <usp10.h>
#include "nvdaHelperRemote.h"
#include "dllmain.h"
#include "apiHook.h"
#include "displayModel.h"
#include <common/log.h>
#include "nvdaControllerInternal.h"
#include "nvdaController.h"
#include <common/lock.h>
#include "gdiHooks.h"

using namespace std;

size_t WA_strlen(const char* str) {
	return strlen(str);
}

size_t WA_strlen(const wchar_t* str) {
	return wcslen(str);
}

char* WA_strncpy(char* dest, const char* source, size_t size) {
	return strncpy(dest,source,size);
}

wchar_t* WA_strncpy(wchar_t* dest, const wchar_t* source, size_t size) {
	return wcsncpy(dest,source,size);
}

map<HWND,int> windowsForTextChangeNotifications;
map<HWND,RECT> textChangeNotifications;
UINT_PTR textChangeNotifyTimerID=0;

void CALLBACK textChangeNotifyTimerProc(HWND hwnd, UINT msg, UINT_PTR timerID, DWORD time) {
	map<HWND,RECT> tempMap;
	textChangeNotifications.swap(tempMap);
	for(map<HWND,RECT>::iterator i=tempMap.begin();i!=tempMap.end();++i) {
		nvdaControllerInternal_displayModelTextChangeNotify((long)(i->first),i->second.left,i->second.top,i->second.right,i->second.bottom);
	}
}

void queueTextChangeNotify(HWND hwnd, RECT& rc) {
	//If this window is not supposed to fire text change notifications then do nothing.
	map<HWND,int>::iterator i=windowsForTextChangeNotifications.find(hwnd);
	if(i==windowsForTextChangeNotifications.end()||i->second<1) return;
	map<HWND,RECT>::iterator n=textChangeNotifications.find(hwnd);
	if(n==textChangeNotifications.end()) {
		// There isn't a notification yet for this window.
		textChangeNotifications.insert(make_pair(hwnd,rc));
	} else {
		// There is already a notification for this window,
		// so expand its rectangle to encompass this new rectangle.
		n->second.left=min(n->second.left,rc.left);
		n->second.top=min(n->second.top,rc.top);
		n->second.right=max(n->second.right,rc.right);
		n->second.bottom=max(n->second.bottom,rc.bottom);
	}
}

displayModelsMap_t<HDC> displayModelsByMemoryDC;
displayModelsMap_t<HWND> displayModelsByWindow;

/**
 * Fetches and or creates a new displayModel for the window of the given device context.
 * If this function returns a displayModel, you must call release on it when you no longer need it. 
 * @param hdc a handle of the device context who's window the displayModel is for.
 * @param noCreate If true a display model will not be created if it does not exist. 
 * @return a pointer to the  new/existing displayModel, NULL if gdiHooks is not initialized or has been terminated. 
 */
inline displayModel_t* acquireDisplayModel(HDC hdc, BOOL noCreate=FALSE) {
	//If we are allowed, acquire use of the displayModel maps
	displayModel_t* model=NULL;
	//If the DC has a window, then either get an existing displayModel using the window, or create a new one and store it by its window.
	//If  the DC does not have a window, try and get the displayModel from our existing Memory DC displayModels. 
	HWND hwnd=WindowFromDC(hdc);
	LOG_DEBUG(L"window from DC is "<<hwnd);
	if(hwnd) {
		displayModelsByWindow.acquire();
		displayModelsMap_t<HWND>::iterator i=displayModelsByWindow.find(hwnd);
		if(i!=displayModelsByWindow.end()) {
			model=i->second;
		} else if(!noCreate) {
			model=new displayModel_t();
			displayModelsByWindow.insert(make_pair(hwnd,model));
		}
		if(model) model->acquire();
		displayModelsByWindow.release();
	} else {
		displayModelsByMemoryDC.acquire();
		displayModelsMap_t<HDC>::iterator i=displayModelsByMemoryDC.find(hdc);
		if(i!=displayModelsByMemoryDC.end()) {
			model=i->second;
		}
		if(model) model->acquire();
		displayModelsByMemoryDC.release();
	}
	return model;
}

/**
 * converts given points from dc coordinates to screen coordinates. 
 * @param hdc a handle to a device context
 * @param points a pointer to the points you wish to convert.
 * @param count the number of points you want to convert.
 */
void dcPointsToScreenPoints(HDC hdc, POINT* points, int count) {
	LPtoDP(hdc,points,count);
	POINT dcOrgPoint;
	GetDCOrgEx(hdc,&dcOrgPoint);
	for(int i=0;i<count;++i) {
		points[i].x+=dcOrgPoint.x;
		points[i].y+=dcOrgPoint.y;
	}
}

/**
 * Given a displayModel, this function clears a rectangle, and inserts a chunk, for the given text, using the given offsets and rectangle etc.
 * This function is used by many of the hook functions.
 * @param model a pointer to a displayModel
 * @param hdc a handle to the device context that was used to write the text originally.
 * @param x the x coordinate (in device units) where the text should start from (depending on textAlign flags, this could be the left, center, or right of the text).
 * @param y the y coordinate (in device units) where the text should start from (depending on textAlign flags, this could be the top, or bottom of the text).
 * @param lprc a pointer to the rectangle that should be cleared. If lprc is NULL, or ETO_OPAQUE is not in fuOptions, then only the rectangle bounding the text will be cleared.
 * @param fuOptions flags accepted by GDI32's ExtTextOut.
 * @param textAlign possible flags returned by GDI32's GetTextAlign.
 * @param lpString the string of unicode text you wish to record.
 * @param characterWidths an optional array of character widths 
 * @param cbCount the length of the string in characters.
 * @param resultTextSize an optional pointer to a SIZE structure that will contain the size of the text.
  */
void ExtTextOutHelper(displayModel_t* model, HDC hdc, int x, int y, const RECT* lprc,UINT fuOptions,UINT textAlign, BOOL stripHotkeyIndicator, const wchar_t* lpString, const int* characterWidths, int cbCount, LPSIZE resultTextSize) {
	RECT clearRect={0,0,0,0};
	//If a rectangle was provided, convert it to screen coordinates
	if(lprc) {
		clearRect=*lprc;
		dcPointsToScreenPoints(hdc,(LPPOINT)&clearRect,2);
		//Also if opaquing is requested, clear this rectangle in the given display model
		if(fuOptions&ETO_OPAQUE) model->clearRectangle(clearRect);
	}
	//If there is no string given, or its only glyphs, then we don't need to go further
	if(!lpString||cbCount<=0||fuOptions&ETO_GLYPH_INDEX) return;
	SIZE _textSize;
	if(!resultTextSize) resultTextSize=&_textSize;
	if(resultTextSize) {
		resultTextSize->cx=0;
		resultTextSize->cy=0;
	}
	wstring newText(lpString,cbCount);
	//Search for and remove the first & symbol if we have been requested to stip hotkey indicator.
	if(stripHotkeyIndicator) {
		size_t pos=newText.find(L'&');
		if(pos!=wstring::npos) newText.erase(pos,1);
	}
	//Fetch the text metrics for this font
	TEXTMETRIC tm;
	GetTextMetrics(hdc,&tm);
	//Calculate character ends X array 
	int* characterEndXArray=(int*)calloc(newText.length(),sizeof(int));
	if(characterWidths) {
		int ac=0;
		for(int i=0;i<newText.length();++i) characterEndXArray[i]=(ac+=characterWidths[(fuOptions&ETO_PDY)?(i*2):i]);
		resultTextSize->cx=ac;
		resultTextSize->cy=tm.tmHeight;
	} else {
		GetTextExtentExPoint(hdc,newText.c_str(),newText.length(),0,NULL,characterEndXArray,resultTextSize);
	}
	//are we writing a transparent background?
	if(tm.tmCharSet!=SYMBOL_CHARSET&&!(fuOptions&ETO_OPAQUE)&&(GetBkMode(hdc)==TRANSPARENT)) {
		//Find out if the text we're writing is just whitespace
		BOOL whitespace=TRUE;
		for(wstring::iterator i=newText.begin();i!=newText.end()&&(whitespace=iswspace(*i));++i);
		if(whitespace) {
			free(characterEndXArray);
			return;
		}
	}
	int textLeft=x;
	int textTop=y;
	//X and Y are not always the left and top of the text.
	//So correct them by taking textAlignment in to account
	UINT hTextAlign=textAlign&(TA_LEFT|TA_RIGHT|TA_CENTER);
	if(hTextAlign==TA_CENTER) {
		LOG_DEBUG(L"TA_CENTER set");
		textLeft-=(resultTextSize->cx/2);
	} else if(hTextAlign==TA_RIGHT) {
		LOG_DEBUG(L"TA_RIGHT set");
		textLeft-=resultTextSize->cx;
	}
	UINT vTextAlign=textAlign&(TA_TOP|TA_BOTTOM|TA_BASELINE);
	if(vTextAlign==TA_BOTTOM) {
		LOG_DEBUG(L"TA_BOTTOM set");
		textTop-=resultTextSize->cy;
	} else if(vTextAlign==TA_BASELINE) {
		LOG_DEBUG(L"TA_BASELINE set");
		textTop-=tm.tmAscent;
	}
	LOG_DEBUG(L"using offset of "<<textLeft<<L","<<textTop);
	RECT textRect={textLeft,textTop,textLeft+resultTextSize->cx,textTop+resultTextSize->cy};
	//We must store chunks using device coordinates, not logical coordinates, as its possible for the DC's viewport to move or resize.
	//For example, in Windows 7, menu items are always drawn at the same DC coordinates, but the DC is moved downward each time.
	dcPointsToScreenPoints(hdc,(LPPOINT)&textRect,2);

	//Clear a space for the text in the model, though take clipping in to account
	RECT tempRect;
	if(lprc&&(fuOptions&ETO_CLIPPED)&&IntersectRect(&tempRect,&textRect,&clearRect)) {
		model->clearRectangle(tempRect,TRUE);
	} else {
		model->clearRectangle(textRect,TRUE);
	}
	//Make sure this is text, and that its not using the symbol charset (e.g. the tick for a checkbox)
	//Before recording the text.
	if(newText.length()>0&&tm.tmCharSet!=SYMBOL_CHARSET) {
		model->insertChunk(textRect,tm.tmAscent,newText,characterEndXArray,(fuOptions&ETO_CLIPPED)?&clearRect:NULL);
		HWND hwnd=WindowFromDC(hdc);
		if(hwnd) queueTextChangeNotify(hwnd,textRect);
	}
	free(characterEndXArray);
}

/**
 * an overload of ExtTextOutHelper to work with ansi strings.
 * @param lpString the string of ansi text you wish to record.
  */
void ExtTextOutHelper(displayModel_t* model, HDC hdc, int x, int y, const RECT* lprc,UINT fuOptions,UINT textAlign, BOOL stripHotkeyIndicator, const char* lpString, const int* characterWidths, int cbCount, LPSIZE resultTextSize) {
	int newCount=0;
	wchar_t* newString=NULL;
	if(lpString&&cbCount) {
		newCount=MultiByteToWideChar(CP_THREAD_ACP,0,lpString,cbCount,NULL,0);
		if(newCount>0) {
			newString=(wchar_t*)calloc(newCount+1,sizeof(wchar_t));
			MultiByteToWideChar(CP_THREAD_ACP,0,lpString,cbCount,newString,newCount);
		}
	}
	ExtTextOutHelper(model,hdc,x,y,lprc,fuOptions,textAlign,stripHotkeyIndicator,newString,characterWidths,newCount,resultTextSize);
	if(newString) free(newString);
}

//TextOut hook class template
//Handles char or wchar_t
template<typename charType> class hookClass_TextOut {
	public:
	typedef int(WINAPI *funcType)(HDC,int,int, const charType*,int);
	static funcType realFunction;
	static int  WINAPI fakeFunction(HDC hdc, int x, int y, const charType* lpString, int cbCount);
};

template<typename charType> typename hookClass_TextOut<charType>::funcType hookClass_TextOut<charType>::realFunction=NULL;

template<typename charType> int  WINAPI hookClass_TextOut<charType>::fakeFunction(HDC hdc, int x, int y, const charType* lpString, int cbCount) {
	UINT textAlign=GetTextAlign(hdc);
	POINT pos={x,y};
	if(textAlign&TA_UPDATECP) GetCurrentPositionEx(hdc,&pos);
	//Call the real function
	BOOL res=realFunction(hdc,x,y,lpString,cbCount);
	//If the real function did not work, or the arguments are not sane, then stop here
	if(res==0||!lpString||cbCount<=0) return res;
	displayModel_t* model=acquireDisplayModel(hdc);
	//If we can't get a display model then stop here.
	if(!model) return res;
	//Calculate the size of the text
	ExtTextOutHelper(model,hdc,pos.x,pos.y,NULL,0,textAlign,FALSE,lpString,NULL,cbCount,NULL);
	model->release();
	return res;
}

//PolyTextOut hook class template

template<typename WA_POLYTEXT> class hookClass_PolyTextOut {
	public:
	typedef BOOL(WINAPI *funcType)(HDC,const WA_POLYTEXT*,int);
	static funcType realFunction;
	static BOOL WINAPI fakeFunction(HDC hdc,const WA_POLYTEXT* pptxt,int cStrings);
};

template<typename WA_POLYTEXT> typename hookClass_PolyTextOut<WA_POLYTEXT>::funcType hookClass_PolyTextOut<WA_POLYTEXT>::realFunction=NULL;

template<typename WA_POLYTEXT> BOOL WINAPI hookClass_PolyTextOut<WA_POLYTEXT>::fakeFunction(HDC hdc,const WA_POLYTEXT* pptxt,int cStrings) {
	//Collect text alignment and possibly current position
	UINT textAlign=GetTextAlign(hdc);
	POINT curPos;
	if(textAlign&TA_UPDATECP) {
		GetCurrentPositionEx(hdc,&curPos);
	}
	//Call the real function
	BOOL res=realFunction(hdc,pptxt,cStrings);
	//If the draw did not work, or there are no strings, then  stop here
	if(res==0||cStrings==0||!pptxt) return res;
	//Get or create a display model for this DC. If we can't get one then stop here
	displayModel_t* model=acquireDisplayModel(hdc);
	if(!model) return res;
	SIZE curTextSize;
	//For each of the strings, record the text
	for(int i=0;i<cStrings;++i) {
		const WA_POLYTEXT* curPptxt=&pptxt[i];
		RECT curClearRect={curPptxt->rcl.left,curPptxt->rcl.top,curPptxt->rcl.right,curPptxt->rcl.bottom};
		//Only use the given x and y if DC's current position should not be used
		if(!(textAlign&TA_UPDATECP)) {
			curPos.x=curPptxt->x;
			curPos.y=curPptxt->y;
		}
		//record the text
		ExtTextOutHelper(model,hdc,curPos.x,curPos.y,&curClearRect,curPptxt->uiFlags,textAlign,FALSE,curPptxt->lpstr,curPptxt->pdx,curPptxt->n,&curTextSize);
		//If the DC's current position should be used,  move our idea of it by the size of the text just recorded
		if(textAlign&TA_UPDATECP) {
			curPos.x+=curTextSize.cx;
			curPos.y+=curTextSize.cy;
		} 
	}
	//Release model and return
	model->release();
	return res;
}

//FillRect hook function
typedef int(WINAPI *FillRect_funcType)(HDC,const RECT*,HBRUSH);
FillRect_funcType real_FillRect=NULL;
int WINAPI fake_FillRect(HDC hdc, const RECT* lprc, HBRUSH hBrush) {
	//Call the real FillRectangle
	int res=real_FillRect(hdc,lprc,hBrush);
	//IfThe fill was successull we can go on.
	if(res==0||lprc==NULL) return res;
	//Try and get a displayModel for this DC, and if we can, then record the original text for these glyphs
	displayModel_t* model=acquireDisplayModel(hdc,TRUE);
	if(!model) return res;
	RECT rect=*lprc;
	dcPointsToScreenPoints(hdc,(LPPOINT)&rect,2);
	model->clearRectangle(rect);
	model->release();
	return res;
}

//PatBlt hook function
typedef BOOL(WINAPI *PatBlt_funcType)(HDC,int,int,int,int,DWORD);
PatBlt_funcType real_PatBlt=NULL;
BOOL WINAPI fake_PatBlt(HDC hdc, int nxLeft, int nxTop, int nWidth, int nHeight, DWORD dwRop) {
	//Call the real PatBlt
	BOOL res=real_PatBlt(hdc,nxLeft,nxTop,nWidth,nHeight,dwRop);
	//IfPatBlt was successfull we can go on
	if(res==0) return res;
	//Try and get a displayModel for this DC, and if we can, then record the original text for these glyphs
	displayModel_t* model=acquireDisplayModel(hdc,TRUE);
	if(!model) return res;
	RECT rect={nxLeft,nxTop,nxLeft+nWidth,nxTop+nHeight};
	dcPointsToScreenPoints(hdc,(LPPOINT)&rect,2);
	model->clearRectangle(rect);
	model->release();
	return res;
}

//BeginPaint hook function
typedef HDC(WINAPI *BeginPaint_funcType)(HWND,LPPAINTSTRUCT);
BeginPaint_funcType real_BeginPaint=NULL;
HDC WINAPI fake_BeginPaint(HWND hwnd, LPPAINTSTRUCT lpPaint) {
	//Call the real BeginPaint
	HDC res=real_BeginPaint(hwnd,lpPaint);
	//If beginPaint was successfull we can go on
	if(res==0||!hwnd) return res;
	//Try and get a displayModel for this DC, and if we can, then record the original text for these glyphs
	displayModel_t* model=acquireDisplayModel(lpPaint->hdc,TRUE);
	if(!model) return res;
	RECT rect=lpPaint->rcPaint;
	ClientToScreen(hwnd,(LPPOINT)&rect);
	ClientToScreen(hwnd,((LPPOINT)&rect)+1);
	model->clearRectangle(rect);
	model->release();
	return res;
}

//ExtTextOut hook class template
//Handles char or wchar_t
template<typename charType> class hookClass_ExtTextOut {
	public:
	typedef BOOL(__stdcall *funcType)(HDC,int,int,UINT,const RECT*,const charType*,UINT,const INT*);
	static funcType realFunction;
	static BOOL __stdcall fakeFunction(HDC hdc, int x, int y, UINT fuOptions, const RECT* lprc, const charType* lpString, UINT cbCount, const INT* lpDx);
};

template<typename charType> typename hookClass_ExtTextOut<charType>::funcType hookClass_ExtTextOut<charType>::realFunction=NULL;

template<typename charType> BOOL __stdcall hookClass_ExtTextOut<charType>::fakeFunction(HDC hdc, int x, int y, UINT fuOptions, const RECT* lprc, const charType* lpString, UINT cbCount, const INT* lpDx) {
	UINT textAlign=GetTextAlign(hdc);
	POINT pos={x,y};
	if(textAlign&TA_UPDATECP) GetCurrentPositionEx(hdc,&pos);
	//Call the real function
	BOOL res=realFunction(hdc,x,y,fuOptions,lprc,lpString,cbCount,lpDx);
	//If the real function did not work, or the arguments are not sane, or only glyphs were provided, then stop here. 
	if(res==0) return res;
	//try to get or create a displayModel for this device context
	displayModel_t* model=acquireDisplayModel(hdc);
	//If we can't get a display model then stop here
	if(!model) return res;
	//Record the text in the displayModel
	ExtTextOutHelper(model,hdc,pos.x,pos.y,lprc,fuOptions,textAlign,FALSE,lpString,lpDx,cbCount,NULL);
	//Release the displayModel and return
	model->release();
	return res;
}

//CreateCompatibleDC hook function
//Hooked so we know when a memory DC is created, as its possible that its contents may at some point be bit blitted back to a window DC (double buffering).
typedef HDC(WINAPI *CreateCompatibleDC_funcType)(HDC);
CreateCompatibleDC_funcType real_CreateCompatibleDC=NULL;
HDC WINAPI fake_CreateCompatibleDC(HDC hdc) {
	//Call the real CreateCompatibleDC
	HDC newHdc=real_CreateCompatibleDC(hdc);
	//If the creation was successful, and the DC that was used in the creation process is a window DC, 
	//we should create a displayModel for this DC so that text writes can be tracked in case  its ever bit blitted to a window DC. 
	//We also need to acquire access to the model maps while we do this
	if(!newHdc) return NULL;
	displayModel_t* model=new displayModel_t();
	displayModelsByMemoryDC.acquire();
	displayModelsByMemoryDC.insert(make_pair(newHdc,model));
	displayModelsByMemoryDC.release();
	return newHdc;
}

//SelectObject hook function
//If a bitmap is being selected, then  we fully clear the display model for this DC if it exists.
typedef HGDIOBJ(WINAPI *SelectObject_funcType)(HDC,HGDIOBJ);
SelectObject_funcType real_SelectObject=NULL;
HGDIOBJ WINAPI fake_SelectObject(HDC hdc, HGDIOBJ hGdiObj) {
	//Call the real SelectObject
	HGDIOBJ res=real_SelectObject(hdc,hGdiObj);
	//If The select was successfull, and the object is a bitmap,  we can go on.
	if(res==0||hGdiObj==NULL||GetObjectType(hGdiObj)!=OBJ_BITMAP) return res;
	//Try and get a displayModel for this DC
	displayModel_t* model=acquireDisplayModel(hdc,TRUE);
	if(!model) return res;
	model->clearAll();
	model->release();
	return res;
}

//DeleteDC hook function
//Hooked so we can get rid of any memory DC no longer needed by the application.
typedef BOOL(WINAPI *DeleteDC_funcType)(HDC);
DeleteDC_funcType real_DeleteDC=NULL;
BOOL WINAPI fake_DeleteDC(HDC hdc) {
	//Call the real DeleteDC
	BOOL res=real_DeleteDC(hdc);
	if(res==0) return res;
	//If the DC was successfully deleted, we should remove  the displayModel we have for it, if it exists.
	displayModelsByMemoryDC.acquire();
	displayModelsMap_t<HDC>::iterator i=displayModelsByMemoryDC.find(hdc);
	if(i!=displayModelsByMemoryDC.end()) {
		i->second->requestDelete();
		displayModelsByMemoryDC.erase(i);
	}
	displayModelsByMemoryDC.release();
	return res;
}

//BitBlt hook function
//Hooked so we can tell when content from one DC is being copied (bit blitted) to another (most likely from a memory DC to a window DC). 
typedef BOOL(WINAPI *BitBlt_funcType)(HDC,int,int,int,int,HDC,int,int,DWORD);
BitBlt_funcType real_BitBlt=NULL;
BOOL WINAPI fake_BitBlt(HDC hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, HDC hdcSrc, int nXSrc, int nYSrc, DWORD dwRop) {
	//Call the real BitBlt
	BOOL res=real_BitBlt(hdcDest,nXDest,nYDest,nWidth,nHeight,hdcSrc,nXSrc,nYSrc,dwRop);
	//If bit blit didn't work, or its not a simple copy, we don't want to know about it
	if(!res) return res;
	BOOL useSource=FALSE;
	switch(dwRop) {
		case MERGECOPY:
		case MERGEPAINT:
		case NOTSRCCOPY:
		case NOTSRCERASE:
		case SRCAND:
		case SRCCOPY:
		case SRCERASE:
		case SRCINVERT:
		case SRCPAINT:
		useSource=TRUE;
	}
	//If there is no source dc given, the destination dc should be used as the source
	if(hdcSrc==NULL) hdcSrc=hdcDest;
	//Try getting a display model for the source DC if one is needed.
	displayModel_t* srcModel=NULL;
	if(useSource) {
		srcModel=acquireDisplayModel(hdcSrc,TRUE);
	}
	//Get or create a display model from the destination DC
	//Don't create one if there is no source model (i.e. dest model will be used as source model)
	displayModel_t* destModel=acquireDisplayModel(hdcDest,srcModel==NULL);
	if(!destModel) {
		if(srcModel) srcModel->release();
		return res;
	}
	RECT srcRect={nXSrc,nYSrc,nXSrc+nWidth,nYSrc+nHeight};
	//we record chunks using device coordinates -- DCs can move/resize
	dcPointsToScreenPoints(hdcSrc,(LPPOINT)&srcRect,2);
	POINT destPos={nXDest,nYDest};
	dcPointsToScreenPoints(hdcDest,&destPos,1);
	if(srcModel) {
		//Copy the requested rectangle from the source model in to the destination model, at the given coordinates.
		srcModel->copyRectangle(srcRect,FALSE,TRUE,destPos.x,destPos.y,NULL,destModel);
		RECT destRect={(srcRect.right-srcRect.left)+destPos.x,(srcRect.bottom-srcRect.top)+destPos.y};
		HWND hwnd=WindowFromDC(hdcDest);
		if(hwnd) queueTextChangeNotify(hwnd,destRect);
	} else {
		//As there is no source model, still at least clear the rectangle
		destModel->clearRectangle(srcRect);
	}
	//release models and return
	if(srcModel) srcModel->release();
	destModel->release();
	return res;
}

typedef struct {
	HDC hdc;
	const void* pString;
	int cString;
	int iCharset;
	DWORD dwFlags;
} ScriptStringAnalyseArgs_t;

typedef map<SCRIPT_STRING_ANALYSIS,ScriptStringAnalyseArgs_t> ScriptStringAnalyseArgsByAnalysis_t;
ScriptStringAnalyseArgsByAnalysis_t ScriptStringAnalyseArgsByAnalysis;
CRITICAL_SECTION criticalSection_ScriptStringAnalyseArgsByAnalysis;
BOOL allow_ScriptStringAnalyseArgsByAnalysis=FALSE;

//ScriptStringAnalyse hook function
//Hooked so we can detect when a character string is being converted in to glyphs.
//Much of Windows (from 2000 onwards) now passes text through uniscribe (this and other Script functions).
typedef HRESULT(WINAPI *ScriptStringAnalyse_funcType)(HDC,const void*,int,int,int,DWORD,int,SCRIPT_CONTROL*,SCRIPT_STATE*,const int*,SCRIPT_TABDEF*,const BYTE*,SCRIPT_STRING_ANALYSIS*);
ScriptStringAnalyse_funcType real_ScriptStringAnalyse=NULL;
HRESULT WINAPI fake_ScriptStringAnalyse(HDC hdc,const void* pString, int cString, int cGlyphs, int iCharset, DWORD dwFlags, int iRectWidth, SCRIPT_CONTROL* psControl, SCRIPT_STATE* psState, const int* piDx, SCRIPT_TABDEF* pTabdef, const BYTE* pbInClass, SCRIPT_STRING_ANALYSIS* pssa) {
	//Call the real ScriptStringAnalyse
	HRESULT res=real_ScriptStringAnalyse(hdc,pString,cString,cGlyphs,iCharset,dwFlags,iRectWidth,psControl,psState,piDx,pTabdef,pbInClass,pssa);
	//We only want to go on if  there's safe arguments
	//We also need to acquire access to our scriptString analysis map
	if(res!=S_OK||!pString||cString<=0||!pssa||!allow_ScriptStringAnalyseArgsByAnalysis) return res;
	EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	if(!allow_ScriptStringAnalyseArgsByAnalysis) {
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		return res;
	}
	//Record information such as the origianl string and a way we can identify it later.
	ScriptStringAnalyseArgs_t args={hdc,pString,cString,iCharset,dwFlags};
	ScriptStringAnalyseArgsByAnalysis[*pssa]=args;
	LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	return res;
}

//ScriptStringFree hook function
//Hooked so we can get rid of any references to information collected via the ScriptStringAnalyse hook function
typedef HRESULT(WINAPI *ScriptStringFree_funcType)(SCRIPT_STRING_ANALYSIS*);
ScriptStringFree_funcType real_ScriptStringFree=NULL;
HRESULT WINAPI fake_ScriptStringFree(SCRIPT_STRING_ANALYSIS* pssa) {
	//Call the real ScriptStringFree
	HRESULT res=real_ScriptStringFree(pssa);
	//If it worked, and arguments seem sane, we go on.
	//We also need to acquire access to our scriptString analysis map
	if(res!=S_OK||!pssa||!allow_ScriptStringAnalyseArgsByAnalysis) return res;
	EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	if(!allow_ScriptStringAnalyseArgsByAnalysis) {
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		return res;
	}
	//Get rid of unneeded info
	ScriptStringAnalyseArgsByAnalysis.erase(*pssa);
	LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	return res; 
}

//ScriptStringOut hook function
//Hooked so we can detect when glyphs previously converted with ScriptStringAnalyse are being outputted.
typedef HRESULT(WINAPI *ScriptStringOut_funcType)(SCRIPT_STRING_ANALYSIS,int,int,UINT,const RECT*,int,int,BOOL);
ScriptStringOut_funcType real_ScriptStringOut=NULL;
HRESULT WINAPI fake_ScriptStringOut(SCRIPT_STRING_ANALYSIS ssa,int iX,int iY,UINT uOptions,const RECT *prc,int iMinSel,int iMaxSel,BOOL fDisabled) {
	//Call the real ScriptStringOut
	HRESULT res=real_ScriptStringOut(ssa,iX,iY,uOptions,prc,iMinSel,iMaxSel,fDisabled);
	//If ScriptStringOut was successful we can go on
	//We also need to acquire access to our Script analysis map
	if(res!=S_OK||!ssa||!allow_ScriptStringAnalyseArgsByAnalysis) return res;
	EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	if(!allow_ScriptStringAnalyseArgsByAnalysis) {
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		return res;
	}
	//Find out if we know about these glyphs
	ScriptStringAnalyseArgsByAnalysis_t::iterator i=ScriptStringAnalyseArgsByAnalysis.find(ssa);
	if(i==ScriptStringAnalyseArgsByAnalysis.end()) {
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		return res;
	} 
	//Try and get/create a displayModel for this DC, and if we can, then record the origianl text for these glyphs
		displayModel_t* model=acquireDisplayModel(i->second.hdc);
	if(!model) {
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		return res;
	}
	BOOL stripHotkeyIndicator=(i->second.dwFlags&SSA_HIDEHOTKEY||i->second.dwFlags&SSA_HOTKEY);
	ExtTextOutHelper(model,i->second.hdc,iX,iY,prc,uOptions,GetTextAlign(i->second.hdc),stripHotkeyIndicator,(wchar_t*)(i->second.pString),NULL,i->second.cString,NULL);
	model->release();
	LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	return res;
}

//ScrollWindow hook function
typedef BOOL(WINAPI *ScrollWindow_funcType)(HWND,int,int,const RECT*, const RECT*);
ScrollWindow_funcType real_ScrollWindow=NULL;
BOOL WINAPI fake_ScrollWindow(HWND hwnd, int XAmount, int YAmount, const RECT* lpRect, const RECT* lpClipRect) {
	BOOL res=real_ScrollWindow(hwnd,XAmount,YAmount,lpRect,lpClipRect);
	if(!res) return res;
	displayModel_t* model=NULL;
	displayModelsByWindow.acquire();
	displayModelsMap_t<HWND>::iterator i=displayModelsByWindow.find(hwnd);
	if(i!=displayModelsByWindow.end()) {
		model=i->second;
		model->acquire();
	}
	displayModelsByWindow.release();
	if(!model) return res;
	RECT clientRect;
	GetClientRect(hwnd,&clientRect);
	RECT realScrollRect=lpRect?*lpRect:clientRect;
	ClientToScreen(hwnd,(LPPOINT)&realScrollRect);
	ClientToScreen(hwnd,((LPPOINT)&realScrollRect)+1);
	RECT realClipRect=lpClipRect?*lpClipRect:clientRect;
	ClientToScreen(hwnd,(LPPOINT)&realClipRect);
	ClientToScreen(hwnd,((LPPOINT)&realClipRect)+1);
	model->copyRectangle(realScrollRect,TRUE,TRUE,realScrollRect.left+XAmount,realScrollRect.top+YAmount,&realClipRect,NULL);
	model->release();
	return res;
}
 
//ScrollWindowEx hook function
typedef BOOL(WINAPI *ScrollWindowEx_funcType)(HWND,int,int,const RECT*, const RECT*, HRGN, LPRECT,UINT);
ScrollWindowEx_funcType real_ScrollWindowEx=NULL;
BOOL WINAPI fake_ScrollWindowEx(HWND hwnd, int dx, int dy, const RECT* prcScroll, const RECT* prcClip, HRGN hrgnUpdate, LPRECT prcUpdate, UINT flags) {
	BOOL res=real_ScrollWindowEx(hwnd,dx,dy,prcScroll,prcClip,hrgnUpdate,prcUpdate,flags);
	if(!res) return res;
	displayModel_t* model=NULL;
	displayModelsByWindow.acquire();
	displayModelsMap_t<HWND>::iterator i=displayModelsByWindow.find(hwnd);
	if(i!=displayModelsByWindow.end()) {
		model=i->second;
		model->acquire();
	}
	displayModelsByWindow.release();
	if(!model) return res;
	RECT clientRect;
	GetClientRect(hwnd,&clientRect);
	RECT realScrollRect=prcScroll?*prcScroll:clientRect;
	ClientToScreen(hwnd,(LPPOINT)&realScrollRect);
	ClientToScreen(hwnd,((LPPOINT)&realScrollRect)+1);
	RECT realClipRect=prcClip?*prcClip:clientRect;
	ClientToScreen(hwnd,(LPPOINT)&realClipRect);
	ClientToScreen(hwnd,((LPPOINT)&realClipRect)+1);
	model->copyRectangle(realScrollRect,TRUE,TRUE,realScrollRect.left+dx,realScrollRect.top+dy,&realClipRect,NULL);
	model->release();
	return res;
}

//DestroyWindow hook function
//Hooked so that we can get rid of  displayModels for windows that are being destroied.
typedef BOOL(WINAPI *DestroyWindow_funcType)(HWND);
DestroyWindow_funcType real_DestroyWindow=NULL;
BOOL WINAPI fake_DestroyWindow(HWND hwnd) {
	//Call the real DestroyWindow
	BOOL res=real_DestroyWindow(hwnd);
	if(res==0) return res;
	//If successful, acquire access to the display model maps and remove the displayModel for this window if it exists.
	displayModelsByWindow.acquire();
	displayModelsMap_t<HWND>::iterator i=displayModelsByWindow.find(hwnd);
	if(i!=displayModelsByWindow.end()) {
		i->second->requestDelete();
		displayModelsByWindow.erase(i);
	}
	displayModelsByWindow.release();
	return res;
}

void gdiHooks_inProcess_initialize() {
	//Initialize the timer for text change notifications
	textChangeNotifyTimerID=SetTimer(NULL,NULL,50,textChangeNotifyTimerProc);
	assert(textChangeNotifyTimerID);
	//Initialize critical sections and access variables for various maps
	InitializeCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	allow_ScriptStringAnalyseArgsByAnalysis=TRUE;
	//Hook needed functions
	hookClass_TextOut<char>::realFunction=apiHook_hookFunction_safe("GDI32.dll",TextOutA,hookClass_TextOut<char>::fakeFunction);
	hookClass_TextOut<wchar_t>::realFunction=apiHook_hookFunction_safe("GDI32.dll",TextOutW,hookClass_TextOut<wchar_t>::fakeFunction);
	hookClass_PolyTextOut<POLYTEXTA>::realFunction=apiHook_hookFunction_safe("GDI32.dll",PolyTextOutA,hookClass_PolyTextOut<POLYTEXTA>::fakeFunction);
	hookClass_PolyTextOut<POLYTEXTW>::realFunction=apiHook_hookFunction_safe("GDI32.dll",PolyTextOutW,hookClass_PolyTextOut<POLYTEXTW>::fakeFunction);
	hookClass_ExtTextOut<char>::realFunction=apiHook_hookFunction_safe("GDI32.dll",ExtTextOutA,hookClass_ExtTextOut<char>::fakeFunction);
	hookClass_ExtTextOut<wchar_t>::realFunction=apiHook_hookFunction_safe("GDI32.dll",ExtTextOutW,hookClass_ExtTextOut<wchar_t>::fakeFunction);
	real_CreateCompatibleDC=apiHook_hookFunction_safe("GDI32.dll",CreateCompatibleDC,fake_CreateCompatibleDC);
	real_SelectObject=apiHook_hookFunction_safe("GDI32.dll",SelectObject,fake_SelectObject);
	real_DeleteDC=apiHook_hookFunction_safe("GDI32.dll",DeleteDC,fake_DeleteDC);
	real_FillRect=apiHook_hookFunction_safe("USER32.dll",FillRect,fake_FillRect);
	real_BeginPaint=apiHook_hookFunction_safe("USER32.dll",BeginPaint,fake_BeginPaint);
	real_BitBlt=apiHook_hookFunction_safe("GDI32.dll",BitBlt,fake_BitBlt);
	real_PatBlt=apiHook_hookFunction_safe("GDI32.dll",PatBlt,fake_PatBlt);
	real_ScrollWindow=apiHook_hookFunction_safe("USER32.dll",ScrollWindow,fake_ScrollWindow);
	real_ScrollWindowEx=apiHook_hookFunction_safe("USER32.dll",ScrollWindowEx,fake_ScrollWindowEx);
	real_DestroyWindow=apiHook_hookFunction_safe("USER32.dll",DestroyWindow,fake_DestroyWindow);
	real_ScriptStringAnalyse=apiHook_hookFunction_safe("USP10.dll",ScriptStringAnalyse,fake_ScriptStringAnalyse);
	real_ScriptStringFree=apiHook_hookFunction_safe("USP10.dll",ScriptStringFree,fake_ScriptStringFree);
	real_ScriptStringOut=apiHook_hookFunction_safe("USP10.dll",ScriptStringOut,fake_ScriptStringOut);
}

void gdiHooks_inProcess_terminate() {
	//Kill the text change notification timer
	KillTimer(0,textChangeNotifyTimerID);
	//Acquire access to the maps and clean them up
	displayModelsByWindow.acquire();
	displayModelsMap_t<HWND>::iterator i=displayModelsByWindow.begin();
	while(i!=displayModelsByWindow.end()) {
		i->second->requestDelete();
		displayModelsByWindow.erase(i++);
	}  
	displayModelsByWindow.release();
	displayModelsByMemoryDC.acquire();
	displayModelsMap_t<HDC>::iterator j=displayModelsByMemoryDC.begin();
	while(j!=displayModelsByMemoryDC.end()) {
		j->second->requestDelete();
		displayModelsByMemoryDC.erase(j++);
	}  
	displayModelsByMemoryDC.release();
	EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	allow_ScriptStringAnalyseArgsByAnalysis=FALSE;
	ScriptStringAnalyseArgsByAnalysis.clear();
	LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
}
