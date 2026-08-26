/* SoAI - Chat sidebar device-local scroll position persistence [frontend/assets/ts/pages/chat/controllers/page/renderer/conversationListScrollState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { readStorageJson, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { isNumber, isObject, isString } from '@core/typeGuards.ts';
import type { JsonRecord } from '@core/types/jsonValues.ts';
import type { CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/public.ts';

const CONVERSATION_LIST_SCROLL_STORAGE_KEY = 'soai.chat.conversation_list_scroll.v1';

interface ConversationListScrollState extends JsonRecord {
    conversationId: string;
    followingConversationId: string | null;
    precedingConversationId: string | null;
    offset: number;
    atStart: boolean;
}

const normalizeConversationId = (value: string | null): string | null => (value !== null && value.trim() ? value : null);

const isScrollState = (value: ReturnType<typeof readStorageJson>): value is ConversationListScrollState => {
    if (!isObject(value)) return false;
    const conversationId = value['conversationId'];
    const followingConversationId = value['followingConversationId'];
    const precedingConversationId = value['precedingConversationId'];
    return isString(conversationId) && conversationId.trim().length > 0 && (followingConversationId === null || isString(followingConversationId)) && (precedingConversationId === null || isString(precedingConversationId)) && isNumber(value['offset']) && Number.isFinite(value['offset']) && typeof value['atStart'] === 'boolean';
};

const readConversationListScrollState = (): ConversationListScrollState | null => {
    try {
        const stored = readStorageJson('sessionStorage', CONVERSATION_LIST_SCROLL_STORAGE_KEY);
        return isScrollState(stored) ? stored : null;
    } catch (error) {
        errorHandler.warn('ConversationListScrollState', 'Failed to read the device-local conversation list scroll position', ensureError(error));
        return null;
    }
};

const writeConversationListScrollState = (container: HTMLElement, conversationIds: readonly string[]): void => {
    const viewportTop = measureLayoutBox(container).top;
    const atStart = container.scrollTop <= 0;
    for (const child of container.children) {
        if (!(child instanceof HTMLElement)) continue;
        const conversationId = normalizeConversationId(child.dataset['collectionId'] ?? null);
        if (conversationId === null) continue;
        const index = conversationIds.indexOf(conversationId);
        if (index < 0 || measureLayoutBox(child).bottom <= viewportTop) continue;
        const followingConversationId = normalizeConversationId(conversationIds[index + 1] ?? null);
        const precedingConversationId = normalizeConversationId(conversationIds[index - 1] ?? null);
        const state: ConversationListScrollState = { conversationId, followingConversationId, precedingConversationId, offset: measureLayoutBox(child).top - viewportTop, atStart };
        try {
            writeStorageJson('sessionStorage', CONVERSATION_LIST_SCROLL_STORAGE_KEY, state);
        } catch (error) {
            errorHandler.warn('ConversationListScrollState', 'Failed to save the device-local conversation list scroll position', ensureError(error));
        }
        return;
    }
};

const resolveConversationListScrollAnchor = (state: ConversationListScrollState | null, conversationIds: readonly string[]): CollectionViewportAnchor | null => {
    if (state === null) return null;
    const candidates = [state.conversationId, state.followingConversationId, state.precedingConversationId];
    for (const conversationId of candidates) {
        if (conversationId === null || !conversationIds.includes(conversationId)) continue;
        return { identifier: conversationId, offset: conversationId === state.conversationId ? state.offset : 0, atStart: conversationId === state.conversationId && state.atStart };
    }
    return null;
};

export { readConversationListScrollState, resolveConversationListScrollAnchor, writeConversationListScrollState };
export type { ConversationListScrollState };
