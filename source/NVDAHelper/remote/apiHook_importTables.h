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

#ifndef _APIHOOK_H
#define _APIHOOK_H

#ifdef __CPLUSCPLUS
extern "C" {
#endif

/**
 * Requests that the given function from the given module should be hooked with the given hook procedure. Note that hooking does not automatically take place when this function is called, so this function can be called many times before the actual hooking can be done in bulk with apiHooks_hookFunctions. 
 * @param moduleName the name of the module the function you wish to hook is located in.
 * @param functionName the name of the function you wish to hook.
 * @param newHookProc the function you wish  to be called instead of the original one.
 * @return the address of the original function. You could use this to call the origianl function from with in your replacement.
 */ 
void* apiHook_requestFunctionHook(const char* moduleName, const char* functionName, void* newHookProc);

/**
 * Hooks all the functions requested with apiHooks_requestFunctionHook.
 * @return true if it succeeded, false otherwize.
 */
BOOL apiHook_hookFunctions();

/**
 * Unhooks any functions previously hooked.
 */
BOOL apiHook_unhookFunctions();

#ifdef __CPLUSCPLUS
extern "C" {
#endif

#endif
