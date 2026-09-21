/* SoAI - Chat feature message persistence [frontend/assets/ts/features/chat/storage/messagePersistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationMessageSyncCursorResponse, ConversationMessageWriteResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { normalizeMessageTimestamps } from '@features/chat/storage/chatStorageBackendMapping.ts';
import { CONVERSATION_INPUT_MESSAGE_ID_FIELD } from '@features/chat/message/messageDomIds.ts';
import { hasPersistedMessageId } from '@features/chat/message/persistedMessageIdentity.ts';
import { normalizeChatMessageForBackendStorage } from '@features/chat/storage/messageNormalization.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import type { ChatStorageMessageRecord } from '@features/chat/storage/storageModels.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';

type MessageWriteResult = {
    lastModifiedAtMs: number;
    messageCount: number;
    canonicalMessages: ChatStorageMessageRecord[];
    localWrite: boolean;
};

type MessagePersistenceInput = {
    apiClient: ChatPageApi;
    conversationId: string;
    expectedLastModifiedAtMs: number;
    messages: readonly ChatMessage[];
};

type TargetedMessageMutationInput = {
    apiClient: ChatPageApi;
    conversationId: string;
    expectedLastModifiedAtMs: number;
    createdAtMs: number;
    messageId: number;
};

type TargetedMessageResubmitInput = TargetedMessageMutationInput & {
    message: ChatMessage;
};

type MessageSyncCursor = {
    latestTimestamp: number | null;
    lastModifiedAtMs: number;
    messageCount: number;
};

const requireExpectedConversationVersion = (value: number): number => {
    if (!isNumber(value) || !isEpochMsNumber(value)) {
        throw new Error('Message persistence requires the current conversation updatedAt version');
    }
    return value;
};

const parseMessageWriteResult = (value: ConversationMessageWriteResponse): MessageWriteResult => {
    const lastModifiedAtMs = value.lastModifiedAtMs;
    const messageCount = value.messageCount;
    const messages = value.messages;
    if (!isNumber(lastModifiedAtMs) || !isEpochMsNumber(lastModifiedAtMs)) {
        throw new Error('Message write response lastModifiedAtMs must be an epoch-millisecond integer');
    }
    if (!isNumber(messageCount) || !Number.isFinite(messageCount) || !Number.isInteger(messageCount) || messageCount < 0) {
        throw new Error('Message write response messageCount must be a non-negative integer');
    }
    const normalizedMessages = normalizeMessageTimestamps(messages);
    const canonicalMessages: ChatStorageMessageRecord[] = [];
    for (let index = 0; index < normalizedMessages.length; index += 1) {
        const message = normalizedMessages[index];
        if (!message) {
            throw new Error(`Message write response message[${String(index)}] is missing`);
        }
        canonicalMessages.push(message);
    }
    if (canonicalMessages.length > messageCount) {
        throw new Error('Message write response messages cannot exceed messageCount');
    }
    return { lastModifiedAtMs, messageCount, canonicalMessages, localWrite: true };
};

const normalizeMessageTimestamp = (value: JsonValue | undefined, messageIndex: number): number => {
    if (!isNumber(value) || !Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        throw new Error(`Chat message[${String(messageIndex)}] timestamp must be a non-negative integer`);
    }
    return value;
};

const normalizeConversationMessagesForBackend = (messages: readonly ChatMessage[]): JsonObject[] => {
    const normalizedMessages: JsonObject[] = [];
    let previousTimestamp: number | null = null;
    for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        const message = messages[messageIndex];
        if (!message) {
            throw new Error(`Chat message[${String(messageIndex)}] is missing`);
        }
        const conversationInputId = message[CONVERSATION_INPUT_MESSAGE_ID_FIELD];
        if (typeof conversationInputId === 'string' && conversationInputId.trim() && !hasPersistedMessageId(message)) {
            continue;
        }
        const normalized = normalizeChatMessageForBackendStorage(message);
        if (normalized === null) {
            throw new Error(`Chat message[${String(messageIndex)}] cannot be normalized for backend persistence`);
        }
        const timestamp = normalizeMessageTimestamp(normalized['timestamp'], messageIndex);
        if (previousTimestamp !== null && timestamp <= previousTimestamp) {
            throw new Error(`Chat message order is not strictly chronological at index ${String(messageIndex)}`);
        }
        previousTimestamp = timestamp;
        normalizedMessages.push(normalized);
    }
    return normalizedMessages;
};

const resolveAppendTailMessages = (messages: readonly ChatMessage[], latestTimestamp: number): JsonObject[] => {
    const candidates: ChatMessage[] = [];
    for (let messageIndex = 0; messageIndex < messages.length; messageIndex += 1) {
        const message = messages[messageIndex];
        if (!message) {
            throw new Error(`Chat message[${String(messageIndex)}] is missing`);
        }
        const timestamp = normalizeMessageTimestamp(message.timestamp, messageIndex);
        if (timestamp > latestTimestamp && message.role === 'user') {
            candidates.push(message);
        }
    }
    return normalizeConversationMessagesForBackend(candidates);
};

const resolveLatestTimestamp = (value: ConversationMessageSyncCursorResponse): number | null => {
    const timestampValue = value.timestamp;
    if (timestampValue === null || timestampValue === undefined) {
        return null;
    }
    if (!isNumber(timestampValue) || !isEpochMsNumber(timestampValue)) {
        throw new Error('Latest timestamp response timestamp must be an epoch-millisecond integer or null');
    }
    return timestampValue;
};

const parseMessageSyncCursor = (value: ConversationMessageSyncCursorResponse): MessageSyncCursor => {
    const lastModifiedAtMs = value.lastModifiedAtMs;
    const messageCount = value.messageCount;
    if (!isNumber(lastModifiedAtMs) || !isEpochMsNumber(lastModifiedAtMs)) {
        throw new Error('Message sync cursor response lastModifiedAtMs must be an epoch-millisecond integer');
    }
    if (!isNumber(messageCount) || !Number.isFinite(messageCount) || !Number.isInteger(messageCount) || messageCount < 0) {
        throw new Error('Message sync cursor response messageCount must be a non-negative integer');
    }
    return {
        latestTimestamp: resolveLatestTimestamp(value),
        lastModifiedAtMs,
        messageCount
    };
};

const persistConversationMessagesToBackendReplace = async (input: MessagePersistenceInput): Promise<MessageWriteResult> => {
    const conversationId = requireConversationId(input.conversationId, 'Conversation');
    const messagesApi = input.apiClient.webui.chat.messages;
    const expectedLastModifiedAtMs = requireExpectedConversationVersion(input.expectedLastModifiedAtMs);
    const normalizedMessages = normalizeConversationMessagesForBackend(input.messages);
    return parseMessageWriteResult(await messagesApi.replace(conversationId, normalizedMessages, expectedLastModifiedAtMs));
};

const persistConversationMessagesToBackendAppendTail = async (input: MessagePersistenceInput): Promise<MessageWriteResult> => {
    const conversationId = requireConversationId(input.conversationId, 'Conversation');
    const messagesApi = input.apiClient.webui.chat.messages;
    requireExpectedConversationVersion(input.expectedLastModifiedAtMs);
    const syncCursor = parseMessageSyncCursor(await messagesApi.syncCursor(conversationId));
    const resolvedLatest = syncCursor.latestTimestamp === null ? 0 : syncCursor.latestTimestamp;
    const tail = resolveAppendTailMessages(input.messages, resolvedLatest);
    if (tail.length === 0) {
        return {
            lastModifiedAtMs: syncCursor.lastModifiedAtMs,
            messageCount: syncCursor.messageCount,
            canonicalMessages: [],
            localWrite: false
        };
    }
    return parseMessageWriteResult(await messagesApi.append(conversationId, tail, syncCursor.lastModifiedAtMs));
};

const persistUserMessageResubmitToBackend = async (input: TargetedMessageResubmitInput): Promise<MessageWriteResult> => {
    const conversationId = requireConversationId(input.conversationId, 'Conversation');
    const expectedLastModifiedAtMs = requireExpectedConversationVersion(input.expectedLastModifiedAtMs);
    const normalizedMessages = normalizeConversationMessagesForBackend([input.message]);
    if (normalizedMessages.length !== 1) {
        throw new Error('Message resubmit requires exactly one normalized message');
    }
    const normalizedMessage = normalizedMessages[0];
    if (normalizedMessage === undefined) {
        throw new Error('Message resubmit requires a normalized message');
    }
    return parseMessageWriteResult(
        await input.apiClient.webui.chat.messages.resubmit(conversationId, {
            expectedLastModifiedAtMs,
            createdAtMs: input.createdAtMs,
            messageId: input.messageId,
            message: normalizedMessage
        })
    );
};

const persistMessageDeleteToBackend = async (input: TargetedMessageMutationInput): Promise<MessageWriteResult> => {
    const conversationId = requireConversationId(input.conversationId, 'Conversation');
    const expectedLastModifiedAtMs = requireExpectedConversationVersion(input.expectedLastModifiedAtMs);
    return parseMessageWriteResult(
        await input.apiClient.webui.chat.messages.deleteMessage(conversationId, {
            expectedLastModifiedAtMs,
            createdAtMs: input.createdAtMs,
            messageId: input.messageId
        })
    );
};

export { persistConversationMessagesToBackendAppendTail, persistConversationMessagesToBackendReplace, persistMessageDeleteToBackend, persistUserMessageResubmitToBackend };
export type { MessageWriteResult };
