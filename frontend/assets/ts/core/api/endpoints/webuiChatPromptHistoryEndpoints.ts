/* SoAI - WebUI chat prompt history endpoints [frontend/assets/ts/core/api/endpoints/webuiChatPromptHistoryEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeChatPromptHistoryResponse, type ChatPromptHistoryResponse } from '@core/api/contracts/chatPromptHistoryContract.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { RequestOptions } from '@core/api/types/request.ts';

interface WebuiChatPromptHistoryEndpoints {
    get(options?: RequestOptions): Promise<ChatPromptHistoryResponse>;
    clear(options?: RequestOptions): Promise<void>;
}

const createChatPromptHistoryEndpoints = (api: ApiClientContext): WebuiChatPromptHistoryEndpoints => ({
    get: async (options = {}): Promise<ChatPromptHistoryResponse> => decodeChatPromptHistoryResponse(await api.get('/api/v1/webui/prompt-history', options)),
    clear: async (options = {}): Promise<void> => {
        decodeNoContentResponse(await api.delete('/api/v1/webui/prompt-history', options), 'Chat prompt history clear response');
    }
});

export { createChatPromptHistoryEndpoints };
export type { WebuiChatPromptHistoryEndpoints };
