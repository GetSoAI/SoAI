/* SoAI - Chat stream activity resource decoding [frontend/assets/ts/core/chat/chatStreamActivitySnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

type ChatStreamActivityResource = JsonObject & {
    activeConversationIds: string[];
};

const decodeConversationIds = (conversationIdsValue: JsonValue | undefined): string[] => {
    if (!Array.isArray(conversationIdsValue)) {
        throw new Error('Invalid Chat stream activity conversation ids');
    }
    const activeConversationIds: string[] = [];
    for (const conversationIdValue of conversationIdsValue) {
        if (!isString(conversationIdValue) || !conversationIdValue.trim()) {
            throw new Error('Invalid Chat stream activity conversation id');
        }
        const conversationId = conversationIdValue.trim();
        if (activeConversationIds.includes(conversationId)) {
            throw new Error('Duplicate Chat stream activity conversation id');
        }
        activeConversationIds.push(conversationId);
    }
    return activeConversationIds;
};

const decodeChatStreamActivityResource = (value: JsonValue | null): ChatStreamActivityResource => {
    if (!isJsonObject(value)) {
        throw new Error('Invalid Chat stream activity resource');
    }
    return { activeConversationIds: decodeConversationIds(value['active_conversation_ids']) };
};

const parseChatStreamActivityResource = (value: JsonValue | null): ChatStreamActivityResource => {
    if (!isJsonObject(value)) {
        throw new Error('Invalid normalized Chat stream activity resource');
    }
    return { activeConversationIds: decodeConversationIds(value['activeConversationIds']) };
};

export { decodeChatStreamActivityResource, parseChatStreamActivityResource };
export type { ChatStreamActivityResource };
