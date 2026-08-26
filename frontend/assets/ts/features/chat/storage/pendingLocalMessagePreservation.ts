/* SoAI - Chat feature pending local message preservation [frontend/assets/ts/features/chat/storage/pendingLocalMessagePreservation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNumber } from '@core/typeGuards.ts';
import type { ConversationMessage } from '@features/chat/ChatTypes.ts';
import { CONVERSATION_INPUT_MESSAGE_ID_FIELD } from '@features/chat/message/messageDomIds.ts';
import { hasPersistedMessageId } from '@features/chat/message/persistedMessageIdentity.ts';
import { insertMessageByTimestamp } from '@features/chat/message/messageTimestampOrdering.ts';

type PendingLocalUserMessage = { message: ConversationMessage; timestamp: number };

const resolveConversationInputMessageId = (message: ConversationMessage): string | null => {
    const inputId = message[CONVERSATION_INPUT_MESSAGE_ID_FIELD];
    if (typeof inputId !== 'string') {
        return null;
    }
    const normalized = inputId.trim();
    return normalized || null;
};

const resolveMessageTimestamp = (message: ConversationMessage): number | null => {
    const timestamp = message['timestamp'];
    if (!isNumber(timestamp) || !Number.isFinite(timestamp) || !Number.isInteger(timestamp)) {
        return null;
    }
    return timestamp;
};

const collectPendingLocalUserMessages = (currentMessages: ConversationMessage[]): PendingLocalUserMessage[] => {
    const pending: PendingLocalUserMessage[] = [];
    const conversationInputIds = new Set<string>();
    for (const message of currentMessages) {
        if (message['role'] !== 'user') {
            continue;
        }
        if (hasPersistedMessageId(message)) {
            continue;
        }
        const timestamp = resolveMessageTimestamp(message);
        if (timestamp === null) {
            continue;
        }
        const normalizedConversationInputId = resolveConversationInputMessageId(message);
        if (normalizedConversationInputId !== null) {
            if (conversationInputIds.has(normalizedConversationInputId)) {
                continue;
            }
            conversationInputIds.add(normalizedConversationInputId);
        }
        pending.push({ message, timestamp });
    }
    return pending;
};

const mergedHasMaterializedConversationInput = (mergedMessages: ConversationMessage[], inputId: string): boolean => {
    for (const message of mergedMessages) {
        if (message['role'] !== 'user' || !hasPersistedMessageId(message)) {
            continue;
        }
        if (resolveConversationInputMessageId(message) === inputId) {
            return true;
        }
    }
    return false;
};

const resolveSnapshotLatestTimestamp = (mergedMessages: ConversationMessage[]): number | null => {
    let latest: number | null = null;
    for (const message of mergedMessages) {
        const timestamp = resolveMessageTimestamp(message);
        if (timestamp === null) {
            continue;
        }
        if (latest === null || timestamp > latest) {
            latest = timestamp;
        }
    }
    return latest;
};

const preservePendingLocalUserMessages = (currentMessages: ConversationMessage[], mergedMessages: ConversationMessage[]): ConversationMessage[] => {
    const pending = collectPendingLocalUserMessages(currentMessages);
    if (pending.length === 0) {
        return mergedMessages;
    }
    const snapshotLatestTimestamp = resolveSnapshotLatestTimestamp(mergedMessages);
    let result: ConversationMessage[] | null = null;
    for (const candidate of pending) {
        const conversationInputId = resolveConversationInputMessageId(candidate.message);
        if (conversationInputId !== null) {
            if (mergedHasMaterializedConversationInput(mergedMessages, conversationInputId)) {
                continue;
            }
            if (result === null) {
                result = [...mergedMessages];
            }
            insertMessageByTimestamp(result, candidate.message, candidate.timestamp);
            continue;
        }
        if (snapshotLatestTimestamp !== null && candidate.timestamp <= snapshotLatestTimestamp) {
            continue;
        }
        if (result === null) {
            result = [...mergedMessages];
        }
        insertMessageByTimestamp(result, candidate.message, candidate.timestamp);
    }
    return result ?? mergedMessages;
};

export { preservePendingLocalUserMessages };
