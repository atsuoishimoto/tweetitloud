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

#ifndef NVDAHELPER_REMOTE_DISPLAYMODEL_H
#define NVDAHELPER_REMOTE_DISPLAYMODEL_H

#include <map>
#include <deque>
#include <windows.h>
#include <common/lock.h>

struct displayModelChunk_t{
	RECT rect;
	int baselineFromTop;
	std::wstring text;
	std::deque<int> characterXArray;
/**
 * Truncates the chunk's text so that only the text that fits in the resulting rectangle is left.  
 * @param truncatePointX the x position at which to truncate
 * @param truncateBefore if true then the chunk is truncated from the left all the way up to  truncation point, if false then its truncated from the point to the end.
 */
	void truncate(int truncatePointX, BOOL truncateBefore);
};

typedef std::map<std::pair<int,int>,displayModelChunk_t*> displayModelChunksByPointMap_t;

/**
 * Holds rectanglular chunks of text, and allows inserting chunks, clearing rectangles, and rendering text in a given rectangle.
 */
class displayModel_t: public LockableAutoFreeObject  {
	private:
	displayModelChunksByPointMap_t chunksByYX; //indexes the chunks by y,x

	protected:

/**
 * Overloaded insertChunk to take an already made chunk
 * @param chunk an already made chunk
 */
	void insertChunk(displayModelChunk_t* chunk);

/**
 * destructor
 */
	virtual ~displayModel_t();

	public:

/**
 * constructor
 */
	displayModel_t();

/**
 * Finds out how many chunks this model contains.
 */
	int getChunkCount();

/**
 * Inserts a text chunk in to the model.
 * @param rect the rectangle bounding the text.
 * @param text the string of unicode text in the chunk.
 * @param characterEndXArray an array of x positions for the end of each character.
 * @param clippingRect a optional pointer to a rectangle which if specified will be used to clip the text so that none falls outside this rectangle. 
 */
	void insertChunk(const RECT& rect, int baselineFromTop, const std::wstring& text, int* characterEndXArray, const RECT* clippingRect);

/**
 * Removes all chunks intersecting the given rectangle. Currently this must be called before inserting chunks as chunks should never overlap.
 * @param rect the rectangle to clear.
 * @param clearForText if true then  the part of any chunk  covered by the rectangle will definitly be removed to make way for text. If False  chunks will only be removed/mutated if the rectangle starts at or outside of, the chunk and overlaps it, or covers the chunk's baseline. 
 */
	void clearRectangle(const RECT& rect, BOOL clearForText=FALSE);

/**
 * Removes all content from this display model.
 */
	void clearAll();

/**
 * Copies the chunks intersecting the given rectangle, in to the given display model, starting from the given coordinates.
 * @param srcRect the rectangle intersecting all the chunks in this model that will be copied.
 * @param removeFromSource if true then the content will be moved, rather than copied
 * @param opaqueCopy if true then the entire destination rectangle will be cleared before inserting any chunks, but if false then only space for each chunk will be cleared.
 * @param destX the x coordinate in the destination model where the rectangle's left edge  starts
 * @param destY the y coordinate in the destnation model where the rectangle's top edge starts
 * @param destClippingRect an optional rectangle which will be used to clip all content being copied in to the destination model
 * @param destModel a pointer to the displayModel the chunks should be copied to (if NULL then this model is used) 
 */
	void copyRectangle(const RECT& srcRect, BOOL removeFromSource, BOOL opaqueCopy, int destX, int destY, const RECT* destClippingRect, displayModel_t* destModel);

/**
 * Fetches the text contained in all chunks intersecting the given rectangle if provided, otherwize the text from all chunks in the model.
 * The chunks are ordered by Y and then by x.
 * @param rect the retangle which intersects the wanted chunks.
 * @param text a string in which all the rendered text will be placed.
 * @param characterPoints a deque in which the points for each character in text will be placed.
 */
	void renderText(const RECT& rect, const int minHorizontalWhitespace, const int minVerticalWhitespace, const bool stripOuterWhitespace, std::wstring& text, std::deque<RECT>& characterRects);

};

#endif
