/* SoAI - Complete operation-local conversation snapshot loading [frontend/assets/ts/features/chat/storage/conversationSnapshotLoading.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeConversationMessageWindowRequest } from '@core/api/contracts/webuiConversationRequestContracts.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { cloneStructured } from '@core/primitives/clone.ts';
import { comparePersistedMessageCursors } from '@features/chat/message/persistedMessageIdentity.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import { parseMessageWindowResponse, type MessageWindowResponse } from '@features/chat/storage/messageWindowPersistence.ts';
import type { ChatStorageMessageRecord, Conversation, MessageCursor } from '@features/chat/storage/storageModels.ts';

const CONVERSATION_SNAPSHOT_PAGE_LIMIT = 1000;

type ConversationSnapshotRuntime = Pick<ChatStorageManagerContract, 'api' | 'runWithBoundary' | 'state'>;

const readSnapshotWindow = async (manager: ConversationSnapshotRuntime, conversationId: string, cursor: MessageCursor | null, signal: AbortSignal | undefined): Promise<MessageWindowResponse> => {
    throwIfAborted(signal);
    const request = cursor === null ? serializeConversationMessageWindowRequest({ direction: 'tail', limit: CONVERSATION_SNAPSHOT_PAGE_LIMIT }) : serializeConversationMessageWindowRequest({ direction: 'before', cursor, limit: CONVERSATION_SNAPSHOT_PAGE_LIMIT });
    const response = await manager.runWithBoundary('chat:readConversationSnapshot', async () => {
        return await manager.api.webui.chat.messages.window(conversationId, request, signal === undefined ? {} : { signal });
    });
    throwIfAborted(signal);
    const readResult = parseMessageWindowResponse(response);
    if (readResult.convId !== conversationId) {
        throw new Error('Message window response conversation id does not match the request');
    }
    return readResult;
};

const requireStableSnapshotWindow = (initialWindow: MessageWindowResponse, nextWindow: MessageWindowResponse, currentOldestCursor: MessageCursor): void => {
    if (nextWindow.totalCount !== initialWindow.totalCount || nextWindow.lastModifiedAtMs !== initialWindow.lastModifiedAtMs) {
        throw new Error('Conversation changed while its complete snapshot was loading');
    }
    if (nextWindow.newestCursor === null || comparePersistedMessageCursors(nextWindow.newestCursor, currentOldestCursor) >= 0) {
        throw new Error('Conversation snapshot pagination did not advance toward older messages');
    }
};

const requireCompleteSnapshotTail = (initialWindow: MessageWindowResponse): void => {
    if (initialWindow.hasNewer) {
        throw new Error('Conversation snapshot tail unexpectedly has newer messages');
    }
};

const readCompleteConversationSnapshot = async (manager: ConversationSnapshotRuntime, conversationId: string, signal?: AbortSignal): Promise<Conversation> => {
    const conversation = manager.state.getConversations().get(conversationId);
    if (!conversation) throw new Error(`Conversation not found: ${conversationId}`);
    const initialWindow = await readSnapshotWindow(manager, conversationId, null, signal);
    requireCompleteSnapshotTail(initialWindow);
    const messagePagesNewestFirst: ChatStorageMessageRecord[][] = [[...initialWindow.messages]];
    let loadedMessageCount = initialWindow.messages.length;
    let oldestCursor = initialWindow.oldestCursor;
    let hasOlder = initialWindow.hasOlder;
    while (hasOlder) {
        if (oldestCursor === null) {
            throw new Error('Conversation snapshot has older messages without an oldest cursor');
        }
        const nextWindow = await readSnapshotWindow(manager, conversationId, oldestCursor, signal);
        requireStableSnapshotWindow(initialWindow, nextWindow, oldestCursor);
        messagePagesNewestFirst.push([...nextWindow.messages]);
        loadedMessageCount += nextWindow.messages.length;
        oldestCursor = nextWindow.oldestCursor;
        hasOlder = nextWindow.hasOlder;
        if (loadedMessageCount > initialWindow.totalCount) {
            throw new Error('Conversation snapshot contains more messages than its authoritative count');
        }
    }
    if (loadedMessageCount !== initialWindow.totalCount) {
        throw new Error('Conversation snapshot message count does not match its authoritative count');
    }
    const snapshot = cloneStructured(conversation);
    snapshot.messages = messagePagesNewestFirst.reverse().flat();
    snapshot.messagesHydrated = true;
    snapshot.messageCount = initialWindow.totalCount;
    snapshot.updatedAt = Math.max(snapshot.updatedAt, initialWindow.lastModifiedAtMs);
    delete snapshot.history;
    return snapshot;
};

export { readCompleteConversationSnapshot };
