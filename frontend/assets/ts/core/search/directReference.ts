/* SoAI - Pasted direct reference parsing for search queries [frontend/assets/ts/core/search/directReference.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseConversationId } from '@core/chat/conversationIdentifier.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { containsSoaiPathToken, extractSoaiPathTokenTexts } from '@core/soailinks/codec.ts';

type SearchDirectReference = Readonly<{ kind: 'conversation'; conversationId: string }> | Readonly<{ kind: 'soaiPath'; virtualPath: string }>;

const parseWholeSoaiPathToken = (query: string): string | null => {
    if (!containsSoaiPathToken(query)) {
        return null;
    }
    try {
        const tokens = extractSoaiPathTokenTexts(query);
        const token = tokens.length === 1 ? tokens[0] : undefined;
        if (token === undefined || token.startIndex !== 0 || token.endIndex !== query.length) {
            return null;
        }
        return toTrimmedString(token.virtualPath) || null;
    } catch (error) {
        errorHandler.debug('SearchDirectReference', 'Pasted SoAI path token could not be decoded', ensureError(error));
        return null;
    }
};

const parseSearchDirectReference = (rawQuery: string): SearchDirectReference | null => {
    const query = toTrimmedString(rawQuery);
    if (!query) {
        return null;
    }
    const conversationId = parseConversationId(query);
    if (conversationId !== null) {
        return { kind: 'conversation', conversationId };
    }
    const virtualPath = parseWholeSoaiPathToken(query);
    if (virtualPath !== null) {
        return { kind: 'soaiPath', virtualPath };
    }
    return null;
};

const queryReferencesConversationOnly = (rawQuery: string): boolean => parseSearchDirectReference(rawQuery)?.kind === 'conversation';

export { parseSearchDirectReference, queryReferencesConversationOnly };
export type { SearchDirectReference };
