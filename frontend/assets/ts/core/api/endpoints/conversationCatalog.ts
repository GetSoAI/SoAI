/* SoAI - Bounded conversation catalog retrieval [frontend/assets/ts/core/api/endpoints/conversationCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeConversationCatalogPageResponse, type ConversationCatalogCursor, type WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { buildQueryRequestOptions } from '@core/api/requestOptions.ts';
import { CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS } from '@core/api/conversationHistoryTimeout.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';
import { createAbortError } from '@core/errors/abort.ts';

const CONVERSATION_CATALOG_PAGE_SIZE = 64;

const loadConversationCatalog = (api: Pick<ApiClientContext, 'get'>): Promise<WebuiConversationResponse[]> =>
    withAbortableTimeout(
        async (signal) => {
            const conversations: WebuiConversationResponse[] = [];
            const identities = new Set<string>();
            let cursor: ConversationCatalogCursor | null = null;
            do {
                const query = { limit: CONVERSATION_CATALOG_PAGE_SIZE, ...(cursor === null ? {} : { 'before_created_at_ms': cursor.createdAtMs, 'before_id': cursor.id }) };
                const page = decodeConversationCatalogPageResponse(await api.get('/api/v1/webui/conversations', buildQueryRequestOptions(query, signal)));
                if (signal.aborted) throw createAbortError('Conversation catalog retrieval aborted.');
                if (page.conversations.length > CONVERSATION_CATALOG_PAGE_SIZE) throw new Error('Conversation catalog page exceeded its requested limit.');
                for (const conversation of page.conversations) {
                    if (identities.has(conversation.id)) throw new Error('Conversation catalog repeated an identity.');
                    identities.add(conversation.id);
                    conversations.push(conversation);
                }
                const nextCursor = page.nextCursor;
                if (nextCursor !== null) {
                    const last = page.conversations.at(-1);
                    if (!last || last.id !== nextCursor.id || last.createdAtMs !== nextCursor.createdAtMs) throw new Error('Conversation catalog cursor does not identify its last record.');
                    if (cursor !== null && (nextCursor.createdAtMs > cursor.createdAtMs || (nextCursor.createdAtMs === cursor.createdAtMs && nextCursor.id >= cursor.id))) throw new Error('Conversation catalog cursor did not advance.');
                }
                cursor = nextCursor;
            } while (cursor !== null);
            return conversations.sort((first, second) => second.lastModifiedAtMs - first.lastModifiedAtMs || second.id.localeCompare(first.id, 'en'));
        },
        { timeoutMs: CONVERSATION_HISTORY_REQUEST_TIMEOUT_MS, timeoutMessage: 'Conversation catalog retrieval timed out.' }
    );

export { loadConversationCatalog };
