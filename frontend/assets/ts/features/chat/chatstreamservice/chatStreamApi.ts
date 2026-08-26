/* SoAI - Chat stream API endpoint contracts [frontend/assets/ts/features/chat/chatstreamservice/chatStreamApi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import type { ConversationStreamStatusResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { mapChatStreamStatusSnapshot, type ChatStreamStatusSnapshot } from '@features/chat/chatstreamservice/activeStreamStatus.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { normalizeMessageTimestamps } from '@features/chat/storage/chatStorageBackendMapping.ts';
import type { RequestOptions } from '@core/api/types/request.ts';

interface ChatStreamApiClient {
    webui: {
        chat: {
            assistantMessages: {
                streamState(conversationId: string, assistantTurnTimestamp: number, modelVariantIndex: number, options?: RequestOptions): Promise<WebuiConversationMessageResponse>;
            };
            streamStatus: {
                get(conversationId: string, options?: RequestOptions): Promise<ConversationStreamStatusResponse>;
            };
        };
    };
}

const fetchAssistantStreamState = async (apiClient: ChatStreamApiClient, conversationId: string, assistantTurnTimestamp: number, modelVariantIndex: number, signal?: AbortSignal): Promise<ChatMessage> => {
    const payload = await apiClient.webui.chat.assistantMessages.streamState(conversationId, assistantTurnTimestamp, modelVariantIndex, signal === undefined ? {} : { signal });
    const normalizedMessages = normalizeMessageTimestamps([payload]);
    const message = normalizedMessages[0];
    if (!message || message.role !== 'assistant') throw new Error('Assistant stream state response must contain one assistant message.');
    return message;
};

const fetchChatStreamStatusSnapshot = async (apiClient: ChatStreamApiClient, conversationId: string, signal?: AbortSignal): Promise<ChatStreamStatusSnapshot> => {
    const payload = await apiClient.webui.chat.streamStatus.get(conversationId, signal === undefined ? {} : { signal });
    const status = mapChatStreamStatusSnapshot(payload);
    if (status === null) {
        throw new Error('Chat stream status response is invalid.');
    }
    return status;
};

export { fetchAssistantStreamState, fetchChatStreamStatusSnapshot };
export type { ChatStreamApiClient };
