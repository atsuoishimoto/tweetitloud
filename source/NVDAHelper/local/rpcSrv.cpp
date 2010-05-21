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

#include <cstdio>
#include <sstream>
#include <windows.h>
#include "nvdaController.h"
#include "nvdaControllerInternal.h"
#include <common/winIPCUtils.h>
#include "rpcSrv.h"

RPC_IF_HANDLE availableInterfaces[]={
	nvdaController_NvdaController_v1_0_s_ifspec,
	nvdaControllerInternal_NvdaControllerInternal_v1_0_s_ifspec
};


//memory allocation functions

void* __RPC_USER midl_user_allocate(size_t size) {
	return malloc(size);
}

void __RPC_USER midl_user_free(void* p) {
	free(p);
}

RPC_STATUS startServer() {
	RPC_STATUS status;
	//Set the protocol
	wchar_t endpointString[64];
	getNVDAControllerNcalrpcEndpointString(endpointString,64,FALSE);
	status=RpcServerUseProtseqEp((RPC_WSTR)L"ncalrpc",RPC_C_PROTSEQ_MAX_REQS_DEFAULT,(RPC_WSTR)endpointString,NULL);
	//We can ignore the error where the endpoint is already set
	if(status!=RPC_S_OK&&status!=RPC_S_DUPLICATE_ENDPOINT) {
		return status;
	}
	//Register the interfaces
	for(int i=0;i<ARRAYSIZE(availableInterfaces);i++) {
		if((status=RpcServerRegisterIf(availableInterfaces[i],NULL,NULL))!=RPC_S_OK) {
			return status;
		}
	}
	//Start listening
	if((status=RpcServerListen(1,RPC_C_LISTEN_MAX_CALLS_DEFAULT,TRUE))!=RPC_S_OK) {
		return status;
	}
	CreateThread(NULL,0,(LPTHREAD_START_ROUTINE)RpcMgmtWaitServerListen,NULL,0,NULL);
	return status;
}

RPC_STATUS stopServer() {
	RPC_STATUS status;
	for(int i=0;i<ARRAYSIZE(availableInterfaces);i++) {
		if((status=RpcServerUnregisterIf(availableInterfaces[i],NULL,1))!=RPC_S_OK) {
			return status;
		}
	}
	return RpcMgmtStopServerListening(NULL); 
}
