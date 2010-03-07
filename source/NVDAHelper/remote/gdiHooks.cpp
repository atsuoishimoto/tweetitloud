#include <cassert>
#include <map>
#include <windows.h>
#include <usp10.h>
#include "apiHook.h"
#include "displayModel.h"
#include <common/log.h>
#include "nvdaControllerInternal.h"
#include "gdiHooks.h"

using namespace std;

typedef map<HDC,displayModel_t*> displayModelsByDC_t;
displayModelsByDC_t displayModelsByMemoryDC;
displayModelsByWindow_t displayModelsByWindow;
CRITICAL_SECTION criticalSection_displayModelMaps;
BOOL allow_displayModelMaps=FALSE;

/**
 * Fetches and or creates a new displayModel for the window of the given device context.
 * If this function returns a displayModel, you must call releaseDisplayModel when finished with it.
 * @param hdc a handle of the device context who's window the displayModel is for.
 * @return a pointer to the  new/existing displayModel, NULL if gdiHooks is not initialized or has been terminated. 
 */
inline displayModel_t* acquireDisplayModel(HDC hdc) {
	//If we are allowed, acquire use of the displayModel maps
	if(!allow_displayModelMaps) return NULL;
	EnterCriticalSection(&criticalSection_displayModelMaps);
	if(!allow_displayModelMaps) {
		LeaveCriticalSection(&criticalSection_displayModelMaps);
		return NULL;
	}
	displayModel_t* model=NULL;
	//If the DC has a window, then either get an existing displayModel using the window, or create a new one and store it by its window.
	//If  the DC does not have a window, try and get the displayModel from our existing Memory DC displayModels. 
	HWND hwnd=WindowFromDC(hdc);
	LOG_DEBUG(L"window from DC is "<<hwnd);
	if(hwnd) {
		displayModelsByWindow_t::iterator i=displayModelsByWindow.find(hwnd);
		if(i!=displayModelsByWindow.end()) {
			model=i->second;
		} else {
			model=new displayModel_t();
			displayModelsByWindow.insert(make_pair(hwnd,model));
		}
	} else {
		displayModelsByDC_t::iterator i=displayModelsByMemoryDC.find(hdc);
		if(i!=displayModelsByMemoryDC.end()) {
			model=i->second;
		}
	}
	if(model) model->AddRef();
	LeaveCriticalSection(&criticalSection_displayModelMaps);
	return model;
}

/**
 * Tells gdiHooks that you are finished with the given displayModel. It is very important that you call releaseDisplayModel for every call to acquireDisplayModel.
 * @param a pointer to the displayModel to release.
 */
inline void releaseDisplayModel(displayModel_t* model) {
	if(model) model->Release();
}

/**
 * Given a displayModel, this function clears a rectangle, and inserts a chunk, for the given text, using the given offsets and rectangle etc.
 * This function is used by many of the hook functions.
 * @param model a pointer to a displayModel
 * @param hdc a handle to the device context that was used to write the text originally.
 * @param x the x coordinate (in device units) where the text should start from (depending on textAlign flags, this could be the left, center, or right of the text).
 * @param y the y coordinate (in device units) where the text should start from (depending on textAlign flags, this could be the top, or bottom of the text).
 * @param textSize a pointer to the size of the text (its width and height).
 * @param lprc a pointer to the rectangle that should be cleared. If lprc is NULL, or ETO_OPAQUE is not in fuOptions, then only the rectangle bounding the text will be cleared.
 * @param fuOptions flags accepted by GDI32's ExtTextOut.
 * @param textAlign possible flags returned by GDI32's GetTextAlign.
 * @param lpString the string of unicode text you wish to record.
 * @param cbCount the length of the string in characters.
  */
void ExtTextOutWHelper(displayModel_t* model, HDC hdc, int x, int y, const SIZE* textSize, const RECT* lprc,UINT fuOptions,UINT textAlign, wchar_t* lpString, int cbCount) {
	wstring newText(lpString,cbCount);
	if(fuOptions&ETO_GLYPH_INDEX) { //The string only contained glyphs, not characters, rather useless to us.
		newText=L"glyphs";
	}
	//are we writing a transparent background?
	if(!(fuOptions&ETO_OPAQUE)&&(GetBkMode(hdc)==TRANSPARENT)) {
		//Find out if the text we're writing is just whitespace
		BOOL whitespace=TRUE;
		for(wstring::iterator i=newText.begin();i!=newText.end()&&(whitespace=iswspace(*i));i++);
		//Because the bacground is transparent, if the text is only whitespace, then return -- don't bother to record anything at all
		if(whitespace) return;
	}
	int xOffset=x;
	int yOffset=y;
	//Correct x and y depending on the text alignment
	if(textAlign&TA_CENTER) {
		LOG_DEBUG(L"TA_CENTER set");
		xOffset-=(textSize->cx/2);
	} else if(textAlign&TA_RIGHT) {
		LOG_DEBUG(L"TA_RIGHT set");
		xOffset-=textSize->cx;
	}
	if(textAlign&TA_BOTTOM) {
		LOG_DEBUG(L"TA_BOTTOM set");
		yOffset-=textSize->cy;
	}
	LOG_DEBUG(L"using offset of "<<xOffset<<L","<<yOffset);
	RECT textRect={xOffset,yOffset,xOffset+textSize->cx,yOffset+textSize->cy};
	//We must store chunks using device coordinates, not logical coordinates, as its possible for the DC's viewport to move or resize.
	//For example, in Windows 7, menu items are always drawn at the same DC coordinates, but the DC is moved downward each time.
	//Device coordinates for a window DC are screen pixels  with 0,0 being the top left of the window's client area.
	LPtoDP(hdc,(LPPOINT)&textRect,2);
	RECT clearRect;
	//If a clearing rectangle was provided we'll use it, otherwise we'll use the text's bounding rectangle.
	if(lprc&&(fuOptions&ETO_OPAQUE)) {
		clearRect=*lprc;
		LPtoDP(hdc,(LPPOINT)&clearRect,2);
	} else {
		LOG_DEBUG(L"Clearing with text's rectangle");
		clearRect=textRect;
	}
	//Update the displayModel.
	model->clearRectangle(clearRect);
	model->insertChunk(textRect,newText);
}

//ExtTextOutW hook function
//This is the lowest level text writing function, though as it can be given pre-calculated glyphs, this is not the only needed function.
typedef BOOL(__stdcall *ExtTextOutW_funcType)(HDC,int,int,UINT,const RECT*,wchar_t*,int,const int*);
ExtTextOutW_funcType real_ExtTextOutW;
BOOL __stdcall fake_ExtTextOutW(HDC hdc, int x, int y, UINT fuOptions, const RECT* lprc, wchar_t* lpString, int cbCount, const int* lpDx) {
	//We can only record stuff if a proper string is provided (I.e. its not NULL and its not glyphs)
	if(lpString&&cbCount>0&&!(fuOptions&ETO_GLYPH_INDEX)) {
		//try to get or create a displayModel for this device context
		displayModel_t* model=acquireDisplayModel(hdc);
		if(model) {
			//Calculate the size of the text
			SIZE textSize;
			GetTextExtentPoint32(hdc,lpString,cbCount,&textSize);
			//ExtTextOut can either provide  specific coordinates, or it can be instructed to use the DC's current position and also update it.
			//if  text alignment does state that the current position must be used, we need to get it before the real ExtTextOut is called, and we need to also update our x,y that we will use for recording the text.
			POINT pos={x,y};
			UINT textAlign=GetTextAlign(hdc);
			if(textAlign&TA_UPDATECP) GetCurrentPositionEx(hdc,&pos);
			//Record the text in the displayModel
			ExtTextOutWHelper(model,hdc,pos.x,pos.y,&textSize,lprc,fuOptions,textAlign,lpString,cbCount);
			//Release the displayModel we got
			releaseDisplayModel(model);
		}
	}
	//Call the real ExtTextOutW
	return real_ExtTextOutW(hdc,x,y,fuOptions,lprc,lpString,cbCount,lpDx);
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
	if(allow_displayModelMaps&&newHdc&&hdc&&WindowFromDC(hdc)) {
		EnterCriticalSection(&criticalSection_displayModelMaps);
		if(!allow_displayModelMaps) {
			LeaveCriticalSection(&criticalSection_displayModelMaps);
			return newHdc;
		}
		displayModel_t* model=new displayModel_t();
		displayModelsByMemoryDC.insert(make_pair(newHdc,model));
		LeaveCriticalSection(&criticalSection_displayModelMaps);
	}
	return newHdc;
}

//DeleteDC hook function
//Hooked so we can get rid of any memory DC no longer needed by the application.
typedef BOOL(WINAPI *DeleteDC_funcType)(HDC);
DeleteDC_funcType real_DeleteDC=NULL;
BOOL WINAPI fake_DeleteDC(HDC hdc) {
	//Call the real DeleteDC
	BOOL res=real_DeleteDC(hdc);
	//If the DC was successfully deleted, we should remove  the displayModel we have for it, if it exists.
	//Acquire access to the display model maps while we do this.
	if(res&&allow_displayModelMaps) {
		EnterCriticalSection(&criticalSection_displayModelMaps);
		if(!allow_displayModelMaps) {
			LeaveCriticalSection(&criticalSection_displayModelMaps);
			return res;
		}
		displayModelsByDC_t::iterator i=displayModelsByMemoryDC.find(hdc);
		if(i!=displayModelsByMemoryDC.end()) {
			i->second->Release();
			displayModelsByMemoryDC.erase(i);
		}
		LeaveCriticalSection(&criticalSection_displayModelMaps);
	}
	return res;
}

//BitBlt hook function
//Hooked so we can tell when content from one DC is being copied (bit blitted) to another (most likely from a memory DC to a window DC). 
typedef BOOL(WINAPI *BitBlt_funcType)(HDC,int,int,int,int,HDC,int,int,DWORD);
BitBlt_funcType real_BitBlt=NULL;
BOOL WINAPI fake_BitBlt(HDC hdcDest, int nXDest, int nYDest, int nWidth, int nHeight, HDC hdcSrc, int nXSrc, int nYSrc, DWORD dwRop) {
	//Call the real BitBlt
	BOOL res=real_BitBlt(hdcDest,nXDest,nYDest,nWidth,nHeight,hdcSrc,nXSrc,nYSrc,dwRop);
	//If bit blit didn't work, we don't want to know about it
	if(!res) return res;
	//Try to get or create a displayModel for the destination DC. If we can't get one we can't go further.
	displayModel_t* destModel=acquireDisplayModel(hdcDest);
	if(!destModel) return res;
	//If the source and destination DCs are the same then we already have our source displayModel.
	//If they are different, then try and get a display model for the source DC, and if we can't we can't go on.
	displayModel_t* srcModel=(hdcSrc==hdcDest)?destModel:acquireDisplayModel(hdcSrc);
	if(srcModel) {
		RECT srcRect={nXSrc,nYSrc,nXSrc+nWidth,nYSrc+nHeight};
		//we record chunks using device coordinates -- DCs can move/resize
		LPtoDP(hdcSrc,(LPPOINT)&srcRect,2);
		POINT destPos={nXDest,nYDest};
		LPtoDP(hdcDest,&destPos,1);
		//Copy the requested rectangle from the source model in to the destination model, at the given coordinates.
		srcModel->copyRectangleToOtherModel(srcRect,destModel,destPos.x,destPos.y);
		//release models and return
		if(srcModel!=destModel) releaseDisplayModel(srcModel);
	}
	releaseDisplayModel(destModel);
	return res;
}

typedef struct {
	HDC hdc;
	const void* pString;
	int cString;
	int iCharset;
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
	if(res==S_OK&&pString&&cString>0&&pssa&&allow_ScriptStringAnalyseArgsByAnalysis) {
		EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		if(!allow_ScriptStringAnalyseArgsByAnalysis) return res;
		//Record information such as the origianl string and a way we can identify it later.
		ScriptStringAnalyseArgs_t args={hdc,pString,cString,iCharset};
		ScriptStringAnalyseArgsByAnalysis[*pssa]=args;
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	}
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
	if(res==S_OK&&pssa&&allow_ScriptStringAnalyseArgsByAnalysis) {
		EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		if(!allow_ScriptStringAnalyseArgsByAnalysis) return res;
		//Get rid of unneeded info
		ScriptStringAnalyseArgsByAnalysis.erase(*pssa);
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	}
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
	if(res==S_OK&&allow_ScriptStringAnalyseArgsByAnalysis) {
		EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
		if(!allow_ScriptStringAnalyseArgsByAnalysis) return res;
		//Find out if we know about these glyphs
		ScriptStringAnalyseArgsByAnalysis_t::iterator i=ScriptStringAnalyseArgsByAnalysis.find(ssa);
		if(i!=ScriptStringAnalyseArgsByAnalysis.end()) {
			//Try and get/create a displayModel for this DC, and if we can, then record the origianl text for these glyphs
			displayModel_t* model=acquireDisplayModel(i->second.hdc);
			if(model) {
				ExtTextOutWHelper(model,i->second.hdc,iX,iY,ScriptString_pSize(i->first),prc,uOptions,GetTextAlign(i->second.hdc),(wchar_t*)(i->second.pString),i->second.cString);
				releaseDisplayModel(model);
			}
		}
		LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	}
	return res;
}

//DestroyWindow hook function
//Hooked so that we can get rid of  displayModels for windows that are being destroied.
typedef BOOL(WINAPI *DestroyWindow_funcType)(HWND);
DestroyWindow_funcType real_DestroyWindow=NULL;
BOOL WINAPI fake_DestroyWindow(HWND hwnd) {
	//Call the real DestroyWindow
	BOOL res=real_DestroyWindow(hwnd);
	//If successful, acquire access to the display model maps and remove the displayModel for this window if it exists.
	if(res) {
		EnterCriticalSection(&criticalSection_displayModelMaps);
		if(!allow_displayModelMaps) {
			LeaveCriticalSection(&criticalSection_displayModelMaps);
			return res;
		}
		displayModelsByWindow_t::iterator i=displayModelsByWindow.find(hwnd);
		if(i!=displayModelsByWindow.end()) {
			i->second->Release();
			displayModelsByWindow.erase(i);
		}
		LeaveCriticalSection(&criticalSection_displayModelMaps);
	}
	return res;
}

void gdiHooks_inProcess_initialize() {
	//Initialize critical sections and access variables for various maps
	InitializeCriticalSection(&criticalSection_displayModelMaps);
	allow_displayModelMaps=TRUE;
	InitializeCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	allow_ScriptStringAnalyseArgsByAnalysis=TRUE;
	//Hook needed functions
	real_CreateCompatibleDC=(CreateCompatibleDC_funcType)apiHook_hookFunction("GDI32.dll","CreateCompatibleDC",fake_CreateCompatibleDC);
	real_DeleteDC=(DeleteDC_funcType)apiHook_hookFunction("GDI32.dll","DeleteDC",fake_DeleteDC);
	real_BitBlt=(BitBlt_funcType)apiHook_hookFunction("GDI32.dll","BitBlt",fake_BitBlt);
	real_DestroyWindow=(DestroyWindow_funcType)apiHook_hookFunction("USER32.dll","DestroyWindow",fake_DestroyWindow);
	real_ExtTextOutW=(ExtTextOutW_funcType)apiHook_hookFunction("GDI32.dll","ExtTextOutW",fake_ExtTextOutW);
	real_ScriptStringAnalyse=(ScriptStringAnalyse_funcType)apiHook_hookFunction("USP10.dll","ScriptStringAnalyse",fake_ScriptStringAnalyse);
	real_ScriptStringFree=(ScriptStringFree_funcType)apiHook_hookFunction("USP10.dll","ScriptStringFree",fake_ScriptStringFree);
	real_ScriptStringOut=(ScriptStringOut_funcType)apiHook_hookFunction("USP10.dll","ScriptStringOut",fake_ScriptStringOut);
}

void gdiHooks_inProcess_terminate() {
	//Acquire access to the maps and clean them up
	EnterCriticalSection(&criticalSection_displayModelMaps);
	allow_displayModelMaps=FALSE;
	displayModelsByWindow_t::iterator i=displayModelsByWindow.begin();
	while(i!=displayModelsByWindow.end()) {
		i->second->Release();
		displayModelsByWindow.erase(i++);
	}  
	displayModelsByDC_t::iterator j=displayModelsByMemoryDC.begin();
	while(j!=displayModelsByMemoryDC.end()) {
		j->second->Release();
		displayModelsByMemoryDC.erase(j++);
	}  
	LeaveCriticalSection(&criticalSection_displayModelMaps);
	EnterCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
	allow_ScriptStringAnalyseArgsByAnalysis=FALSE;
	ScriptStringAnalyseArgsByAnalysis.clear();
	LeaveCriticalSection(&criticalSection_ScriptStringAnalyseArgsByAnalysis);
}
