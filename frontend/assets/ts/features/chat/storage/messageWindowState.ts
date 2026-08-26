/* SoAI - Chat storage message window state application [frontend/assets/ts/features/chat/storage/messageWindowState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMessageRole } from '@core/chat/messageRoles.ts';
import { isNonNegativeInteger, isNumber, isPlainObject, isString } from '@core/typeGuards.ts';
import { isChatMessage } from '@features/chat/message/chatMessageGuards.ts';
import { buildPersistedMessageCursorKey, comparePersistedMessageCursors, hasPersistedMessageId, resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import { mergeStreamingAssistantMessages } from '@features/chat/storage/assistantMessageMerging.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import type { MessageWindowResponse } from '@features/chat/storage/messageWindowPersistence.ts';
import { preservePendingLocalUserMessages } from '@features/chat/storage/pendingLocalMessagePreservation.ts';
import type { ChatStorageMessageRecord, Conversation, ConversationMessageRange, MessageCursor, MessageWindowDirection } from '@features/chat/storage/storageModels.ts';
import type { ConversationMessage } from '@features/chat/ChatTypes.ts';

const MAX_RETAINED_WINDOW_MESSAGES = 1000;

const isStorageMessageRecord = (value: ConversationMessage): value is ChatStorageMessageRecord => {
    if (!isPlainObject(value)) {
        return false;
    }
    return isString(value['role']) && isMessageRole(value['role']) && isNumber(value['timestamp']) && Number.isFinite(value['timestamp']) && Number.isInteger(value['timestamp']);
};

const collectStorageMessageRecords = (messages: readonly ConversationMessage[]): ChatStorageMessageRecord[] => {
    const records: ChatStorageMessageRecord[] = [];
    for (const message of messages) {
        if (isStorageMessageRecord(message)) {
            records.push(message);
        }
    }
    return records;
};

const countPersistedConversationMessages = (conversation: Conversation): number => {
    let count = 0;
    for (const message of conversation.messages) {
        if (!isPlainObject(message)) {
            continue;
        }
        if (!isChatMessage(message) || !hasPersistedMessageId(message)) {
            continue;
        }
        count += 1;
    }
    return count;
};

const resolveKnownPersistedMessageCount = (conversation: Conversation): number => {
    const historyCount = conversation.history?.totalCount;
    const summaryCount = conversation.messageCount;
    const persistedMessageCount = countPersistedConversationMessages(conversation);
    const validHistoryCount = isNonNegativeInteger(historyCount) ? historyCount : 0;
    const validSummaryCount = isNonNegativeInteger(summaryCount) ? summaryCount : 0;
    return Math.max(validHistoryCount, validSummaryCount, persistedMessageCount);
};

const mergeMessageLists = (left: readonly ChatStorageMessageRecord[], right: readonly ChatStorageMessageRecord[]): ChatStorageMessageRecord[] => {
    const byKey = new Map<string, ChatStorageMessageRecord>();
    let transientIndex = 0;
    for (const message of [...left, ...right]) {
        const cursor = resolvePersistedMessageCursor(message);
        const key = cursor === null ? `transient:${String(transientIndex)}` : buildPersistedMessageCursorKey(cursor);
        transientIndex += cursor === null ? 1 : 0;
        byKey.set(key, message);
    }
    return [...byKey.values()].sort((leftMessage, rightMessage) => {
        const leftCursor = resolvePersistedMessageCursor(leftMessage);
        const rightCursor = resolvePersistedMessageCursor(rightMessage);
        if (leftCursor === null || rightCursor === null) {
            return leftMessage.timestamp - rightMessage.timestamp;
        }
        return comparePersistedMessageCursors(leftCursor, rightCursor);
    });
};

const boundRenderMessages = (messages: ChatStorageMessageRecord[], direction: MessageWindowDirection): ChatStorageMessageRecord[] => {
    if (messages.length <= MAX_RETAINED_WINDOW_MESSAGES) {
        return messages;
    }
    if (direction === 'before') {
        return messages.slice(0, MAX_RETAINED_WINDOW_MESSAGES);
    }
    return messages.slice(messages.length - MAX_RETAINED_WINDOW_MESSAGES);
};

const buildRetainedRange = (messages: ChatStorageMessageRecord[]): ConversationMessageRange[] => {
    const cursors = messages.map(resolvePersistedMessageCursor).filter((cursor): cursor is MessageCursor => cursor !== null);
    const firstCursor = cursors[0] ?? null;
    const lastCursor = cursors[cursors.length - 1] ?? null;
    if (firstCursor === null || lastCursor === null) {
        return [];
    }
    return [
        {
            firstCursor,
            lastCursor,
            messages
        }
    ];
};

const resolveLoadedUniqueCount = (messages: readonly ChatStorageMessageRecord[]): number => {
    const keys = new Set<string>();
    for (const message of messages) {
        const cursor = resolvePersistedMessageCursor(message);
        if (cursor !== null) {
            keys.add(buildPersistedMessageCursorKey(cursor));
        }
    }
    return keys.size;
};

const resolveHasOlder = (conversation: Conversation, readResult: MessageWindowResponse, direction: MessageWindowDirection, preserveRetainedHistory: boolean): boolean => {
    if (preserveRetainedHistory && conversation.history !== undefined) {
        return conversation.history.hasOlder;
    }
    if (direction === 'after') {
        return conversation.history?.hasOlder ?? readResult.hasOlder;
    }
    return readResult.hasOlder;
};

const resolveHasNewer = (conversation: Conversation, readResult: MessageWindowResponse, direction: MessageWindowDirection): boolean => {
    if (direction === 'before') {
        return conversation.history?.hasNewer ?? readResult.hasNewer;
    }
    return readResult.hasNewer;
};

const firstCursorOf = (messages: readonly ChatStorageMessageRecord[]): MessageCursor | null => {
    for (const message of messages) {
        const cursor = resolvePersistedMessageCursor(message);
        if (cursor !== null) {
            return cursor;
        }
    }
    return null;
};

const lastCursorOf = (messages: readonly ChatStorageMessageRecord[]): MessageCursor | null => {
    for (let index = messages.length - 1; index >= 0; index -= 1) {
        const candidate = messages[index];
        if (candidate === undefined) {
            continue;
        }
        const cursor = resolvePersistedMessageCursor(candidate);
        if (cursor !== null) {
            return cursor;
        }
    }
    return null;
};

const droppedNewerMessages = (mergedWindow: readonly ChatStorageMessageRecord[], boundedWindow: readonly ChatStorageMessageRecord[]): boolean => {
    const mergedLast = lastCursorOf(mergedWindow);
    const boundedLast = lastCursorOf(boundedWindow);
    if (mergedLast === null || boundedLast === null) {
        return false;
    }
    return comparePersistedMessageCursors(boundedLast, mergedLast) < 0;
};

const droppedOlderMessages = (mergedWindow: readonly ChatStorageMessageRecord[], boundedWindow: readonly ChatStorageMessageRecord[]): boolean => {
    const mergedFirst = firstCursorOf(mergedWindow);
    const boundedFirst = firstCursorOf(boundedWindow);
    if (mergedFirst === null || boundedFirst === null) {
        return false;
    }
    return comparePersistedMessageCursors(boundedFirst, mergedFirst) > 0;
};

const shouldPreserveRetainedHistory = (conversation: Conversation, readResult: MessageWindowResponse, direction: MessageWindowDirection, replaceLocalAssistantTail: boolean): boolean => {
    if (direction !== 'tail' || conversation.history === undefined || replaceLocalAssistantTail) {
        return false;
    }
    return readResult.totalCount >= conversation.history.totalCount;
};

const resolveAuthoritativeWindowMessages = (currentMessages: readonly ChatStorageMessageRecord[], readResult: MessageWindowResponse, preserveRetainedHistory: boolean): ChatStorageMessageRecord[] => {
    const oldestCursor = readResult.oldestCursor;
    if (!preserveRetainedHistory || oldestCursor === null) {
        return readResult.messages;
    }
    const retainedOlderMessages = currentMessages.filter((message) => {
        const cursor = resolvePersistedMessageCursor(message);
        return cursor !== null && comparePersistedMessageCursors(cursor, oldestCursor) < 0;
    });
    return mergeMessageLists(retainedOlderMessages, readResult.messages);
};

const applyWindowToConversation = (manager: Pick<ChatStorageManagerContract, 'chatStreamService' | 'state'>, conversation: Conversation, readResult: MessageWindowResponse, direction: MessageWindowDirection, mergeStreamingAssistants: boolean, replaceLocalAssistantTail: boolean): void => {
    const currentMessages = conversation.messages;
    const currentStorageMessages = collectStorageMessageRecords(currentMessages);
    const activeAssistantMessage = mergeStreamingAssistants ? manager.chatStreamService.getActiveAssistantMessage(conversation.id) : null;
    const preserveRetainedHistory = shouldPreserveRetainedHistory(conversation, readResult, direction, replaceLocalAssistantTail);
    const authoritativeWindow = resolveAuthoritativeWindowMessages(currentStorageMessages, readResult, preserveRetainedHistory);
    const mergedWindow = direction === 'tail' || direction === 'around' ? authoritativeWindow : mergeMessageLists(currentStorageMessages, readResult.messages);
    const boundedWindow = boundRenderMessages(mergedWindow, direction);
    const boundingDroppedNewer = droppedNewerMessages(mergedWindow, boundedWindow);
    const boundingDroppedOlder = droppedOlderMessages(mergedWindow, boundedWindow);
    const assistantMergeSource = replaceLocalAssistantTail ? boundedWindow : currentMessages;
    const mergedMessages = mergeStreamingAssistants ? mergeStreamingAssistantMessages(assistantMergeSource, boundedWindow, activeAssistantMessage) : boundedWindow;
    conversation.messages = preservePendingLocalUserMessages(currentMessages, mergedMessages);
    const historyMessages = collectStorageMessageRecords(conversation.messages);
    const retainedRanges = buildRetainedRange(historyMessages);
    const retainedRange = retainedRanges[0] ?? null;
    const hasOlder = boundingDroppedOlder || resolveHasOlder(conversation, readResult, direction, preserveRetainedHistory);
    const hasNewer = boundingDroppedNewer || resolveHasNewer(conversation, readResult, direction);
    conversation.updatedAt = Math.max(conversation.updatedAt, readResult.lastModifiedAtMs);
    conversation.messageCount = readResult.totalCount;
    conversation.history = {
        conversationId: conversation.id,
        version: readResult.lastModifiedAtMs,
        totalCount: readResult.totalCount,
        loadedUniqueCount: Math.max(readResult.loadedCountHint, resolveLoadedUniqueCount(historyMessages)),
        retainedRanges,
        oldestCursor: retainedRange?.firstCursor ?? readResult.oldestCursor,
        newestCursor: retainedRange?.lastCursor ?? readResult.newestCursor,
        hasOlder,
        hasNewer,
        blockingStatus: 'ready',
        backgroundStatus: hasOlder || hasNewer ? 'idle' : 'complete',
        backgroundDirection: null,
        runningActivity: conversation.history?.runningActivity ?? null
    };
    conversation.messagesHydrated = true;
};

export { applyWindowToConversation, countPersistedConversationMessages, resolveKnownPersistedMessageCount };
