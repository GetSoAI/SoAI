/* SoAI - Chat feature conversation list refresh [frontend/assets/ts/features/chat/storage/conversationListRefresh.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isBoolean, isNumber } from '@core/typeGuards.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { parseBackendConversationList } from '@features/chat/storage/conversationPayloadParsing.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ChatStorageManagerContract } from '@features/chat/storage/managerContracts.ts';
import type { WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { resolveKnownPersistedMessageCount } from '@features/chat/storage/messageWindowState.ts';

type ChatConversationListRuntime = Pick<ChatStorageManagerContract, 'api' | 'clearConversationSelection' | 'conversationManager' | 'invalidateChatMarkup' | 'isActive' | 'refreshConversationListUI' | 'state'>;

const conversationListRefreshStateByManager = new WeakMap<ChatConversationListRuntime, { sequence: number }>();

const resolveConversationListRefreshState = (manager: ChatConversationListRuntime): { sequence: number } => {
    const existing = conversationListRefreshStateByManager.get(manager);
    if (existing) {
        return existing;
    }
    const state = { sequence: 0 };
    conversationListRefreshStateByManager.set(manager, state);
    return state;
};

const wasConversationModifiedAfterRefreshStart = (conversation: Conversation, refreshStartedAtMs: number): boolean => {
    if (!isNumber(refreshStartedAtMs) || !Number.isFinite(refreshStartedAtMs) || refreshStartedAtMs <= 0) {
        throw new Error('Conversation list refresh requires a positive refresh start timestamp');
    }
    const createdAt = conversation.createdAt;
    const updatedAt = conversation.updatedAt;
    if (isNumber(createdAt) && Number.isFinite(createdAt) && createdAt >= refreshStartedAtMs) {
        return true;
    }
    if (isNumber(updatedAt) && Number.isFinite(updatedAt) && updatedAt >= refreshStartedAtMs) {
        return true;
    }
    return false;
};

const copyOptionalBooleanField = (target: Conversation, source: Conversation, field: 'isAutomation' | 'isMessaging' | 'isArchived'): void => {
    const value = source[field];
    if (isBoolean(value)) {
        target[field] = value;
        return;
    }
    delete target[field];
};

const mergeExistingConversationRefreshState = (normalizedConversation: Conversation, existingConversation: Conversation, preserveSelectedWindow: boolean): void => {
    const incomingUpdatedAt = normalizedConversation.updatedAt;
    const invalidatesHydratedHistory = incomingUpdatedAt >= existingConversation.updatedAt && normalizedConversation.messageCount !== undefined && normalizedConversation.messageCount < resolveKnownPersistedMessageCount(existingConversation);
    if (incomingUpdatedAt < existingConversation.updatedAt) {
        normalizedConversation.title = existingConversation.title;
        normalizedConversation.color = existingConversation.color;
        normalizedConversation.isFavorite = existingConversation.isFavorite;
        normalizedConversation.modelSettings = existingConversation.modelSettings;
        normalizedConversation.messageCount = existingConversation.messageCount ?? existingConversation.messages.length;
        copyOptionalBooleanField(normalizedConversation, existingConversation, 'isAutomation');
        copyOptionalBooleanField(normalizedConversation, existingConversation, 'isMessaging');
        normalizedConversation.messagingPlatform = existingConversation.messagingPlatform ?? null;
        normalizedConversation.messagingAccountLabel = existingConversation.messagingAccountLabel ?? null;
        normalizedConversation.messagingAccountSnapshotId = existingConversation.messagingAccountSnapshotId ?? null;
        if (existingConversation.settingsAuthority) normalizedConversation.settingsAuthority = existingConversation.settingsAuthority;
        else delete normalizedConversation.settingsAuthority;
        copyOptionalBooleanField(normalizedConversation, existingConversation, 'isArchived');
    }
    normalizedConversation.updatedAt = Math.max(existingConversation.updatedAt, incomingUpdatedAt);
    normalizedConversation.messagesHydrated = preserveSelectedWindow && !invalidatesHydratedHistory && existingConversation.history !== undefined && existingConversation.messagesHydrated === true;
    if (preserveSelectedWindow && existingConversation.history && !invalidatesHydratedHistory) {
        normalizedConversation.history = existingConversation.history;
    } else {
        delete normalizedConversation.history;
    }
    if (preserveSelectedWindow && (existingConversation.history || invalidatesHydratedHistory) && isArray(existingConversation.messages)) {
        normalizedConversation.messages = existingConversation.messages;
    } else {
        normalizedConversation.messages = [];
    }
};

const applyConversationList = (manager: ChatConversationListRuntime, response: readonly WebuiConversationResponse[], refreshStartedAtMs: number): boolean => {
    const existingConversations = manager.state.getConversations();
    const currentConversationId = manager.state.getCurrentConversationId();
    const nextConversations = new Map<string, Conversation>();
    const parsedConversations = parseBackendConversationList(response);
    for (const normalizedConversation of parsedConversations.values()) {
        const existingConversation = existingConversations.get(normalizedConversation.id);
        if (existingConversation) {
            mergeExistingConversationRefreshState(normalizedConversation, existingConversation, normalizedConversation.id === currentConversationId);
        }
        nextConversations.set(normalizedConversation.id, normalizedConversation);
        manager.conversationManager.markConversationPersisted(normalizedConversation.id);
    }
    for (const [conversationId, conversation] of existingConversations.entries()) {
        if (nextConversations.has(conversationId)) {
            continue;
        }
        if (conversationId === currentConversationId && conversation.isArchived === true) {
            nextConversations.set(conversationId, conversation);
            continue;
        }
        const shouldPreserve = !manager.conversationManager.isConversationPersisted(conversationId) || wasConversationModifiedAfterRefreshStart(conversation, refreshStartedAtMs);
        if (shouldPreserve) {
            nextConversations.set(conversationId, conversation);
        }
    }
    manager.state.setConversations(nextConversations);
    if (!currentConversationId) {
        return false;
    }
    return !nextConversations.has(currentConversationId);
};

const refreshConversationList = async (manager: ChatConversationListRuntime): Promise<void> => {
    if (!manager.isActive()) {
        return;
    }
    const refreshStartedAtMs = serverEpochMs();
    const refreshState = resolveConversationListRefreshState(manager);
    const refreshSequence = refreshState.sequence + 1;
    refreshState.sequence = refreshSequence;
    const chatApi = manager.api.webui.chat;
    const response = await chatApi.list();
    if (!manager.isActive()) {
        return;
    }
    if (resolveConversationListRefreshState(manager).sequence !== refreshSequence) {
        return;
    }
    const shouldClearConversationSelection = applyConversationList(manager, response, refreshStartedAtMs);
    if (!manager.isActive()) {
        return;
    }
    if (shouldClearConversationSelection) {
        await manager.clearConversationSelection();
        return;
    }
    manager.invalidateChatMarkup('list');
    await manager.refreshConversationListUI();
};

export { refreshConversationList };
