/* SoAI - Shared frontend API endpoint layer WebUI chat draft endpoints [frontend/assets/ts/core/api/endpoints/webuiChatDraftEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeConversationDraftResponse, serializeConversationDraftSaveRequest, type ConversationDraftResponse, type ConversationDraftSaveRequest } from '@core/api/contracts/chatQueueDraftContracts.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import type { WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';

interface WebuiChatDraftEndpoints {
    get(id: string, options?: RequestOptions): Promise<ConversationDraftResponse>;
    save(id: string, payload: ConversationDraftSaveRequest, options?: RequestOptions): Promise<ConversationDraftResponse>;
    delete(id: string, options?: RequestOptions): Promise<ConversationDraftResponse>;
}

const createDraftEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiChatDraftEndpoints => ({
    get: async (id, options = {}): Promise<ConversationDraftResponse> => decodeConversationDraftResponse(await api.get(paths.draft(id), options)),
    save: async (id, payload, options = {}): Promise<ConversationDraftResponse> => decodeConversationDraftResponse(await api.put(paths.draft(id), serializeConversationDraftSaveRequest(payload), options)),
    delete: async (id, options = {}): Promise<ConversationDraftResponse> => decodeConversationDraftResponse(await api.delete(paths.draft(id), options))
});

export { createDraftEndpoints };
export type { WebuiChatDraftEndpoints };
