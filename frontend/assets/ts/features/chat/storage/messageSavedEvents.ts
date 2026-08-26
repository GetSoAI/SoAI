/* SoAI - Frontend chat storage message-saved realtime handling [frontend/assets/ts/features/chat/storage/messageSavedEvents.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNonRetryableApiRequestError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { MessageSavedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';
import { refreshConversationList } from '@features/chat/storage/conversationListRefresh.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import { applyMaterializedMessageEvent } from '@features/chat/storage/materializedMessageEvent.ts';
import { resolveKnownPersistedMessageCount } from '@features/chat/storage/messageWindowState.ts';
import type { Conversation, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';

type ChatMessageSavedRuntime = Pick<ChatStorageManagerContract, 'api' | 'chatStreamService' | 'clearConversationSelection' | 'consumeMatchingLocalMessageWrite' | 'conversationManager' | 'evictConversationMessages' | 'invalidateChatMarkup' | 'isActive' | 'loadConversationMessages' | 'refreshConversationListUI' | 'refreshConversationsUI' | 'state'>;

const hasCurrentConversationAdvancedPastMessageCount = (manager: ChatMessageSavedRuntime, conversationId: string, messageCount: number): boolean => {
    const currentConversationId = manager.state.getCurrentConversationId();
    if (currentConversationId !== conversationId) {
        return false;
    }
    const currentConversation = manager.state.getConversations().get(conversationId);
    if (!currentConversation || currentConversation.history === undefined || currentConversation.messagesHydrated !== true) {
        return false;
    }
    return resolveKnownPersistedMessageCount(currentConversation) > messageCount;
};

const isCurrentConversationScrolledAwayFromTail = (manager: ChatMessageSavedRuntime, conversationId: string): boolean => {
    if (manager.state.getCurrentConversationId() !== conversationId) {
        return false;
    }
    const currentConversation = manager.state.getConversations().get(conversationId);
    if (!currentConversation || currentConversation.history === undefined || currentConversation.messagesHydrated !== true) {
        return false;
    }
    return currentConversation.history.hasNewer === true;
};

const ensureConversationListEntry = async (manager: ChatMessageSavedRuntime, conversationId: string): Promise<boolean> => {
    if (manager.state.getConversations().has(conversationId)) {
        return true;
    }
    await refreshConversationList(manager);
    if (!manager.isActive()) {
        return false;
    }
    return manager.state.getConversations().has(conversationId);
};

const refreshListOnly = async (manager: ChatMessageSavedRuntime): Promise<void> => {
    manager.invalidateChatMarkup('list');
    await manager.refreshConversationListUI();
};

const isSelectedConversation = (manager: ChatMessageSavedRuntime, conversationId: string): boolean => {
    return manager.state.getCurrentConversationId() === conversationId;
};

const settleOffscreenMessageSaved = async (manager: ChatMessageSavedRuntime, conversationId: string): Promise<void> => {
    manager.evictConversationMessages(conversationId);
    await refreshListOnly(manager);
};

const isAuthoritativeMessageCountDecrease = (conversation: Conversation | undefined, messageCount: number, lastModifiedAtMs: number): boolean => {
    if (!conversation || lastModifiedAtMs < conversation.updatedAt) {
        return false;
    }
    return messageCount < resolveKnownPersistedMessageCount(conversation);
};

const handleMessageSaved = async (manager: ChatMessageSavedRuntime, event: MessageSavedEvent): Promise<void> => {
    if (!manager.isActive()) {
        return;
    }
    const conversationId = event.convId;
    const messageCount = event.messageCount;
    const lastModifiedAtMs = event.lastModifiedAtMs;
    manager.conversationManager.markConversationPersisted(conversationId);
    const conversation = manager.state.getConversations().get(conversationId);
    const wasSelectedConversation = isSelectedConversation(manager, conversationId);
    const authoritativeCountDecrease = isAuthoritativeMessageCountDecrease(conversation, messageCount, lastModifiedAtMs);
    const materializedMessageApplied = conversation && wasSelectedConversation ? applyMaterializedMessageEvent(conversation, event.message) : false;
    if (conversation) {
        if (lastModifiedAtMs >= conversation.updatedAt) {
            conversation.messageCount = messageCount;
        }
        conversation.updatedAt = Math.max(conversation.updatedAt, lastModifiedAtMs);
    }
    if (manager.consumeMatchingLocalMessageWrite(conversationId, messageCount, lastModifiedAtMs)) {
        return;
    }
    if (!(await ensureConversationListEntry(manager, conversationId))) {
        return;
    }
    if (!isSelectedConversation(manager, conversationId)) {
        await settleOffscreenMessageSaved(manager, conversationId);
        return;
    }
    const reconciliation = await manager.chatStreamService.reconcileMessageSaved(conversationId);
    if (!manager.isActive()) {
        return;
    }
    if (!isSelectedConversation(manager, conversationId)) {
        await settleOffscreenMessageSaved(manager, conversationId);
        return;
    }
    const selectedConversation = manager.state.getConversations().get(conversationId);
    const canUseMaterializedMessage = wasSelectedConversation && selectedConversation === conversation;
    if (canUseMaterializedMessage && !authoritativeCountDecrease && !reconciliation.canonicalLoad) {
        if (materializedMessageApplied) {
            await manager.refreshConversationsUI();
        } else {
            await refreshListOnly(manager);
        }
        return;
    }
    if (!authoritativeCountDecrease && hasCurrentConversationAdvancedPastMessageCount(manager, conversationId, messageCount)) {
        await refreshListOnly(manager);
        return;
    }
    if (!authoritativeCountDecrease && isCurrentConversationScrolledAwayFromTail(manager, conversationId)) {
        await refreshListOnly(manager);
        return;
    }
    try {
        const loadOptions: LoadConversationMessagesOptions = {
            expectedMessageCount: messageCount,
            mergeStreamingAssistants: authoritativeCountDecrease
        };
        if (authoritativeCountDecrease) {
            loadOptions.allowAuthoritativeCountDecrease = true;
        }
        await manager.loadConversationMessages(conversationId, loadOptions);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isNonRetryableApiRequestError(runtimeError)) {
            throw runtimeError;
        }
        errorHandler.warn('ChatStorageMessageSavedEvents', 'Message reload rejected; refreshing conversation list only', runtimeError);
        await refreshListOnly(manager);
        return;
    }
    if (!manager.isActive()) {
        return;
    }
    if (!isSelectedConversation(manager, conversationId)) {
        await settleOffscreenMessageSaved(manager, conversationId);
        return;
    }
    await manager.refreshConversationsUI();
};

export { handleMessageSaved };
