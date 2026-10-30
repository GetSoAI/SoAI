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

type ConversationSnapshotReader = Pick<ChatStorageManagerContract, 'api' | 'runWithBoundary'>;
type ConversationSnapshotRuntime = ConversationSnapshotReader & Pick<ChatStorageManagerContract, 'state'>;

interface ConversationSnapshotVisitOptions {
    pageLimit?: number;
    signal?: AbortSignal;
    verifyFreshness?: boolean;
    visitPage: (messages: readonly ChatStorageMessageRecord[], metadata: ConversationSnapshotMetadata) => Promise<boolean>;
}

interface ConversationSnapshotMetadata {
    totalCount: number;
    revision: number;
    visitedCount: number;
}

interface ConversationSnapshotVisitResult extends ConversationSnapshotMetadata {
    status: 'complete' | 'stopped';
}

class ConversationSnapshotChangedError extends Error {
    constructor() {
        super('Conversation changed while its complete snapshot was loading');
        this.name = 'ConversationSnapshotChangedError';
    }
}

const readSnapshotWindow = async (manager: ConversationSnapshotReader, conversationId: string, cursor: MessageCursor | null, pageLimit: number, signal: AbortSignal | undefined): Promise<MessageWindowResponse> => {
    throwIfAborted(signal);
    const request = cursor === null ? serializeConversationMessageWindowRequest({ direction: 'tail', limit: pageLimit }) : serializeConversationMessageWindowRequest({ direction: 'before', cursor, limit: pageLimit });
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

const requireStableSnapshotWindow = (initialWindow: MessageWindowResponse, nextWindow: MessageWindowResponse, currentOldestCursor: MessageCursor | null): void => {
    if (nextWindow.totalCount !== initialWindow.totalCount || nextWindow.lastModifiedAtMs !== initialWindow.lastModifiedAtMs) {
        throw new ConversationSnapshotChangedError();
    }
    if (currentOldestCursor !== null && (nextWindow.newestCursor === null || comparePersistedMessageCursors(nextWindow.newestCursor, currentOldestCursor) >= 0)) {
        throw new Error('Conversation snapshot pagination did not advance toward older messages');
    }
};

const requireCompleteSnapshotTail = (initialWindow: MessageWindowResponse): void => {
    if (initialWindow.hasNewer) {
        throw new Error('Conversation snapshot tail unexpectedly has newer messages');
    }
};

const visitConversationSnapshot = async (manager: ConversationSnapshotReader, conversationId: string, options: ConversationSnapshotVisitOptions): Promise<ConversationSnapshotVisitResult> => {
    const { signal, visitPage } = options;
    const pageLimit = options.pageLimit ?? CONVERSATION_SNAPSHOT_PAGE_LIMIT;
    if (!Number.isSafeInteger(pageLimit) || pageLimit < 1 || pageLimit > CONVERSATION_SNAPSHOT_PAGE_LIMIT) throw new Error('Conversation snapshot page limit must be between 1 and 1000');
    const initialWindow = await readSnapshotWindow(manager, conversationId, null, pageLimit, signal);
    requireCompleteSnapshotTail(initialWindow);
    let currentWindow = initialWindow;
    let visitedCount = 0;
    let status: ConversationSnapshotVisitResult['status'] = 'complete';
    while (true) {
        visitedCount += currentWindow.messages.length;
        if (visitedCount > initialWindow.totalCount) {
            throw new Error('Conversation snapshot contains more messages than its authoritative count');
        }
        const shouldContinue = await visitPage(currentWindow.messages, { totalCount: initialWindow.totalCount, revision: initialWindow.lastModifiedAtMs, visitedCount });
        throwIfAborted(signal);
        if (!shouldContinue) {
            status = 'stopped';
            break;
        }
        if (!currentWindow.hasOlder) break;
        const oldestCursor = currentWindow.oldestCursor;
        if (oldestCursor === null) {
            throw new Error('Conversation snapshot has older messages without an oldest cursor');
        }
        const nextWindow = await readSnapshotWindow(manager, conversationId, oldestCursor, pageLimit, signal);
        requireStableSnapshotWindow(initialWindow, nextWindow, oldestCursor);
        currentWindow = nextWindow;
    }
    if (status === 'complete' && visitedCount !== initialWindow.totalCount) {
        throw new Error('Conversation snapshot message count does not match its authoritative count');
    }
    if (options.verifyFreshness === true) {
        const finalWindow = await readSnapshotWindow(manager, conversationId, null, pageLimit, signal);
        requireCompleteSnapshotTail(finalWindow);
        requireStableSnapshotWindow(initialWindow, finalWindow, null);
    }
    return { status, totalCount: initialWindow.totalCount, revision: initialWindow.lastModifiedAtMs, visitedCount };
};

const readCompleteConversationSnapshot = async (manager: ConversationSnapshotRuntime, conversationId: string, signal?: AbortSignal): Promise<Conversation> => {
    const conversation = manager.state.getConversations().get(conversationId);
    if (!conversation) throw new Error(`Conversation not found: ${conversationId}`);
    const messagePagesNewestFirst: ChatStorageMessageRecord[][] = [];
    const result = await visitConversationSnapshot(manager, conversationId, {
        ...(signal === undefined ? {} : { signal }),
        visitPage: async (messages) => {
            messagePagesNewestFirst.push([...messages]);
            return true;
        }
    });
    const snapshot = cloneStructured(conversation);
    snapshot.messages = messagePagesNewestFirst.reverse().flat();
    snapshot.messagesHydrated = true;
    snapshot.messageCount = result.totalCount;
    snapshot.updatedAt = Math.max(snapshot.updatedAt, result.revision);
    delete snapshot.history;
    return snapshot;
};

export { ConversationSnapshotChangedError, readCompleteConversationSnapshot, visitConversationSnapshot };
export type { ConversationSnapshotMetadata, ConversationSnapshotReader, ConversationSnapshotVisitOptions, ConversationSnapshotVisitResult };
