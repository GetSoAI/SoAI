/* SoAI - Authoritative materialized conversation-input message application [frontend/assets/ts/features/chat/storage/materializedMessageEvent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { WebuiConversationMessageResponse } from '@core/api/contracts/webuiMessageContracts.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { CONVERSATION_INPUT_MESSAGE_ID_FIELD } from '@features/chat/message/messageDomIds.ts';
import { hasPersistedMessageId } from '@features/chat/message/persistedMessageIdentity.ts';
import { insertMessageByTimestamp } from '@features/chat/message/messageTimestampOrdering.ts';
import { normalizeMessageTimestamps } from '@features/chat/storage/chatStorageBackendMapping.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

const applyMaterializedMessageEvent = (conversation: Conversation, materializedMessage: WebuiConversationMessageResponse | null): boolean => {
    if (materializedMessage === null) {
        return false;
    }
    const message = normalizeMessageTimestamps([materializedMessage])[0];
    if (!message || message.role !== 'user' || !hasPersistedMessageId(message)) {
        throw new Error('Message saved event materialization must contain a persisted user message.');
    }
    const conversationInputId = message[CONVERSATION_INPUT_MESSAGE_ID_FIELD];
    if (typeof conversationInputId !== 'string' || !conversationInputId.trim()) {
        throw new Error('Message saved event materialization must contain a conversation input id.');
    }
    let matchedIndex: number | null = null;
    for (let index = 0; index < conversation.messages.length; index += 1) {
        const candidate = conversation.messages[index];
        if (!isJsonObject(candidate)) {
            continue;
        }
        const matchesPersistedId = candidate['id'] === message.id;
        const matchesConversationInput = candidate[CONVERSATION_INPUT_MESSAGE_ID_FIELD] === conversationInputId;
        if (!matchesPersistedId && !matchesConversationInput) {
            continue;
        }
        if (matchedIndex !== null && matchedIndex !== index) {
            throw new Error('Message saved event materialization conflicts with existing message identities.');
        }
        matchedIndex = index;
    }
    if (matchedIndex !== null) {
        conversation.messages.splice(matchedIndex, 1);
    }
    insertMessageByTimestamp(conversation.messages, message, message.timestamp);
    return true;
};

export { applyMaterializedMessageEvent };
