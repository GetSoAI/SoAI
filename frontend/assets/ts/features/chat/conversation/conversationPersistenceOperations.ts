/* SoAI - Chat feature conversation persistence operations [frontend/assets/ts/features/chat/conversation/conversationPersistenceOperations.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import { applyConversationMetadataSnapshot, applyConversationSettingsSnapshot, buildConversationCreatePayload, parseConversationRecordForId, parseCreatedConversationRecord, type ConversationPersistenceSnapshot } from '@features/chat/conversation/conversationPersistenceSnapshots.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { WebuiConversationResponse } from '@core/api/contracts/webuiConversationContracts.ts';
import { serializeConversationModelSettings } from '@core/chat/executionSettingsMapping.ts';

const rollbackCreatedConversation = async (chatApi: ChatPageApi['webui']['chat'], conversationId: string, error: Error, context: string): Promise<never> => {
    try {
        await chatApi.delete(conversationId);
    } catch (cleanupError) {
        const creationError = ensureError(error);
        const cleanupRuntimeError = ensureError(cleanupError);
        throw new Error(`${creationError.message}; ${context} ${conversationId}: ${cleanupRuntimeError.message}`);
    }
    throw ensureError(error);
};

const parseCreatedConversationWithCleanup = async (chatApi: ChatPageApi['webui']['chat'], created: WebuiConversationResponse, conversationId: string, title: string): Promise<Conversation> => {
    try {
        return parseCreatedConversationRecord(created, conversationId, title);
    } catch (error) {
        const runtimeError = ensureError(error);
        return rollbackCreatedConversation(chatApi, conversationId, runtimeError, 'failed to delete malformed created conversation');
    }
};

const syncPersistedConversationSnapshot = async (chatApi: ChatPageApi['webui']['chat'], snapshot: ConversationPersistenceSnapshot, target: Conversation): Promise<void> => {
    const conversationId = snapshot.id;
    if (!compareParameterValues(serializeConversationModelSettings(target.modelSettings), serializeConversationModelSettings(snapshot.modelSettings))) {
        const settingsUpdated = await chatApi.updateSettings(conversationId, serializeConversationModelSettings(snapshot.modelSettings));
        applyConversationSettingsSnapshot(target, parseConversationRecordForId(settingsUpdated, conversationId, 'Updated conversation settings payload'));
    }
    if (target.color !== snapshot.color) {
        const colorUpdated = await chatApi.updateColor(conversationId, snapshot.color);
        applyConversationMetadataSnapshot(target, parseConversationRecordForId(colorUpdated, conversationId, 'Updated conversation color payload'));
    }
    if (target.isFavorite !== snapshot.isFavorite) {
        const favoriteUpdated = await chatApi.updateFavorite(conversationId, snapshot.isFavorite);
        applyConversationMetadataSnapshot(target, parseConversationRecordForId(favoriteUpdated, conversationId, 'Updated conversation favorite payload'));
    }
};

const createPersistedConversation = async (chatApi: ChatPageApi['webui']['chat'], snapshot: ConversationPersistenceSnapshot): Promise<Conversation> => {
    const createPayload = buildConversationCreatePayload(snapshot);
    const created = await chatApi.create(createPayload);
    const persistedConversation = await parseCreatedConversationWithCleanup(chatApi, created, snapshot.id, snapshot.title);
    try {
        await syncPersistedConversationSnapshot(chatApi, snapshot, persistedConversation);
    } catch (error) {
        const runtimeError = ensureError(error);
        return rollbackCreatedConversation(chatApi, snapshot.id, runtimeError, 'failed to delete partially synchronized created conversation');
    }
    return persistedConversation;
};

export { createPersistedConversation, parseCreatedConversationWithCleanup };
