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
#include <windows.h>
#include <set>
#include <string>
#include <sstream>
#include <ia2.h>
#include <common/ia2utils.h>
#include <remote/nvdaHelperRemote.h>
#include <vbufBase/backend.h>
#include <common/debug.h>
#include <vbufBase/utils.h>
#include "gecko_ia2.h"

using namespace std;

#define IGNORE_NONINTERACTIVE_UNLABELED_GRAPHICS 1
#define IGNORE_UNNEEDED_GRAPHICS_IN_LINKS 1

#define NAVRELATION_NODE_CHILD_OF 0x1005

HWND findRealMozillaWindow(HWND hwnd) {
	DEBUG_MSG(L"Finding real window for window "<<hwnd);
	if(hwnd==0||!IsWindow(hwnd)) {
		DEBUG_MSG(L"Invalid window");
		return (HWND)0;
	}
	wchar_t className[256];
	bool foundWindow=false;
	do {
		if(GetClassName(hwnd,className,256)==0) {
			DEBUG_MSG(L"Could not get class name for window "<<hwnd);
			return hwnd;
		}
		DEBUG_MSG(L"class name for window "<<hwnd<<L" is "<<className);
		if(wcscmp(L"MozillaWindowClass",className)!=0) {
			foundWindow=true;
		} else {
			hwnd=GetAncestor(hwnd,GA_PARENT);
		}
	} while(hwnd&&!foundWindow);
	DEBUG_MSG(L"Found window "<<hwnd);
	return hwnd;
}

IAccessible2* IAccessible2FromIdentifier(int docHandle, int ID) {
	int res;
	IAccessible* pacc=NULL;
	IServiceProvider* pserv=NULL;
	IAccessible2* pacc2=NULL;
	VARIANT varChild;
	DEBUG_MSG(L"calling AccessibleObjectFromEvent");
	if((res=AccessibleObjectFromEvent((HWND)docHandle,OBJID_CLIENT,ID,&pacc,&varChild))!=S_OK) {
		DEBUG_MSG(L"AccessibleObjectFromEvent returned "<<res);
		return NULL;
	}
	DEBUG_MSG(L"got IAccessible at "<<pacc);
	VariantClear(&varChild);
	DEBUG_MSG(L"calling IAccessible::QueryInterface with IID_IServiceProvider");
	if((res=pacc->QueryInterface(IID_IServiceProvider,(void**)(&pserv)))!=S_OK) {
		DEBUG_MSG(L"IAccessible::QueryInterface returned "<<res);
		pacc->Release();
		return NULL;
	}  
	DEBUG_MSG(L"IServiceProvider at "<<pserv);
	DEBUG_MSG(L"releasing IAccessible");
	pacc->Release();
	DEBUG_MSG(L"calling IServiceProvider::QueryService with IID_IAccessible2");
	if((res=pserv->QueryService(IID_IAccessible,IID_IAccessible2,(void**)(&pacc2)))!=S_OK) {
		DEBUG_MSG(L"IServiceProvider::QueryService returned "<<res);
		pacc2=NULL;
	}  else {
		DEBUG_MSG(L"IAccessible2 at "<<pacc2);
	}
	DEBUG_MSG(L"releasingIServiceProvider");
	pserv->Release();
	return pacc2;
}

VBufStorage_fieldNode_t* fillVBuf(IAccessible2* pacc, VBufStorage_buffer_t* buffer, VBufStorage_controlFieldNode_t* parentNode, VBufStorage_fieldNode_t* previousNode, IAccessibleTable2* paccTable=NULL, long tableID=0) {
	int res;
	DEBUG_MSG(L"Entered fillVBuf, with pacc at "<<pacc<<L", parentNode at "<<parentNode<<L", previousNode "<<previousNode);
	assert(buffer); //buffer can't be NULL
	assert(!parentNode||buffer->isNodeInBuffer(parentNode)); //parent node must be in buffer
	assert(!previousNode||buffer->isNodeInBuffer(previousNode)); //Previous node must be in buffer
	VBufStorage_fieldNode_t* tempNode;
	bool isBlockElement=TRUE;
	//all IAccessible methods take a variant for childID, get one ready
	VARIANT varChild;
	varChild.vt=VT_I4;
	long left=0, top=0, width=0, height=0;
	varChild.lVal=0;
	if((res=pacc->accLocation(&left,&top,&width,&height,varChild))!=S_OK) {
		DEBUG_MSG(L"Error getting accLocation");
	}
	//get docHandle -- IAccessible2 windowHandle
	DEBUG_MSG(L"get docHandle with IAccessible2::get_windowHandle");
	int docHandle;
	if((res=pacc->get_windowHandle((HWND*)(&docHandle)))!=S_OK) {
		DEBUG_MSG(L"pacc->get_windowHandle returned "<<res);
		docHandle=0;
		return NULL;
	}
	docHandle=(int)findRealMozillaWindow((HWND)docHandle);
	if(docHandle==0) {
		DEBUG_MSG(L"bad docHandle");
		return NULL;
	}
	DEBUG_MSG(L"docHandle is "<<docHandle);
	//Get ID -- IAccessible2 uniqueID
	DEBUG_MSG(L"get ID with IAccessible2::get_uniqueID");
	int ID;
	if((res=pacc->get_uniqueID((long*)(&ID)))!=S_OK) {
		DEBUG_MSG(L"pacc->get_uniqueID returned "<<res);
		ID=0;
		return NULL;
	}
	DEBUG_MSG(L"ID is "<<ID);
	//Make sure that we don't already know about this object -- protect from loops
	if(buffer->getControlFieldNodeWithIdentifier(docHandle,ID)!=NULL) {
		DEBUG_MSG(L"a node with this docHandle and ID already exists, returning NULL");
		return NULL;
	}
	//Add this node to the buffer
	DEBUG_MSG(L"Adding Node to buffer");
	parentNode=buffer->addControlFieldNode(parentNode,previousNode,docHandle,ID,TRUE);
	assert(parentNode); //new node must have been created
	previousNode=NULL;
	DEBUG_MSG(L"Added  node at "<<parentNode);
	//Get role -- IAccessible2 role
	DEBUG_MSG(L"get role with IAccessible2::role");
	long role=0;
	BSTR roleString=NULL;
	if((res=pacc->role(&role))!=S_OK) {
		DEBUG_MSG(L"pacc->get_role returned "<<res);
		role=IA2_ROLE_UNKNOWN;
	}
	VARIANT varRole;
	VariantInit(&varRole);
	if(role==0) {
		if((res=pacc->get_accRole(varChild,&varRole))!=S_OK) {
			DEBUG_MSG(L"accRole returned code "<<res);
		}
		if(varRole.vt==VT_I4) {
			role=varRole.lVal;
			DEBUG_MSG(L"Got role of "<<role);
		} else if(varRole.vt==VT_BSTR) {
			roleString=varRole.bstrVal;
			DEBUG_MSG(L"Got role string of "<<roleString);
		}
	} else {
		DEBUG_MSG(L"role is "<<role);
	}
	//Add role as an attrib
	{
		wostringstream s;
		if(roleString!=NULL) {
			s<<roleString;
		} else {
			s<<role;
		}
		parentNode->addAttribute(L"IAccessible::role",s.str().c_str());
	}
	VariantClear(&varRole);
	//get states -- IAccessible accState
	DEBUG_MSG(L"get states with IAccessible::get_accState");
	varChild.lVal=0;
	VARIANT varState;
	VariantInit(&varState);
	if((res=pacc->get_accState(varChild,&varState))!=S_OK) {
		DEBUG_MSG(L"pacc->get_accState returned "<<res);
		varState.vt=VT_I4;
		varState.lVal=0;
	}
	int states=varState.lVal;
	VariantClear(&varState);
	DEBUG_MSG(L"states is "<<states);
	//Add each state that is on, as an attrib
	for(int i=0;i<32;++i) {
		int state=1<<i;
		if(state&states) {
			wostringstream nameStream;
			nameStream<<L"IAccessible::state_"<<state;
			parentNode->addAttribute(nameStream.str().c_str(),L"1");
		}
	}
	//get IA2States -- IAccessible2 states
	DEBUG_MSG(L"get IA2States with IAccessible2::get_states");
	int IA2States;
	if((res=pacc->get_states((AccessibleStates*)(&IA2States)))!=S_OK) {
		DEBUG_MSG(L"pacc->get_states returned "<<res);
		IA2States=0;
	}
	DEBUG_MSG(L"IA2States is "<<IA2States);
	//Add each state that is on, as an attrib
	for(int i=0;i<32;++i) {
		int state=1<<i;
		if(state&IA2States) {
			wostringstream nameStream;
			nameStream<<L"IAccessible2::state_"<<state;
			parentNode->addAttribute(nameStream.str().c_str(),L"1");
		}
	}
	//get keyboardShortcut -- IAccessible accKeyboardShortcut;
	DEBUG_MSG(L"get keyboardShortcut with IAccessible::get_accKeyboardShortcut");
	BSTR keyboardShortcut;
	varChild.lVal=0;
	if((res=pacc->get_accKeyboardShortcut(varChild,&keyboardShortcut))!=S_OK) {
		DEBUG_MSG(L"pacc->get_accKeyboardShortcut returned "<<res);
		keyboardShortcut=NULL;
	}
	if(keyboardShortcut!=NULL) {
		DEBUG_MSG(L"keyboardShortcut is "<<keyboardShortcut);
	} else {
		DEBUG_MSG(L"keyboardShortcut is NULL");
	}
	//Add keyboardShortcut as an attrib
	if(keyboardShortcut!=NULL) {
		parentNode->addAttribute(L"keyboardShortcut",keyboardShortcut);
		//Free keyboardShortcut string memory
		SysFreeString(keyboardShortcut);
	} else {
		parentNode->addAttribute(L"keyboardShortcut",L"");
	}
	//get IA2Attributes -- IAccessible2 attributes;
	DEBUG_MSG(L"get IA2Attributes with IAccessible2::get_attributes");
	BSTR IA2Attributes;
	if((res=pacc->get_attributes(&IA2Attributes))!=S_OK) {
		DEBUG_MSG(L"pacc->get_attributes returned "<<res);
		IA2Attributes=NULL;
	}
	map<wstring,wstring> IA2AttribsMap;
	if(IA2Attributes!=NULL) {
		DEBUG_MSG(L"IA2Attributes is "<<IA2Attributes);
		IA2AttribsToMap(IA2Attributes,IA2AttribsMap);
	} else {
		DEBUG_MSG(L"IA2Attributes is NULL");
	}
	if(IA2Attributes!=NULL) {
		// Add each IA2 attribute as an attrib.
		for(map<wstring,wstring>::const_iterator it=IA2AttribsMap.begin();it!=IA2AttribsMap.end();++it) {
			wostringstream nameStream;
			nameStream<<L"IAccessible2::attribute_"<<it->first;
			parentNode->addAttribute(nameStream.str().c_str(),it->second.c_str());
		}
	} else {
		parentNode->addAttribute(L"IAccessible2::attributes",L"");
	}
	DEBUG_MSG(L"getting accDefaultAction");
	BSTR defaction=NULL;
	if((res=pacc->get_accDefaultAction(varChild,&defaction))!=S_OK) {
		DEBUG_MSG(L"IAccessible::get_accDefaultAction returned "<<res);
		defaction=NULL;
	}
	if(defaction!=NULL&&SysStringLen(defaction)==0) {
		SysFreeString(defaction);
		defaction=NULL;
	}
	if(defaction!=NULL) {
		parentNode->addAttribute(L"defaultAction",defaction);
	}
	{
		//Check IA2Attributes, and or the role etc to work out if this object is a block element
		DEBUG_MSG(L"Is this object a block element?");
		map<wstring,wstring>::const_iterator it;
		if(IA2States&IA2_STATE_MULTI_LINE) {
			// Multiline nodes should always be block.
			isBlockElement=TRUE;
		} else if((it=IA2AttribsMap.find(L"display"))!=IA2AttribsMap.end()) {
			// If there is a display attribute, we can rely solely on this to determine whether this is a block element or not.
			DEBUG_MSG(L"IA2Attributes contains display, value "<<it->second);
			isBlockElement=(it->second!=L"inline");
		} else if((it=IA2AttribsMap.find(L"formatting"))!=IA2AttribsMap.end()&&it->second==L"block") {
			DEBUG_MSG(L"IA2Attributes contains formatting:block, this is a block element");
			isBlockElement=TRUE;
		} else if(role==ROLE_SYSTEM_TABLE||role==ROLE_SYSTEM_CELL||role==IA2_ROLE_SECTION||role==ROLE_SYSTEM_DOCUMENT||role==IA2_ROLE_INTERNAL_FRAME||role==IA2_ROLE_UNKNOWN||role==ROLE_SYSTEM_SEPARATOR) {
			DEBUG_MSG(L"role is a known block element role so we should treet this object as a block element");
			isBlockElement=TRUE;
		} else {
			DEBUG_MSG(L"This object is not a block element");
			isBlockElement=FALSE;
		}
	}
	parentNode->setIsBlock(isBlockElement);
	DEBUG_MSG(L"getting accName");
	BSTR name=NULL;
	if((res=pacc->get_accName(varChild,&name))!=S_OK) {
		DEBUG_MSG(L"IAccessible::get_accName returned "<<res);
		name=NULL;
	}
	// Handle table cell information.
	IAccessibleTableCell* paccTableCell = NULL;
	// If paccTable is not NULL, it is the table interface for the table above this object.
	if (paccTable && (res = pacc->QueryInterface(IID_IAccessibleTableCell, (void**)(&paccTableCell))) == S_OK) {
		wostringstream s;
		// tableID is the IAccessible2::uniqueID for paccTable.
		s << tableID;
		parentNode->addAttribute(L"table-id", s.str());
		s.str(L"");
		long row, column, rowExtents, columnExtents;
		boolean isSelected;
		if ((res = paccTableCell->get_rowColumnExtents(&row, &column, &rowExtents, &columnExtents, &isSelected)) == S_OK) {
			DEBUG_MSG(L"IAccessibleTableCell::get_rowColumnExtents succeeded, adding attributes");
			s << row + 1;
			parentNode->addAttribute(L"table-rownumber", s.str());
			s.str(L"");
			s << column + 1;
			parentNode->addAttribute(L"table-columnnumber", s.str());
			if (columnExtents > 1) {
				s.str(L"");
				s << columnExtents;
				parentNode->addAttribute(L"table-columnsspanned", s.str());
			}
			if (rowExtents > 1) {
				s.str(L"");
				s << rowExtents;
				parentNode->addAttribute(L"table-rowsspanned", s.str());
			}
		}
		IUnknown** headerCells;
		long nHeaderCells;
		if ((res = paccTableCell->get_columnHeaderCells(&headerCells, &nHeaderCells)) == S_OK) {
			DEBUG_MSG(L"IAccessibleTableCell::get_columnHeaderCells succeeded, adding header IDs");
			s.str(L"");
			for (int hci = 0; hci < nHeaderCells; hci++) {
				IAccessible2* headerCellPacc = NULL;
				if ((res = headerCells[hci]->QueryInterface(IID_IAccessible2, (void**)(&headerCellPacc))) != S_OK) {
					DEBUG_MSG(L"QueryInterface column header cell " << hci << " to IAccessible2 failed with " << res);
					headerCells[hci]->Release();
					continue;
				}
				headerCells[hci]->Release();
				long headerCellID;
				if ((res = headerCellPacc->get_uniqueID(&headerCellID)) != S_OK) {
					DEBUG_MSG("IAccessible2::get_uniqueID on column header cell " << hci << " failed with " << res);
					headerCellPacc->Release();
					continue;
				}
				s << headerCellID << L",";
				headerCellPacc->Release();
			}
			if (!s.str().empty())
				parentNode->addAttribute(L"table-columnheadercells", s.str());
		}
		if ((res = paccTableCell->get_rowHeaderCells(&headerCells, &nHeaderCells)) == S_OK) {
			DEBUG_MSG(L"IAccessibleTableCell::get_rowHeaderCells succeeded, adding header IDs");
			s.str(L"");
			for (int hci = 0; hci < nHeaderCells; hci++) {
				IAccessible2* headerCellPacc = NULL;
				if ((res = headerCells[hci]->QueryInterface(IID_IAccessible2, (void**)(&headerCellPacc))) != S_OK) {
					DEBUG_MSG(L"QueryInterface row header cell " << hci << " to IAccessible2 failed with " << res);
					headerCells[hci]->Release();
					continue;
				}
				headerCells[hci]->Release();
				long headerCellID;
				if ((res = headerCellPacc->get_uniqueID(&headerCellID)) != S_OK) {
					DEBUG_MSG("IAccessible2::get_uniqueID on row header cell " << hci << " failed with " << res);
					headerCellPacc->Release();
					continue;
				}
				s << headerCellID << L",";
				headerCellPacc->Release();
			}
			if (!s.str().empty())
				parentNode->addAttribute(L"table-rowheadercells", s.str());
		}
		paccTableCell->Release();
		paccTableCell = NULL;
		// We're now within a cell, so descendant nodes shouldn't refer to this table anymore.
		paccTable = NULL;
		tableID = 0;
	}
	// Handle table information.
	// Don't release the table unless it was created in this call.
	bool releaseTable = false;
	map<wstring,wstring>::const_iterator IA2AttribsMapIt;
	// If paccTable is not NULL, we're within a table but not yet within a cell, so don't bother to query for table info.
	if (!paccTable) {
		// Try to get table information.
		DEBUG_MSG(L"paccTable is NULL, trying to get table information");
		DEBUG_MSG(L"get paccTable with IAccessible2::QueryInterface and IID_IAccessibleTable2");
		if((res=pacc->QueryInterface(IID_IAccessibleTable2,(void**)(&paccTable)))!=S_OK&&res!=E_NOINTERFACE) {
			DEBUG_MSG(L"pacc->QueryInterface, with IID_IAccessibleTable, returned "<<res);
			paccTable=NULL;
		}
		DEBUG_MSG(L"paccTable is "<<paccTable);
		if (paccTable) {
			// We did the QueryInterface for paccTable, so we must release it after all calls that use it are done.
			releaseTable = true;
			// This is a table, so add its information as attributes.
			if((IA2AttribsMapIt = IA2AttribsMap.find(L"layout-guess")) != IA2AttribsMap.end()) {
				DEBUG_MSG(L"Found a layout table, setting table-layout attrib");
				parentNode->addAttribute(L"table-layout",L"1");
			}
			wostringstream s;
			tableID = ID;
			s << ID;
			parentNode->addAttribute(L"table-id", s.str());
			s.str(L"");
			long count = 0;
			DEBUG_MSG(L"Getting row count");
			if ((res = paccTable->get_nRows(&count)) == S_OK) {
				DEBUG_MSG(L"row count is " << count);
				s << count;
				parentNode->addAttribute(L"table-rowcount", s.str());
				s.str(L"");
			}
			if ((res = paccTable->get_nColumns(&count)) == S_OK) {
				DEBUG_MSG(L"column count is " << count);
				s << count;
				parentNode->addAttribute(L"table-columncount", s.str());
			}
			// Add the table summary if one is present and the table is visible.
			if (name && width > 0 && height > 0 && (tempNode = buffer->addTextFieldNode(parentNode, previousNode, name)))
				previousNode = tempNode;
		}
	}
	IAccessibleText* paccText=NULL;
	IAccessibleHypertext* paccHypertext=NULL;
	//get IAccessibleText interface
	DEBUG_MSG(L"get paccText with IAccessible2::QueryInterface and IID_IAccessibleText");
	 if((res=pacc->QueryInterface(IID_IAccessibleText,(void**)(&paccText)))!=S_OK&&res!=E_NOINTERFACE) {
		DEBUG_MSG(L"pacc->QueryInterface, with IID_IAccessibleText, returned "<<res);
		paccText=NULL;
	}
	DEBUG_MSG(L"paccText is "<<paccText);
	//Get IAccessibleHypertext interface
	DEBUG_MSG(L"get paccHypertext with IAccessible2::QueryInterface and IID_IAccessibleHypertext");
	 if((res=pacc->QueryInterface(IID_IAccessibleHypertext,(void**)(&paccHypertext)))!=S_OK&&res!=E_NOINTERFACE) {
		DEBUG_MSG(L"pacc->QueryInterface, with IID_IAccessibleHypertext, returned "<<res);
		paccHypertext=NULL;
	}
	DEBUG_MSG(L"paccHypertext is "<<paccHypertext);
	//Get the text from the IAccessibleText interface
	DEBUG_MSG(L"LGet IA2Text with IAccessibleText::text");
	BSTR IA2Text=NULL;
	if(paccText&&(res=paccText->get_text(0,-1,&IA2Text))!=S_OK) {
		DEBUG_MSG(L"paccText->text, from 0 to -1 (end), returned "<<res);
		IA2Text=NULL;
	}
	if(IA2Text!=NULL) {
		DEBUG_MSG(L"got IA2Text");
	} else {
		DEBUG_MSG(L"IA2Text is NULL");
	}
	//Get the text length
	DEBUG_MSG(L"get IA2TextLength with SysStringLen");
	int IA2TextLength=0;
	if(IA2Text!=NULL) {
		IA2TextLength=SysStringLen(IA2Text);
	}
	DEBUG_MSG(L"IA2TextLength is "<<IA2TextLength);
	int IA2TextIsUnneededSpace=1;
	if(IA2TextLength>0&&(role!=ROLE_SYSTEM_TEXT||(states&STATE_SYSTEM_READONLY))&&!(IA2States&IA2_STATE_EDITABLE)) {
		for(int i=0;i<IA2TextLength;++i) {
			if(IA2Text[i]==L'\n'||IA2Text[i]==L'\xfffc'||!iswspace(IA2Text[i])) {
				DEBUG_MSG(L"IA2Text is not whitespace");
				IA2TextIsUnneededSpace=0;
				break;
			}
		}
		if(IA2TextIsUnneededSpace) {
			DEBUG_MSG(L"IA2Text is whitespace");
		}
	} else {
		IA2TextIsUnneededSpace=0;
	}
	DEBUG_MSG(L"getting accValue");
	BSTR value=NULL;
	if((res=pacc->get_accValue(varChild,&value))!=S_OK) {
		DEBUG_MSG(L"IAccessible::get_accValue returned "<<res);
		value=NULL;
	}
	if(value!=NULL&&SysStringLen(value)==0) {
		SysFreeString(value);
		value=NULL;
	}
	//Get the child count
	int childCount=0;
	if(IA2TextIsUnneededSpace||role==ROLE_SYSTEM_COMBOBOX||(role==ROLE_SYSTEM_LIST&&!(states&STATE_SYSTEM_READONLY))||role==IA2_ROLE_UNKNOWN||role==IA2_ROLE_EMBEDDED_OBJECT) {
		DEBUG_MSG(L"Forcing childCount to 0 as we don't want this node's children");
		childCount=0;
	} else {
		DEBUG_MSG(L"get childCount with IAccessible::get_accChildCount");
		if((res=pacc->get_accChildCount((long*)(&childCount)))!=S_OK) {
		DEBUG_MSG(L"pacc->get_accChildCount returned "<<res);
			childCount=0;
		}
		DEBUG_MSG(L"childCount is "<<childCount);
	}
	//If this isn't a button or a graphic, then add the name as a field attribute
	if(role!=ROLE_SYSTEM_LINK&&role!=ROLE_SYSTEM_PUSHBUTTON&&role!=ROLE_SYSTEM_GRAPHIC&&name!=NULL) {
		parentNode->addAttribute(L"name",name);
	}
	if(childCount>0||(width>0&&height>0)) {
		//If there is an IAccessibleHypertext interface, then we should scan for embedded object chars
		//treet the text between the embedded object chars as normal text
		//Look up the IAccessible2 objects at the positions of the embedded object chars
		//Add the text and IA2 objects in order to a vector for later adding to the buffer
		if(paccHypertext&&IA2Text!=NULL&&IA2TextLength>0&&!IA2TextIsUnneededSpace) {
		DEBUG_MSG(L"scanning text for embedded object chars");
			int textStart=-1;
			wchar_t* tempText=NULL;
			for(int i=0;i<IA2TextLength;++i) {
				DEBUG_MSG(L"offset "<<i);
				if(IA2Text[i]!=0xfffc) { //is not an embeded object char
					DEBUG_MSG(L"normal char");
					if(tempText==NULL) {
						textStart=i;
						DEBUG_MSG(L"allocating new tempText memory to hold "<<((IA2TextLength+1)-i)<<L" chars");
						tempText=(wchar_t*)malloc(sizeof(wchar_t)*((IA2TextLength+1)-i));
						if(tempText==NULL) {
							DEBUG_MSG(L"Error allocating tempText memory");
							return NULL;
						}
					}
					tempText[i-textStart]=IA2Text[i];
				} else { //is an embedded object char
					DEBUG_MSG(L"is an embedded object char");
					if(tempText!=NULL) {
						DEBUG_MSG(L"there is tempText, terminate it with NULL");
						tempText[i-textStart]=L'\0';
						DEBUG_MSG(L"adding tempText of length "<<(i-textStart)+1<<L" to buffer");
						if((tempNode=buffer->addTextFieldNode(parentNode,previousNode,tempText))!=NULL) {
							previousNode=tempNode;
						}
						free(tempText);
						tempText=NULL;
					}
					DEBUG_MSG(L"get hyperlinkIndex with IAccessibleHypertext::get_hyperlinkIndex and offset "<<i);
					int hyperlinkIndex;
					if((res=paccHypertext->get_hyperlinkIndex(i,(long*)(&hyperlinkIndex)))!=S_OK) {
						DEBUG_MSG(L"paccHypertext->hyperlinkIndex with offset "<<i<<L" returned "<<res);
						continue;
					}
					DEBUG_MSG(L"hyperlinkIndex is "<<hyperlinkIndex);
					DEBUG_MSG(L"get paccHyperlink with IAccessibleHypertext::get_hyperlink and index "<<hyperlinkIndex);
					IAccessibleHyperlink* paccHyperlink=NULL;
					if((res=paccHypertext->get_hyperlink(hyperlinkIndex,&paccHyperlink))!=S_OK) {
						DEBUG_MSG(L"pacc->hyperlink with index of "<<hyperlinkIndex<<L" returned "<<res);
						continue;
					}
					DEBUG_MSG(L"get childPacc with IAccessibleHyperlink::QueryInterface and IID_IAccessible2");
					IAccessible2* childPacc=NULL;
					if((res=paccHyperlink->QueryInterface(IID_IAccessible2,(void**)(&childPacc)))!=S_OK) {
						DEBUG_MSG(L"paccHyperlink->QueryInterface with IID_IAccessible2, returned "<<res);
						paccHyperlink->Release();
						continue;
					}
					DEBUG_MSG(L"Release paccHyperlink");
					paccHyperlink->Release();
					#if IGNORE_UNNEEDED_GRAPHICS_IN_LINKS&&IGNORE_NONINTERACTIVE_UNLABELED_GRAPHICS
					long childRole;
					BSTR childName=NULL;
					BSTR childDefaction=NULL;
						//role must be link, must have name, 
					//childRole must be graphic, must have no or empty childName, childDefaction can't be click.
					if(role==ROLE_SYSTEM_LINK&&name!=NULL&&!isWhitespace(name)&&childPacc->role(&childRole)==S_OK&&childRole==ROLE_SYSTEM_GRAPHIC&&(childPacc->get_accName(varChild,&childName)!=S_OK||childName==NULL||SysStringLen(childName)==0)&&(childPacc->get_accDefaultAction(varChild,&childDefaction)==S_OK||wcscmp(childDefaction?childDefaction:L"",L"click")!=0)) {
						DEBUG_MSG(L"Ignoring unneeded graphic in link");
						if(childName) SysFreeString(childName);
						if(childDefaction) SysFreeString(childDefaction);
					childPacc->Release();
						continue;
					}
					if(childName) SysFreeString(childName);
					if(childDefaction) SysFreeString(childDefaction);
					#endif
					DEBUG_MSG(L"calling fillVBuf with childPacc ");
					if((tempNode=fillVBuf(childPacc,buffer,parentNode,previousNode,paccTable,tableID))!=NULL) {
						previousNode=tempNode;
					} else {
						DEBUG_MSG(L"Error in fillVBuf");
					}
					childPacc->Release();
				}
			}
			DEBUG_MSG(L"End of scan");
			if(tempText!=NULL) {
				DEBUG_MSG(L"some tempText left, terminate with NULL");
				tempText[IA2TextLength-textStart]=L'\0';
				DEBUG_MSG(L"add tempText of length "<<(IA2TextLength-textStart)+1<<L" to buffer");
				previousNode=buffer->addTextFieldNode(parentNode,previousNode,tempText);
				free(tempText);
				tempText=NULL;
			}
		} else  if(IA2TextLength>0&&!IA2TextIsUnneededSpace) {
			DEBUG_MSG(L"add IA2Text to childVector");
			if((tempNode=buffer->addTextFieldNode(parentNode,previousNode,IA2Text))!=NULL) {
				previousNode=tempNode;
			}
		} 
		if(IA2Text!=NULL) {
			DEBUG_MSG(L"Freeing IA2Text");
			SysFreeString(IA2Text);
		}
		if(IA2TextLength==0||IA2TextIsUnneededSpace) {
			DEBUG_MSG(L"object had no text");
			//If the object has no text at all then we need to get children the ol' fassion way
			if(childCount>0) {
				DEBUG_MSG(L"Allocate memory to hold children");
				VARIANT* varChildren;
				if((varChildren=(VARIANT*)malloc(sizeof(VARIANT)*childCount))==NULL) {
					DEBUG_MSG(L"Error allocating varChildren memory");
					return NULL;
				}
				DEBUG_MSG(L"Fetch children with AccessibleChildren");
				if((res=AccessibleChildren(pacc,0,childCount,varChildren,(long*)(&childCount)))!=S_OK) {
					DEBUG_MSG(L"AccessibleChildren returned "<<res);
					childCount=0;
				}
				DEBUG_MSG(L"got "<<childCount<<L" children");
				for(int i=0;i<childCount;++i) {
					DEBUG_MSG(L"child "<<i);
					if(varChildren[i].vt==VT_DISPATCH) {
						DEBUG_MSG(L"QueryInterface dispatch child to IID_IAccesible2");
						IAccessible2* childPacc=NULL;
						if((res=varChildren[i].pdispVal->QueryInterface(IID_IAccessible2,(void**)(&childPacc)))!=S_OK) {
							DEBUG_MSG(L"varChildren["<<i<<L"].pdispVal->QueryInterface to IID_iAccessible2 returned "<<res);
							childPacc=NULL;
						}
						if(childPacc) {
							DEBUG_MSG(L"calling _filVBufHelper with child object ");
							if((tempNode=fillVBuf(childPacc,buffer,parentNode,previousNode,paccTable,tableID))!=NULL) {
								previousNode=tempNode;
							} else {
								DEBUG_MSG(L"Error in calling fillVBuf");
							}
							DEBUG_MSG(L"releasing child IAccessible2 object");
							childPacc->Release();
						}
					}
					VariantClear(&(varChildren[i]));
				}
				DEBUG_MSG(L"Freeing memory holding children");
				free(varChildren);
			}
			if(childCount==0) {
				DEBUG_MSG(L"ChildCount is 0, so add accessible value or name as text");
				if(role==ROLE_SYSTEM_LINK||role==ROLE_SYSTEM_PUSHBUTTON||role==ROLE_SYSTEM_MENUITEM) {
					DEBUG_MSG(L"For buttons and links we use the name as the text");
					if(name!=NULL) {
						DEBUG_MSG(L"adding name to buffer");
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,name);
					} else if((role==ROLE_SYSTEM_LINK)&&(value!=NULL)) {
						wchar_t* newValue=_wcsdup(getNameForURL(value).c_str());
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,newValue);
						free(newValue);
					} else if(value!=NULL) {
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,value);
					} else if(width>0||height>0) {
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,L" ");
					}
				} else if(role==ROLE_SYSTEM_GRAPHIC) {
					DEBUG_MSG(L"For graphics we use the name as the text");
					int isClickable=(wcscmp(defaction?defaction:L"",L"click")==0);
					int inLink=(states&STATE_SYSTEM_LINKED);
					// Unneeded graphics in links are handled elsewhere, so if we see alt="" here, we should ignore alt and fall back.
					// However, if we see alt="" for a clickable, use the alt and don't fall back.
					if(name!=NULL&&(SysStringLen(name)>0||isClickable)) {
						DEBUG_MSG(L"adding name to buffer");
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,name);
					} else if((value!=NULL)&&(!IGNORE_NONINTERACTIVE_UNLABELED_GRAPHICS||(!isClickable&&inLink))) {
						wchar_t* newValue=_wcsdup(getNameForURL(value).c_str());
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,newValue);
						free(newValue);
					} else if((IA2AttribsMap.count(L"src")>0)&&(!IGNORE_NONINTERACTIVE_UNLABELED_GRAPHICS||(isClickable||inLink))) {
						wchar_t* newValue=_wcsdup(getNameForURL(IA2AttribsMap[L"src"]).c_str());
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,newValue);
						free(newValue);
					}
				} else {
					if(value!=NULL) {
						DEBUG_MSG(L"adding value to buffer");
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,value);
					} else if(role!=ROLE_SYSTEM_CELL&&role!=IA2_ROLE_SECTION&&(width>0&&height>0)) {
						previousNode=buffer->addTextFieldNode(parentNode,previousNode,L" ");
					}
				}
			}
		}
		if ((role == ROLE_SYSTEM_CELL || role == ROLE_SYSTEM_ROWHEADER || role == ROLE_SYSTEM_COLUMNHEADER) && parentNode->getLength() == 0) {
			// Always render a space for empty table cells.
			previousNode=buffer->addTextFieldNode(parentNode,previousNode,L" ");
			parentNode->setIsBlock(false);
		}
	}
	//Free any objects and text etc we don't need, before doing any recursion to save memory
	if(name!=NULL) {
		SysFreeString(name);
	}
	if(value!=NULL) {
		SysFreeString(value);
	}
	if(defaction!=NULL) {
		SysFreeString(defaction);
		defaction=NULL;
	}
	DEBUG_MSG(L"Release pacc");
	if(paccText!=NULL) {
		DEBUG_MSG(L"Release paccText");
		paccText->Release();
	}
	if(paccHypertext!=NULL) {
		DEBUG_MSG(L"Release paccHypertext");
		paccHypertext->Release();
	}
	if (releaseTable) {
		DEBUG_MSG(L"Release paccTable");
		paccTable->Release();
	}
	DEBUG_MSG(L"Returning node at "<<parentNode);
	return parentNode;
}

bool getDocumentFrame(HWND* hwnd, long* childID) {
	int res;
	IAccessible2* pacc=IAccessible2FromIdentifier((int)*hwnd,*childID);
	if (!pacc) {
		DEBUG_MSG(L"Could not get IAccessible2 object");
		return false;
	}
	DEBUG_MSG(L"got IAccessible2 object at "<<pacc);

	IAccessible2* parentPacc=NULL;
	VARIANT varChild;
	varChild.vt=VT_I4;
	varChild.lVal=*childID;
	VARIANT varDisp;
	if((res=pacc->accNavigate(NAVRELATION_NODE_CHILD_OF,varChild,&varDisp))!=S_OK) {
		DEBUG_MSG(L"failed to get object from node_child_of relation");
		pacc->Release();
		return false;
	}

	if(varDisp.vt!=VT_DISPATCH) {
		DEBUG_MSG(L"variant from node_child_of relation does not hold an IDispatch");
		VariantClear(&varDisp);
		pacc->Release();
		return false;
	}
	DEBUG_MSG(L"got IDispatch object at "<<varDisp.pdispVal<<L" for node_child_of relation");

	if((res=varDisp.pdispVal->QueryInterface(IID_IAccessible2,(void**)&parentPacc))!=S_OK) {
		DEBUG_MSG(L"Could not queryInterface to IAccessible2 from IDispatch for node_child_of relation");
		VariantClear(&varDisp);
		pacc->Release();
		return false;
	}
	DEBUG_MSG(L"got IAccessible2 object at "<<parentPacc<<L" from node_child_of relation");
	VariantClear(&varDisp);

	if(parentPacc==pacc) {
		DEBUG_MSG(L"parentPacc and pacc are equal, bad relation");
		parentPacc->Release();
		pacc->Release();
		return false;
	}

	long role;
	if((res=parentPacc->role(&role))!=S_OK||role!=IA2_ROLE_INTERNAL_FRAME) {
		DEBUG_MSG(L"parentPacc is not a frame");
		parentPacc->Release();
		pacc->Release();
		return false;
	}

	if(((res=parentPacc->get_uniqueID((long*)childID))!=S_OK)||*childID>=0) {
		DEBUG_MSG(L"could not get valid uniqueID from parentPacc");
		parentPacc->Release();
		pacc->Release();
		return false;
	}
	DEBUG_MSG(L"got uniqueID "<<*childID<<L" from parentPacc");

	if((res=parentPacc->get_windowHandle(hwnd))!=S_OK) {
		DEBUG_MSG(L"Could not get valid window handle from parentPacc");
		parentPacc->Release();
		pacc->Release();
		return false;
	}
	DEBUG_MSG(L"got windowhandle "<<*hwnd<<L" from parentPacc");

	parentPacc->Release();
	pacc->Release();

	return true;
}

void CALLBACK GeckoVBufBackend_t::renderThread_winEventProcHook(HWINEVENTHOOK hookID, DWORD eventID, HWND hwnd, long objectID, long childID, DWORD threadID, DWORD time) {
	switch(eventID) {
		case IA2_EVENT_TEXT_INSERTED:
		case IA2_EVENT_TEXT_REMOVED:
		case EVENT_OBJECT_REORDER:
		case EVENT_OBJECT_NAMECHANGE:
		case EVENT_OBJECT_VALUECHANGE:
		case EVENT_OBJECT_DESCRIPTIONCHANGE:
		case EVENT_OBJECT_STATECHANGE:
		case IA2_EVENT_OBJECT_ATTRIBUTE_CHANGED:
		break;
		default:
		return;
	}
	if(childID>=0||objectID!=OBJID_CLIENT) {
		return;
	}
	DEBUG_MSG(L"winEvent for window "<<hwnd);
	hwnd=findRealMozillaWindow(hwnd);
	if(hwnd==0) {
		DEBUG_MSG(L"Invalid window");
		return;
	}
	int docHandle=(int)hwnd;
	int ID=childID;
	VBufBackend_t* backend=NULL;
	DEBUG_MSG(L"Searching for backend in collection of "<<runningBackends.size()<<L" running backends");
	for(VBufBackendSet_t::iterator i=runningBackends.begin();i!=runningBackends.end();++i) {
		HWND rootWindow=(HWND)((*i)->rootDocHandle);
		DEBUG_MSG(L"Comparing backends root window "<<rootWindow<<L" with window "<<hwnd);
		if(rootWindow==hwnd||IsChild(rootWindow,hwnd)) {
			backend=(*i);
		}
	}
	if(backend==NULL) {
		return;
	}
	DEBUG_MSG(L"found active backend for this window at "<<backend);
	//Ignore state change events on the root node (document) as it can cause rerendering when the document goes busy
	if(eventID==EVENT_OBJECT_STATECHANGE&&hwnd==(HWND)(backend->rootDocHandle)&&childID==backend->rootID) return;
	VBufStorage_controlFieldNode_t* node=backend->getControlFieldNodeWithIdentifier(docHandle,ID);
	if(node==NULL&&eventID==EVENT_OBJECT_STATECHANGE) {
		// This event is possibly due to a new document loading in a subframe.
		// Gecko doesn't fire a reorder on the iframe (Mozilla bug 420845), so we need to use NODE_CHILD_OF in this case so that frames will reload.
		DEBUG_MSG(L"State change on an unknown node in a subframe, try NODE_CHILD_OF");
		if (getDocumentFrame(&hwnd, &childID)) {
			#ifdef DEBUG
			Beep(2000,50);
			#endif
			DEBUG_MSG(L"Got NODE_CHILD_OF, recursing");
			renderThread_winEventProcHook(hookID,eventID,hwnd,OBJID_CLIENT,childID,threadID,time);
		} else {
			DEBUG_MSG(L"NODE_CHILD_OF failed, returning");
		}
		return;
	}
	if(node==NULL) {
		DEBUG_MSG(L"No nodes to use, returning");
		return;
	}
	DEBUG_MSG(L"Invalidating subtree with node at "<<node);
	backend->invalidateSubtree(node);
}

void GeckoVBufBackend_t::renderThread_initialize() {
	registerWinEventHook(renderThread_winEventProcHook);
	DEBUG_MSG(L"Registered win event callback");
	VBufBackend_t::renderThread_initialize();
}

void GeckoVBufBackend_t::renderThread_terminate() {
	unregisterWinEventHook(renderThread_winEventProcHook);
	DEBUG_MSG(L"Unregistered winEvent hook");
	VBufBackend_t::renderThread_terminate();
}

void GeckoVBufBackend_t::render(VBufStorage_buffer_t* buffer, int docHandle, int ID, VBufStorage_controlFieldNode_t* oldNode) {
	DEBUG_MSG(L"Rendering from docHandle "<<docHandle<<L", ID "<<ID<<L", in to buffer at "<<buffer);
	IAccessible2* pacc=IAccessible2FromIdentifier(docHandle,ID);
	if(pacc==NULL) {
		DEBUG_MSG(L"Could not get IAccessible2, returning");
		return;
	}
	DEBUG_MSG(L"Calling fillVBuf");
	fillVBuf(pacc, buffer, NULL, NULL);
	pacc->Release();
	DEBUG_MSG(L"Rendering done");
}

GeckoVBufBackend_t::GeckoVBufBackend_t(int docHandle, int ID): VBufBackend_t(docHandle,ID) {
	DEBUG_MSG(L"Gecko backend constructor");
}

GeckoVBufBackend_t::~GeckoVBufBackend_t() {
	DEBUG_MSG(L"Gecko backend destructor");
}

extern "C" __declspec(dllexport) VBufBackend_t* VBufBackend_create(int docHandle, int ID) {
	VBufBackend_t* backend=new GeckoVBufBackend_t(docHandle,ID);
	DEBUG_MSG(L"Created new backend at "<<backend);
	return backend;
}
