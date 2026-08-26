/* SoAI - Archived conversations modal pagination [frontend/assets/ts/pages/chat/controllers/modals/archivedconversations/pagination/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseArchivedConversationSearchResponse, parseArchivedConversationsPage } from '@features/chat/public.ts';
import type { ArchivedConversationsModalHost, ArchivedConversationsModalState } from '@pages/chat/controllers/modals/archivedconversations/types.ts';

const ARCHIVED_CONVERSATIONS_PAGE_SIZE = 50;

const resetArchivedConversationState = (state: ArchivedConversationsModalState, query: string): void => {
    state.conversations = [];
    state.totalCount = 0;
    state.nextCursor = null;
    state.query = query;
    state.loading = false;
    state.searchMode = Boolean(query);
    state.requestVersion += 1;
    state.selectedIds.clear();
    state.selectionActive = false;
    state.renamingId = null;
    state.renameDraft = '';
};

const loadArchivedConversationsPage = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, signal: AbortSignal): Promise<void> => {
    if (state.loading || state.searchMode || (state.conversations.length > 0 && state.nextCursor === null)) {
        return;
    }
    const requestVersion = state.requestVersion + 1;
    state.requestVersion = requestVersion;
    state.loading = true;
    try {
        const cursor = state.nextCursor;
        const response = await host.api.webui.chat.listArchived(
            {
                limit: ARCHIVED_CONVERSATIONS_PAGE_SIZE,
                beforeLastModifiedAtMs: cursor?.lastModifiedAtMs,
                beforeId: cursor?.id
            },
            { signal }
        );
        if (signal.aborted || state.requestVersion !== requestVersion || state.searchMode) {
            return;
        }
        const page = parseArchivedConversationsPage(response);
        state.conversations = [...state.conversations, ...page.conversations];
        state.totalCount = page.totalCount;
        state.nextCursor = page.nextCursor;
    } finally {
        if (state.requestVersion === requestVersion) {
            state.loading = false;
        }
    }
};

const searchArchivedConversations = async (host: ArchivedConversationsModalHost, state: ArchivedConversationsModalState, signal: AbortSignal): Promise<void> => {
    if (!state.query) {
        return;
    }
    const query = state.query;
    const requestVersion = state.requestVersion + 1;
    state.requestVersion = requestVersion;
    state.loading = true;
    try {
        const response = await host.api.webui.chat.searchArchived(
            {
                q: query,
                limit: 200
            },
            { signal }
        );
        if (signal.aborted || state.requestVersion !== requestVersion || state.query !== query || !state.searchMode) {
            return;
        }
        state.conversations = parseArchivedConversationSearchResponse(response);
        state.totalCount = state.conversations.length;
        state.nextCursor = null;
    } finally {
        if (state.requestVersion === requestVersion) {
            state.loading = false;
        }
    }
};

export { loadArchivedConversationsPage, resetArchivedConversationState, searchArchivedConversations };
