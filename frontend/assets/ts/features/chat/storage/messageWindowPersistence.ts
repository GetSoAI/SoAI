/* SoAI - Chat message window response parsing [frontend/assets/ts/features/chat/storage/messageWindowPersistence.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationMessageWindowResponse, ConversationRunningActivityResponse, MessageCursorResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { comparePersistedMessageCursors, resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import { normalizeMessageTimestamps } from '@features/chat/storage/chatStorageBackendMapping.ts';
import type { ChatStorageMessageRecord, MessageCursor } from '@features/chat/storage/storageModels.ts';

type MessageWindowResponse = {
    convId: string;
    messages: ChatStorageMessageRecord[];
    returnedCount: number;
    loadedCountHint: number;
    totalCount: number;
    oldestCursor: MessageCursor | null;
    newestCursor: MessageCursor | null;
    hasOlder: boolean;
    hasNewer: boolean;
    lastModifiedAtMs: number;
};

type ParsedRunningActivitySnapshot = {
    convId: string;
    runningMessages: ChatStorageMessageRecord[];
    lastModifiedAtMs: number;
};

const requireNonNegativeInteger = (value: number, label: string): number => {
    if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0) {
        throw new Error(`${label} must be a non-negative integer`);
    }
    return value;
};

const requireEpochMs = (value: number, label: string): number => {
    if (!isEpochMsNumber(value)) {
        throw new Error(`${label} must be an epoch-millisecond integer`);
    }
    return value;
};

const parseMessageCursor = (value: MessageCursorResponse | null, label: string): MessageCursor | null => {
    if (value === null) {
        return null;
    }
    return {
        createdAtMs: requireEpochMs(value.createdAtMs, `${label}.createdAtMs`),
        id: requireNonNegativeInteger(value.id, `${label}.id`)
    };
};

const requireWindowMessageCursor = (message: ChatStorageMessageRecord, index: number): MessageCursor => {
    const cursor = resolvePersistedMessageCursor(message);
    if (cursor === null) {
        throw new Error(`Message window message[${String(index)}] must include a persisted cursor`);
    }
    return cursor;
};

const requireMatchingCursor = (actual: MessageCursor, expected: MessageCursor | null, label: string): void => {
    if (expected === null || comparePersistedMessageCursors(actual, expected) !== 0) {
        throw new Error(`${label} does not match the message window boundary`);
    }
};

const validateMessageWindowResponse = (response: MessageWindowResponse): MessageWindowResponse => {
    const messages = response.messages;
    if (response.returnedCount !== messages.length) {
        throw new Error('Message window returnedCount does not match messages length');
    }
    if (response.loadedCountHint < response.returnedCount) {
        throw new Error('Message window loadedCountHint cannot be lower than returnedCount');
    }
    if (response.totalCount < response.returnedCount) {
        throw new Error('Message window totalCount cannot be lower than returnedCount');
    }
    if (messages.length === 0) {
        if (response.oldestCursor !== null || response.newestCursor !== null || response.hasOlder || response.hasNewer) {
            throw new Error('Empty message window cannot include boundary cursors or paging flags');
        }
        return response;
    }
    const firstMessage = messages[0];
    if (firstMessage === undefined) {
        throw new Error('Message window first message is missing');
    }
    const firstCursor = requireWindowMessageCursor(firstMessage, 0);
    let previousCursor = firstCursor;
    for (let index = 1; index < messages.length; index += 1) {
        const message = messages[index];
        if (message === undefined) {
            throw new Error(`Message window message[${String(index)}] is missing`);
        }
        const cursor = requireWindowMessageCursor(message, index);
        if (comparePersistedMessageCursors(previousCursor, cursor) >= 0) {
            throw new Error('Message window messages must be strictly ordered by cursor');
        }
        previousCursor = cursor;
    }
    requireMatchingCursor(firstCursor, response.oldestCursor, 'Message window oldestCursor');
    requireMatchingCursor(previousCursor, response.newestCursor, 'Message window newestCursor');
    return response;
};

const parseMessageWindowResponse = (value: ConversationMessageWindowResponse): MessageWindowResponse => {
    const convId = value.convId;
    if (typeof convId !== 'string' || !convId.trim()) {
        throw new Error('Message window convId must be a non-empty string');
    }
    return validateMessageWindowResponse({
        convId: convId.trim(),
        messages: normalizeMessageTimestamps(value.messages),
        returnedCount: requireNonNegativeInteger(value.returnedCount, 'Message window returnedCount'),
        loadedCountHint: requireNonNegativeInteger(value.loadedCountHint, 'Message window loadedCountHint'),
        totalCount: requireNonNegativeInteger(value.totalCount, 'Message window totalCount'),
        oldestCursor: parseMessageCursor(value.oldestCursor, 'Message window oldestCursor'),
        newestCursor: parseMessageCursor(value.newestCursor, 'Message window newestCursor'),
        hasOlder: value.hasOlder,
        hasNewer: value.hasNewer,
        lastModifiedAtMs: requireEpochMs(value.lastModifiedAtMs, 'Message window lastModifiedAtMs')
    });
};

const parseRunningActivitySnapshot = (value: ConversationRunningActivityResponse): ParsedRunningActivitySnapshot => {
    const convId = value.convId;
    if (typeof convId !== 'string' || !convId.trim()) {
        throw new Error('Running activity snapshot convId must be a non-empty string');
    }
    return {
        convId: convId.trim(),
        runningMessages: normalizeMessageTimestamps(value.runningMessages),
        lastModifiedAtMs: requireEpochMs(value.lastModifiedAtMs, 'Running activity lastModifiedAtMs')
    };
};

export { parseMessageWindowResponse, parseRunningActivitySnapshot };
export type { MessageWindowResponse, ParsedRunningActivitySnapshot };
