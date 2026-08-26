/* SoAI - Chat feature storage actions [frontend/assets/ts/features/chat/storage/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { buildPersistedMessageCursorKey, resolvePersistedMessageCursor } from '@features/chat/message/persistedMessageIdentity.ts';
import { parseBackendConversationList, requirePersistableConversation } from '@features/chat/storage/conversationPayloadParsing.ts';
import { countPersistedConversationMessages, loadConversationMessages } from '@features/chat/storage/messageWindowLoading.ts';
import { persistConversationMessagesToBackendAppendTail, persistConversationMessagesToBackendReplace, persistMessageDeleteToBackend, persistMessageTruncateToBackend, persistUserMessageResubmitToBackend, type MessageWriteResult } from '@features/chat/storage/messagePersistence.ts';
import type { ChatStorageMessageRecord, Conversation } from '@features/chat/storage/storageModels.ts';
import type { ConversationContract, ConversationMessage } from '@features/chat/ChatTypes.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';

type ChatStorageActionsRuntime = Pick<ChatStorageManagerContract, 'api' | 'chatStreamService' | 'conversationManager' | 'errorHandler' | 'evictConversationMessages' | 'isActive' | 'markLocalMessageWrite' | 'messageWindowRequests' | 'runSerializedConversationSync' | 'runWithBoundary' | 'saveChatState' | 'showNotification' | 'state' | 'validateStoredMessageTimestamps'>;

const resolveCanonicalCursorKey = (message: ConversationMessage): string | null => {
    const cursor = resolvePersistedMessageCursor(message);
    if (cursor === null) {
        return null;
    }
    return buildPersistedMessageCursorKey(cursor);
};

const resolveFallbackMessageKey = (message: ConversationMessage): string | null => {
    const timestamp = message['timestamp'];
    const role = message['role'];
    if (!isNumber(timestamp) || !Number.isSafeInteger(timestamp) || timestamp < 0 || !isString(role) || !role.trim()) {
        return null;
    }
    return `${String(timestamp)}:${role.trim().toLowerCase()}`;
};

const incrementCount = (counts: Map<string, number>, key: string): void => {
    counts.set(key, (counts.get(key) ?? 0) + 1);
};

const buildFallbackCounts = (messages: readonly ConversationMessage[]): Map<string, number> => {
    const counts = new Map<string, number>();
    for (const message of messages) {
        if (resolveCanonicalCursorKey(message) !== null) {
            continue;
        }
        const fallbackKey = resolveFallbackMessageKey(message);
        if (fallbackKey !== null) {
            incrementCount(counts, fallbackKey);
        }
    }
    return counts;
};

const refreshConversationAfterAmbiguousWrite = async (manager: ChatStorageActionsRuntime, conversationId: string): Promise<void> => {
    try {
        await loadConversationMessages(manager, conversationId, { force: true });
    } catch (error) {
        if (!manager.isActive()) {
            return;
        }
        manager.errorHandler?.warn?.('ChatStorageActions', 'Post-write canonical message reload failed', ensureError(error));
        manager.showNotification(i18n.t('chat.errors.syncFailed'), 'error');
    }
};

const applyMessageWriteResult = async (manager: ChatStorageActionsRuntime, conversation: Conversation, result: MessageWriteResult): Promise<void> => {
    conversation.updatedAt = Math.max(conversation.updatedAt, result.lastModifiedAtMs);
    conversation.messageCount = result.messageCount;
    let requiresCanonicalReload = false;
    const isSelectedConversation = manager.state.getCurrentConversationId() === conversation.id;
    if (!isSelectedConversation) {
        manager.evictConversationMessages(conversation.id);
    } else if (result.canonicalMessages.length === result.messageCount) {
        conversation.messages = result.canonicalMessages;
        conversation.messagesHydrated = true;
    } else if (result.canonicalMessages.length > 0) {
        const canonicalByCursor = new Map<string, ChatStorageMessageRecord>();
        const canonicalByFallback = new Map<string, ChatStorageMessageRecord>();
        const canonicalFallbackCounts = new Map<string, number>();
        for (const message of result.canonicalMessages) {
            const cursorKey = resolveCanonicalCursorKey(message);
            if (cursorKey !== null) {
                canonicalByCursor.set(cursorKey, message);
            }
            const fallbackKey = resolveFallbackMessageKey(message);
            if (fallbackKey !== null) {
                canonicalByFallback.set(fallbackKey, message);
                incrementCount(canonicalFallbackCounts, fallbackKey);
            }
        }
        const localFallbackCounts = buildFallbackCounts(conversation.messages);
        let appliedCanonicalCount = 0;
        conversation.messages = conversation.messages.map((message) => {
            const cursorKey = resolveCanonicalCursorKey(message);
            if (cursorKey !== null) {
                const canonical = canonicalByCursor.get(cursorKey) ?? null;
                if (canonical !== null) {
                    appliedCanonicalCount += 1;
                    return canonical;
                }
                return message;
            }
            const fallbackKey = resolveFallbackMessageKey(message);
            if (fallbackKey === null || localFallbackCounts.get(fallbackKey) !== 1 || canonicalFallbackCounts.get(fallbackKey) !== 1) {
                return message;
            }
            const canonical = canonicalByFallback.get(fallbackKey) ?? null;
            if (canonical === null) {
                return message;
            }
            appliedCanonicalCount += 1;
            return canonical;
        });
        requiresCanonicalReload = appliedCanonicalCount < result.canonicalMessages.length;
    }
    if (result.localWrite) {
        manager.markLocalMessageWrite(conversation.id, result.messageCount, result.lastModifiedAtMs);
    }
    if (conversation.history) {
        conversation.history.version = result.lastModifiedAtMs;
        conversation.history.totalCount = result.messageCount;
    }
    manager.saveChatState(true);
    if (requiresCanonicalReload && isSelectedConversation) {
        await refreshConversationAfterAmbiguousWrite(manager, conversation.id);
    }
};

async function loadConversationCatalogFromBackend(manager: ChatStorageActionsRuntime): Promise<void> {
    const chatApi = manager.api.webui.chat;
    const backendConversations = await manager.runWithBoundary('chat:loadConversations', async () => {
        const response = await chatApi.list();
        return parseBackendConversationList(response);
    });
    if (!manager.isActive()) {
        return;
    }
    manager.state.setConversations(backendConversations);
    manager.conversationManager.markAllConversationsPersisted();
}

async function syncConversation(manager: ChatStorageActionsRuntime, conversation: Conversation, messageSyncMode: 'replace' | 'append_tail'): Promise<void> {
    await manager.runSerializedConversationSync(conversation.id, async () => {
        await manager.runWithBoundary('chat:syncConversationMessages', async () => {
            if (messageSyncMode === 'append_tail') {
                const writeResult = await persistConversationMessagesToBackendAppendTail({
                    apiClient: manager.api,
                    conversationId: conversation.id,
                    expectedLastModifiedAtMs: conversation.updatedAt,
                    messages: conversation.messages
                });
                await applyMessageWriteResult(manager, conversation, writeResult);
                return;
            }
            if (conversation.history) {
                throw new Error('Full message replacement is not allowed for server-windowed conversations.');
            }
            const writeResult = await persistConversationMessagesToBackendReplace({
                apiClient: manager.api,
                conversationId: conversation.id,
                expectedLastModifiedAtMs: conversation.updatedAt,
                messages: conversation.messages
            });
            await applyMessageWriteResult(manager, conversation, writeResult);
        });
    });
}

async function saveAndSync(manager: ChatStorageActionsRuntime, conversation: ConversationContract | null, force = false, sync = true, messageSyncMode: 'replace' | 'append_tail' = 'replace'): Promise<void> {
    manager.saveChatState(force);
    if (!sync) return;
    const persistableConversation = requirePersistableConversation(conversation);
    await manager.conversationManager.ensureConversationPersisted(persistableConversation);
    await syncConversation(manager, persistableConversation, messageSyncMode);
}

async function resubmitUserMessage(manager: ChatStorageActionsRuntime, conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }): Promise<void> {
    const persistableConversation = requirePersistableConversation(conversation);
    const writeResult = await manager.runWithBoundary('chat:resubmitUserMessage', () =>
        persistUserMessageResubmitToBackend({
            apiClient: manager.api,
            conversationId: persistableConversation.id,
            expectedLastModifiedAtMs: persistableConversation.updatedAt,
            createdAtMs: inputArguments.createdAtMs,
            messageId: inputArguments.messageId,
            message: inputArguments.message
        })
    );
    await applyMessageWriteResult(manager, persistableConversation, writeResult);
}

async function truncateMessagesFromCursor(manager: ChatStorageActionsRuntime, conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }): Promise<void> {
    const persistableConversation = requirePersistableConversation(conversation);
    const writeResult = await manager.runWithBoundary('chat:truncateMessagesFromCursor', () =>
        persistMessageTruncateToBackend({
            apiClient: manager.api,
            conversationId: persistableConversation.id,
            expectedLastModifiedAtMs: persistableConversation.updatedAt,
            createdAtMs: inputArguments.createdAtMs,
            messageId: inputArguments.messageId
        })
    );
    await applyMessageWriteResult(manager, persistableConversation, writeResult);
}

async function deleteMessageByCursor(manager: ChatStorageActionsRuntime, conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }): Promise<void> {
    const persistableConversation = requirePersistableConversation(conversation);
    const writeResult = await manager.runWithBoundary('chat:deleteMessageByCursor', () =>
        persistMessageDeleteToBackend({
            apiClient: manager.api,
            conversationId: persistableConversation.id,
            expectedLastModifiedAtMs: persistableConversation.updatedAt,
            createdAtMs: inputArguments.createdAtMs,
            messageId: inputArguments.messageId
        })
    );
    await applyMessageWriteResult(manager, persistableConversation, writeResult);
}

export { countPersistedConversationMessages, deleteMessageByCursor, loadConversationCatalogFromBackend, loadConversationMessages, resubmitUserMessage, saveAndSync, syncConversation, truncateMessagesFromCursor };
