/* SoAI - Chat storage message window loading [frontend/assets/ts/features/chat/storage/messageWindowLoading.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { serializeConversationMessageWindowRequest } from '@core/api/contracts/webuiConversationRequestContracts.ts';
import { isAbortError, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import { parseMessageWindowResponse, parseRunningActivitySnapshot } from '@features/chat/storage/messageWindowPersistence.ts';
import { computeRunningActivitySnapshot } from '@features/chat/storage/runningActivitySnapshotComputation.ts';
import { applyWindowToConversation, countPersistedConversationMessages, resolveKnownPersistedMessageCount } from '@features/chat/storage/messageWindowState.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import type { Conversation, LoadConversationMessagesOptions, MessageWindowDirection } from '@features/chat/storage/storageModels.ts';

type ChatMessageWindowRuntime = Pick<ChatStorageManagerContract, 'api' | 'chatStreamService' | 'errorHandler' | 'isActive' | 'messageWindowRequests' | 'runWithBoundary' | 'state' | 'validateStoredMessageTimestamps'>;

const normalizeExpectedMessageCount = (value: number | undefined): number | null => {
    return typeof value === 'number' && Number.isFinite(value) && Number.isInteger(value) && value >= 0 ? value : null;
};

const isWindowResponseApplicable = (conversation: Conversation, expectedMessageCount: number | null, readTotalCount: number, readLastModifiedAtMs: number, force: boolean, allowAuthoritativeCountDecrease: boolean): boolean => {
    if (conversation.history !== undefined && readLastModifiedAtMs < conversation.history.version) {
        return false;
    }
    if (readLastModifiedAtMs < conversation.updatedAt) {
        return false;
    }
    if (force || allowAuthoritativeCountDecrease) {
        return true;
    }
    if (expectedMessageCount === null) {
        return true;
    }
    if (resolveKnownPersistedMessageCount(conversation) > expectedMessageCount) {
        return false;
    }
    return readTotalCount >= expectedMessageCount;
};

const loadRunningActivitySnapshot = async (manager: ChatMessageWindowRuntime, conversationId: string, signal?: AbortSignal): Promise<void> => {
    const controller = manager.messageWindowRequests.resolveRunningActivityController(conversationId);
    await controller.runLatest(async (request) => {
        const response = await runWithAbortSignalScope([request.signal, signal], async (combinedSignal) => {
            return await manager.runWithBoundary('chat:refreshRunningActivitySnapshot', async () => {
                return await manager.api.webui.chat.messages.runningActivity(conversationId, { signal: combinedSignal });
            });
        });
        throwIfAborted(signal);
        const currentConversationId = manager.state.getCurrentConversationId();
        if (!request.isCurrent() || !manager.isActive() || currentConversationId !== conversationId) {
            return null;
        }
        const parsed = parseRunningActivitySnapshot(response);
        if (parsed.convId !== conversationId) {
            throw new Error('Running activity snapshot conversation id does not match the request');
        }
        const conversation = manager.state.getConversations().get(conversationId);
        if (!conversation?.history) {
            return null;
        }
        conversation.history.runningActivity = computeRunningActivitySnapshot(parsed);
        return null;
    });
};

const refreshRunningActivitySnapshotForHydratedWindow = async (manager: ChatMessageWindowRuntime, conversationId: string, signal?: AbortSignal): Promise<void> => {
    try {
        await loadRunningActivitySnapshot(manager, conversationId, signal);
    } catch (error) {
        if (isAbortError(error)) {
            return;
        }
        manager.errorHandler?.warn?.('ChatStorageMessageWindowLoading', 'Running activity snapshot refresh failed', ensureError(error));
    }
};

const loadWindowResponse = async (manager: ChatMessageWindowRuntime, conversationId: string, options: LoadConversationMessagesOptions, direction: MessageWindowDirection): Promise<void> => {
    const controller = manager.messageWindowRequests.resolveWindowController(conversationId, direction);
    await controller.runLatest(async (request) => {
        const response = await runWithAbortSignalScope([request.signal, options.signal], async (signal) => {
            return await manager.runWithBoundary('chat:loadConversationMessages', async () => {
                return await manager.api.webui.chat.messages.window(conversationId, serializeConversationMessageWindowRequest(options), { signal });
            });
        });
        throwIfAborted(options.signal);
        const currentConversationId = manager.state.getCurrentConversationId();
        if (!request.isCurrent() || !manager.isActive() || currentConversationId !== conversationId) {
            return null;
        }
        const readResult = parseMessageWindowResponse(response);
        if (readResult.convId !== conversationId) {
            throw new Error('Message window response conversation id does not match the request');
        }
        const conversation = manager.state.getConversations().get(conversationId);
        if (!conversation) {
            return null;
        }
        const expectedMessageCount = normalizeExpectedMessageCount(options.expectedMessageCount);
        if (!isWindowResponseApplicable(conversation, expectedMessageCount, readResult.totalCount, readResult.lastModifiedAtMs, options.force === true, options.allowAuthoritativeCountDecrease === true)) {
            return null;
        }
        const replaceLocalAssistantTail = direction === 'tail' && options.allowAuthoritativeCountDecrease === true;
        applyWindowToConversation(manager, conversation, readResult, direction, options.mergeStreamingAssistants !== false, replaceLocalAssistantTail);
        manager.validateStoredMessageTimestamps();
        return null;
    });
};

async function loadConversationMessages(manager: ChatMessageWindowRuntime, conversationId: string, options: LoadConversationMessagesOptions = {}): Promise<void> {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    const conversation = manager.state.getConversations().get(normalizedConversationId);
    if (!conversation) {
        throw new Error(`Conversation not found: ${normalizedConversationId}`);
    }
    const direction = options.direction ?? 'tail';
    try {
        if (direction === 'tail' || direction === 'around') {
            manager.messageWindowRequests.invalidateConversation(normalizedConversationId);
            await loadWindowResponse(manager, normalizedConversationId, options, direction);
            await refreshRunningActivitySnapshotForHydratedWindow(manager, normalizedConversationId, options.signal);
            return;
        }
        await loadWindowResponse(manager, normalizedConversationId, options, direction);
    } catch (error) {
        if (isAbortError(error)) {
            return;
        }
        throw error;
    }
}

const refreshRunningActivitySnapshot = async (manager: ChatMessageWindowRuntime, conversationId: string): Promise<void> => {
    const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
    try {
        await loadRunningActivitySnapshot(manager, normalizedConversationId);
    } catch (error) {
        if (isAbortError(error)) {
            return;
        }
        throw error;
    }
};

export { countPersistedConversationMessages, loadConversationMessages, refreshRunningActivitySnapshot };
