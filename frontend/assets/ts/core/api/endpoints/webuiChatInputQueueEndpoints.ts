/* SoAI - WebUI chat input queue API endpoint factory [frontend/assets/ts/core/api/endpoints/webuiChatInputQueueEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeConversationInputCreated, decodeConversationInputList, serializeConversationInputEnqueueRequest, type ConversationInputAdmission, type ConversationInputEnqueueRequest, type ConversationInputListResponse } from '@core/api/contracts/chatQueueDraftContracts.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { WebuiConversationPaths } from '@core/api/endpoints/webuiConversationPaths.ts';

interface WebuiInputQueueEndpoints {
    list(id: string): Promise<ConversationInputListResponse>;
    enqueue(id: string, payload: ConversationInputEnqueueRequest): Promise<ConversationInputAdmission>;
    cancel(id: string, inputId: string): Promise<void>;
}

const createInputQueueEndpoints = (api: ApiClientContext, paths: WebuiConversationPaths): WebuiInputQueueEndpoints => {
    return {
        list: async (id): Promise<ConversationInputListResponse> => decodeConversationInputList(await api.get(paths.inputQueue(id))),
        enqueue: async (id, payload): Promise<ConversationInputAdmission> => decodeConversationInputCreated(await api.post(paths.inputQueue(id), serializeConversationInputEnqueueRequest(payload))),
        cancel: async (id, inputId): Promise<void> => {
            decodeNoContentResponse(await api.delete(paths.inputQueuePrompt(id, inputId)), 'Conversation input cancellation response');
        }
    };
};

export { createInputQueueEndpoints };
export type { WebuiInputQueueEndpoints };
