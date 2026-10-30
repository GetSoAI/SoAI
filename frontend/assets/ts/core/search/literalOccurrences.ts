/* SoAI - Literal overlapping search with stable UTF-16 offsets [frontend/assets/ts/core/search/literalOccurrences.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { unicodeCodePointLength } from '@core/primitives/text.ts';
import type { SearchWorkBudget } from '@core/search/searchWorkBudget.ts';

interface LiteralSearchQuery {
    foldedText: string;
}

interface LiteralOccurrenceScanResult {
    count: number;
    stopped: boolean;
}

const LITERAL_SEARCH_CHUNK_LENGTH = 8192;

const foldSearchCodePoint = (character: string): string => {
    const lower = character.toLowerCase();
    return lower.length === character.length && (lower.length === 1 || unicodeCodePointLength(lower) === 1) ? lower : character;
};

const createLiteralSearchQuery = (text: string): LiteralSearchQuery => ({ foldedText: Array.from(text, foldSearchCodePoint).join('') });

const isLiteralSearchOffsetBoundary = (text: string, offset: number): boolean => {
    if (offset === 0 || offset === text.length) return true;
    const previous = text.charCodeAt(offset - 1);
    const current = text.charCodeAt(offset);
    return !(previous >= 0xd800 && previous <= 0xdbff && current >= 0xdc00 && current <= 0xdfff);
};

const scanLiteralOccurrences = async (text: string, query: LiteralSearchQuery, budget: SearchWorkBudget, visitMatch?: (offset: number) => boolean): Promise<LiteralOccurrenceScanResult> => {
    await budget.checkpoint();
    if (!query.foldedText) return { count: 0, stopped: false };
    const foldedChunks: string[] = [];
    let chunk: string[] = [];
    let chunkLength = 0;
    for (const character of text) {
        chunk.push(foldSearchCodePoint(character));
        chunkLength += character.length;
        if (chunkLength >= LITERAL_SEARCH_CHUNK_LENGTH) {
            foldedChunks.push(chunk.join(''));
            chunk = [];
            chunkLength = 0;
            await budget.checkpoint();
        }
    }
    foldedChunks.push(chunk.join(''));
    const foldedText = foldedChunks.join('');
    let count = 0;
    for (let chunkStart = 0; chunkStart < foldedText.length; chunkStart += LITERAL_SEARCH_CHUNK_LENGTH) {
        const chunkEnd = Math.min(foldedText.length, chunkStart + LITERAL_SEARCH_CHUNK_LENGTH);
        const searchChunk = foldedText.slice(chunkStart, chunkEnd + query.foldedText.length - 1);
        let offset = searchChunk.indexOf(query.foldedText);
        while (offset >= 0 && chunkStart + offset < chunkEnd) {
            const matchOffset = chunkStart + offset;
            if (isLiteralSearchOffsetBoundary(text, matchOffset) && isLiteralSearchOffsetBoundary(text, matchOffset + query.foldedText.length)) {
                count += 1;
                if (visitMatch?.(matchOffset) === false) return { count, stopped: true };
                if (count % 128 === 0) await budget.checkpoint();
            }
            const character = text.codePointAt(matchOffset);
            offset = searchChunk.indexOf(query.foldedText, offset + (character !== undefined && character > 0xffff ? 2 : 1));
        }
        await budget.checkpoint();
    }
    return { count, stopped: false };
};

export { createLiteralSearchQuery, isLiteralSearchOffsetBoundary, scanLiteralOccurrences };
export type { LiteralOccurrenceScanResult, LiteralSearchQuery };
