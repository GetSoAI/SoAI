/* SoAI - Chat feature storage events [frontend/assets/ts/features/chat/storage/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_CONTRACTS } from '@core/realtime/eventcontracts/registry.ts';
import type { ConversationCreatedEvent, ConversationDeletedEvent, ConversationUpdatedEvent } from '@core/realtime/eventcontracts/conversationContracts.ts';
import { createWebSocketContractBinding, subscribeManagedWebSocketContracts } from '@core/realtime/websocketBatchSubscription.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { refreshConversationList } from '@features/chat/storage/conversationListRefresh.ts';
import { resolveMessageTitle } from '@features/chat/messageBuilding.ts';
import { parseBackendConversationUpdateEvent } from '@features/chat/storage/conversationPayloadParsing.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import { i18n } from '@core/i18n/index.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { handleMessageSaved } from '@features/chat/storage/messageSavedEvents.ts';

type ChatStorageEventsRuntime = Pick<ChatStorageManagerContract, 'api' | 'chatStreamService' | 'clearConversationSelection' | 'consumeMatchingLocalMessageWrite' | 'conversationManager' | 'errorHandler' | 'evictConversationMessages' | 'handleConversationDeleted' | 'handleConversationSettingsAuthorityChanged' | 'invalidateChatMarkup' | 'isActive' | 'loadConversationMessages' | 'refreshConversationListUI' | 'refreshConversationMetadataUI' | 'refreshConversationsUI' | 'showNotification' | 'state' | 'stopStreaming'>;

const reportEventRefreshFailure = (manager: ChatStorageEventsRuntime, message: string, error: Error): void => {
    if (!manager.isActive()) {
        return;
    }
    manager.errorHandler?.warn?.('ChatStorageManager', message, error);
    manager.showNotification(i18n.t('chat.errors.syncFailed'), 'error');
    void refreshConversationList(manager).catch((refreshError) => {
        if (!manager.isActive()) {
            return;
        }
        manager.errorHandler?.warn?.('ChatStorageManager', 'Failed to refresh conversations after a realtime sync error', ensureError(refreshError));
    });
};

const runConversationEventHandler = (manager: ChatStorageEventsRuntime, message: string, operation: () => Promise<void>): void => {
    void operation().catch((error) => reportEventRefreshFailure(manager, message, ensureError(error)));
};

const markConversationPersisted = (manager: ChatStorageEventsRuntime, conversationId: string): void => {
    manager.conversationManager.markConversationPersisted(conversationId);
};

const resolveConversationDefaultTitle = (conversation: Conversation): string | null => {
    for (const message of conversation.messages) {
        if (!isJsonObject(message) || message['role'] !== 'user') {
            continue;
        }
        const resolvedTitle = resolveMessageTitle(message);
        return resolvedTitle ? resolvedTitle : null;
    }
    return null;
};

const shouldIgnoreStaleTitlePatch = (conversation: Conversation, incomingTitle: string, incomingUpdatedAt: number): boolean => {
    if (incomingUpdatedAt >= conversation.updatedAt) {
        return false;
    }
    if (conversation.title === incomingTitle) {
        return false;
    }
    const defaultTitle = resolveConversationDefaultTitle(conversation);
    if (defaultTitle !== null && conversation.title === defaultTitle) {
        return false;
    }
    return true;
};

const shouldApplyStaleTitlePatch = (conversation: Conversation, incomingTitle: string, incomingUpdatedAt: number): boolean => {
    return incomingUpdatedAt < conversation.updatedAt && !shouldIgnoreStaleTitlePatch(conversation, incomingTitle, incomingUpdatedAt);
};

const applyConversationUpdatedEventPayload = (manager: ChatStorageEventsRuntime, event: ConversationUpdatedEvent): boolean => {
    const existingConversationId = event.convId;
    const currentConversation = manager.state.getConversations().get(existingConversationId);
    const parsed = parseBackendConversationUpdateEvent(event, currentConversation ? currentConversation.modelSettings : { model: null });
    if (!currentConversation) {
        return parsed.patch.settingsAuthorityChanged === true;
    }
    const conversationId = parsed.conversationId;
    const targetConversation = manager.state.getConversations().get(conversationId);
    if (!targetConversation) {
        return parsed.patch.settingsAuthorityChanged === true;
    }
    const updatedAt = parsed.patch.updatedAt;
    const isStalePatch = updatedAt < targetConversation.updatedAt;
    if (isStalePatch) {
        if (parsed.patch.title !== undefined && shouldApplyStaleTitlePatch(targetConversation, parsed.patch.title, updatedAt)) {
            targetConversation.title = parsed.patch.title;
            targetConversation.updatedAt = Math.max(targetConversation.updatedAt, updatedAt);
        }
        return parsed.patch.settingsAuthorityChanged === true;
    }
    if (parsed.patch.title !== undefined) {
        targetConversation.title = parsed.patch.title;
    }
    if (parsed.patch.isFavorite !== undefined) {
        targetConversation.isFavorite = parsed.patch.isFavorite;
    }
    if (parsed.patch.color !== undefined) {
        targetConversation.color = parsed.patch.color;
    }
    if (parsed.patch.modelSettings !== undefined) {
        targetConversation.modelSettings = parsed.patch.modelSettings;
    }
    if (parsed.patch.isArchived !== undefined) {
        targetConversation.isArchived = parsed.patch.isArchived;
    }
    if (parsed.patch.messageCount !== undefined) {
        targetConversation.messageCount = parsed.patch.messageCount;
    }
    targetConversation.updatedAt = Math.max(targetConversation.updatedAt, updatedAt);
    return parsed.patch.settingsAuthorityChanged === true;
};

const shouldRemoveArchivedConversationFromList = (manager: ChatStorageEventsRuntime, event: ConversationUpdatedEvent, conversationId: string, conversation: Conversation | undefined): boolean => {
    if (manager.state.getCurrentConversationId() === conversationId) {
        return false;
    }
    if (event.isArchived !== true) {
        return false;
    }
    return conversation?.isArchived === true;
};

const handleConversationCreated = async (manager: ChatStorageEventsRuntime, event: ConversationCreatedEvent): Promise<void> => {
    if (!manager.isActive()) {
        return;
    }
    const conversationId = event.convId;
    markConversationPersisted(manager, conversationId);
    await refreshConversationList(manager);
};

const handleConversationUpdated = async (manager: ChatStorageEventsRuntime, event: ConversationUpdatedEvent): Promise<void> => {
    if (!manager.isActive()) {
        return;
    }
    const conversationId = event.convId;
    const wasInMap = manager.state.getConversations().has(conversationId);
    markConversationPersisted(manager, conversationId);
    const settingsAuthorityChanged = applyConversationUpdatedEventPayload(manager, event);
    if (!manager.isActive()) {
        return;
    }
    if (settingsAuthorityChanged) {
        await refreshConversationList(manager);
        if (!manager.isActive()) {
            return;
        }
        manager.handleConversationSettingsAuthorityChanged(conversationId);
        return;
    }
    const updatedConversation = manager.state.getConversations().get(conversationId);
    if (shouldRemoveArchivedConversationFromList(manager, event, conversationId, updatedConversation)) {
        manager.state.getConversations().delete(conversationId);
        manager.invalidateChatMarkup('list');
        await manager.refreshConversationListUI();
        return;
    }
    if (!wasInMap && event.isArchived === false) {
        await refreshConversationList(manager);
        return;
    }
    await manager.refreshConversationMetadataUI();
};

const handleConversationDeleted = async (manager: ChatStorageEventsRuntime, event: ConversationDeletedEvent): Promise<void> => {
    if (!manager.isActive()) {
        return;
    }
    const conversationId = event.convId;
    const currentConversationId = manager.state.getCurrentConversationId();
    const shouldStopStreaming = currentConversationId === conversationId || manager.chatStreamService.isStreaming(conversationId);
    if (shouldStopStreaming) {
        manager.stopStreaming('Conversation deleted');
    }
    await manager.handleConversationDeleted(conversationId);
};

const subscribeToConversationEvents = (manager: ChatStorageEventsRuntime, resources: ResourceTracker): void => {
    try {
        resources.track(
            subscribeManagedWebSocketContracts({
                label: 'ChatStorageManager',
                events: [
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.conversation.created,
                        handler: (event) => runConversationEventHandler(manager, 'Failed to handle conversation created event', () => handleConversationCreated(manager, event))
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.conversation.updated,
                        handler: (event) => runConversationEventHandler(manager, 'Failed to handle conversation updated event', () => handleConversationUpdated(manager, event))
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.conversation.deleted,
                        handler: (event) => runConversationEventHandler(manager, 'Failed to handle conversation deleted event', () => handleConversationDeleted(manager, event))
                    }),
                    createWebSocketContractBinding({
                        contract: WEBSOCKET_EVENT_CONTRACTS.conversation.messageSaved,
                        handler: (event) => runConversationEventHandler(manager, 'Failed to handle message saved event', () => handleMessageSaved(manager, event))
                    })
                ]
            })
        );
    } catch (error) {
        resources.cleanup();
        throw error;
    }
};

export { subscribeToConversationEvents };
