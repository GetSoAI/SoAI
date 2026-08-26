/* SoAI - Chat feature conversation manager [frontend/assets/ts/features/chat/ChatConversationManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import { ensureConversationLoaded, setConversationArchived } from '@features/chat/conversation/conversationArchiveOperations.ts';
import { deleteConversations } from '@features/chat/conversation/conversationBatchDeletionOperations.ts';
import { toggleConversationFavorite } from '@features/chat/conversation/conversationFavoriteOperations.ts';
import type { ConversationMetadataOperationDependencies } from '@features/chat/conversation/conversationMetadataOperationDeps.ts';
import { ConversationMutationSequencer } from '@features/chat/conversation/conversationMutationSequencing.ts';
import { createPersistedConversation, parseCreatedConversationWithCleanup } from '@features/chat/conversation/conversationPersistenceOperations.ts';
import { applyConversationMetadataSnapshot, applyConversationSettingsSnapshot, buildConversationCreatePayload, parseConversationRecordForId, reconcilePersistedConversationSnapshot, requireConversationPersistenceSnapshot, requireConversationStateEntry } from '@features/chat/conversation/conversationPersistenceSnapshots.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import { updateConversationTitle } from '@features/chat/conversation/conversationTitleOperations.ts';
import { ConversationSettingsUpdateQueue } from '@features/chat/conversation/ConversationSettingsUpdateQueue.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import { requireConversationColor } from '@features/chat/storage/conversationPayloadParsing.ts';
import { persistConversationMessagesToBackendReplace } from '@features/chat/storage/messagePersistence.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { serializeConversationModelSettings, serializeConversationModelSettingsUpdate } from '@core/chat/executionSettingsMapping.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

interface ChatConversationManagerDependencies {
    api: ChatPageApi;
    createConversationId: () => string;
    onConversationPersisted?: (conversationId: string) => void;
}
interface ChatConversationManagerState {
    conversations: Map<string, Conversation>;
    getCurrentConversationId: () => string | null;
    setCurrentConversationId: (conversationId: string | null) => void;
}

class ChatConversationManager {
    #dependencies: ChatConversationManagerDependencies;
    #state: ChatConversationManagerState;
    #chatApi: ChatPageApi['webui']['chat'];
    #persistedConversationIds: Set<string> = new Set();
    #persistingConversationById: Map<string, Promise<void>> = new Map();
    #deletedWhilePersistingConversationIds: Set<string> = new Set();
    #mutationSequencer: ConversationMutationSequencer = new ConversationMutationSequencer();
    #settingsUpdateQueue: ConversationSettingsUpdateQueue = new ConversationSettingsUpdateQueue();
    constructor(dependencies: ChatConversationManagerDependencies, state: ChatConversationManagerState) {
        this.#dependencies = dependencies;
        this.#state = state;
        this.#chatApi = dependencies.api.webui.chat;
    }
    getDefaultTitle(): string {
        return i18n.t('chat.conversation.newTitle');
    }
    isConversationPersisted(conversationId: string): boolean {
        return this.#persistedConversationIds.has(conversationId);
    }
    markConversationPersisted(conversationId: string): void {
        if (this.#persistedConversationIds.has(conversationId)) {
            return;
        }
        this.#persistedConversationIds.add(conversationId);
        this.#dependencies.onConversationPersisted?.(conversationId);
    }
    markAllConversationsPersisted(): void {
        for (const id of this.#state.conversations.keys()) {
            this.#persistedConversationIds.add(id);
        }
    }
    async ensureConversationPersisted(conversation: Conversation): Promise<void> {
        const normalizedId = requireConversationId(conversation.id, 'Conversation');
        if (this.#persistedConversationIds.has(normalizedId)) {
            return;
        }
        const inFlightPersistence = this.#persistingConversationById.get(normalizedId);
        if (inFlightPersistence) {
            await inFlightPersistence;
            return;
        }
        const persistOperation = (async (): Promise<void> => {
            const snapshot = requireConversationPersistenceSnapshot({ ...conversation, id: normalizedId });
            const persistedConversation = await createPersistedConversation(this.#chatApi, snapshot);
            if (this.#deletedWhilePersistingConversationIds.has(normalizedId)) {
                this.#deletedWhilePersistingConversationIds.delete(normalizedId);
                await this.#chatApi.delete(normalizedId);
                return;
            }
            this.#persistedConversationIds.add(normalizedId);
            this.#dependencies.onConversationPersisted?.(normalizedId);
            const local = this.#state.conversations.get(normalizedId);
            if (local) {
                reconcilePersistedConversationSnapshot(local, snapshot, persistedConversation);
                this.#state.conversations.set(normalizedId, local);
            }
        })();
        this.#persistingConversationById.set(normalizedId, persistOperation);
        try {
            await persistOperation;
        } finally {
            if (!this.#persistedConversationIds.has(normalizedId)) {
                this.#deletedWhilePersistingConversationIds.delete(normalizedId);
            }
            this.#persistingConversationById.delete(normalizedId);
        }
    }
    async createNewConversation(): Promise<Conversation> {
        const id = requireConversationId(this.#dependencies.createConversationId(), 'Conversation');
        const title = i18n.t('chat.conversation.newTitle');
        const createPayload = buildConversationCreatePayload({ id, title });
        const created = await this.#chatApi.create(createPayload, {});
        const conversation = await parseCreatedConversationWithCleanup(this.#chatApi, created, id, String(createPayload['title']));
        this.#state.conversations.set(conversation.id, conversation);
        this.#persistedConversationIds.add(conversation.id);
        this.#dependencies.onConversationPersisted?.(conversation.id);
        return conversation;
    }
    switchConversation(conversationId: string): { conversation: Conversation; storedModelKey: string | null } {
        const conversation = this.#state.conversations.get(conversationId);
        if (!conversation) {
            throw new Error('Conversation not found');
        }
        this.#state.setCurrentConversationId(conversationId);
        const storedModelKey = conversation.modelSettings.model;
        return { conversation, storedModelKey };
    }
    async deleteConversation(conversationId: string): Promise<void> {
        await this.deleteConversations([conversationId]);
    }
    async deleteConversations(conversationIds: readonly string[]): Promise<readonly string[]> {
        return await deleteConversations(
            {
                chatApi: this.#chatApi,
                conversations: this.#state.conversations,
                persistedConversationIds: this.#persistedConversationIds,
                persistingConversationById: this.#persistingConversationById,
                deletedWhilePersistingConversationIds: this.#deletedWhilePersistingConversationIds,
                forgetConversation: (conversationId) => this.forgetConversation(conversationId),
                getDefaultTitle: () => this.getDefaultTitle()
            },
            conversationIds
        );
    }
    forgetConversation(conversationId: string): void {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        if (this.#state.getCurrentConversationId() === normalizedConversationId) {
            this.#state.setCurrentConversationId(null);
        }
        this.#state.conversations.delete(normalizedConversationId);
        this.#persistedConversationIds.delete(normalizedConversationId);
        this.#deletedWhilePersistingConversationIds.delete(normalizedConversationId);
        this.#mutationSequencer.clearConversation(normalizedConversationId);
    }
    async updateConversationColor(conversationId: string, color: string | null): Promise<void> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        const conversation = this.#state.conversations.get(normalizedConversationId);
        if (!conversation) return;
        const normalizedColor = requireConversationColor(color, 'Conversation');
        if (conversation.color === normalizedColor) {
            return;
        }
        const previousColor = conversation.color;
        const mutationVersion = this.#mutationSequencer.begin(normalizedConversationId, 'color');
        let expectedUpdatedAt = conversation.updatedAt;
        conversation.color = normalizedColor;
        this.#state.conversations.set(normalizedConversationId, conversation);
        try {
            await this.ensureConversationPersisted(conversation);
            if (!this.#mutationSequencer.isCurrent(normalizedConversationId, 'color', mutationVersion) || this.#state.conversations.get(normalizedConversationId) !== conversation || conversation.color !== normalizedColor) {
                return;
            }
            expectedUpdatedAt = conversation.updatedAt;
            const updated = await this.#chatApi.updateColor(normalizedConversationId, normalizedColor);
            if (!this.#mutationSequencer.isCurrent(normalizedConversationId, 'color', mutationVersion) || this.#state.conversations.get(normalizedConversationId) !== conversation) {
                return;
            }
            applyConversationMetadataSnapshot(conversation, parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation color payload'));
            this.#state.conversations.set(normalizedConversationId, conversation);
        } catch (error) {
            if (!this.#mutationSequencer.isCurrent(normalizedConversationId, 'color', mutationVersion) || this.#state.conversations.get(normalizedConversationId) !== conversation || conversation.color !== normalizedColor || conversation.updatedAt !== expectedUpdatedAt) {
                return;
            }
            conversation.color = previousColor;
            this.#state.conversations.set(normalizedConversationId, conversation);
            throw error;
        }
    }
    async toggleConversationFavorite(conversationId: string): Promise<void> {
        await toggleConversationFavorite(this.#buildConversationMetadataOperationDependencies(), conversationId);
    }
    async setArchived(conversationId: string, isArchived: boolean): Promise<void> {
        await setConversationArchived(this.#buildConversationMetadataOperationDependencies(), conversationId, isArchived);
    }
    async ensureConversationLoaded(conversationId: string): Promise<void> {
        await ensureConversationLoaded(this.#buildConversationMetadataOperationDependencies(), conversationId);
    }
    async updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
    async updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate, returnAuthoritativeSettings: true): Promise<JsonObject>;
    async updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate, returnAuthoritativeSettings = false): Promise<void | JsonObject> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        if (!isPlainObject(patch)) {
            throw new Error('Conversation settings patch must be an object');
        }
        const authoritativeSettings = await this.#settingsUpdateQueue.enqueue(normalizedConversationId, async (): Promise<JsonObject> => {
            const conversation = requireConversationStateEntry(this.#state.conversations, normalizedConversationId);
            if (!isChatConversationSettingsWritable(conversation)) {
                throw new Error('Managed conversation settings are backend-owned and cannot be updated from chat');
            }
            await this.ensureConversationPersisted(conversation);
            const updated = await this.#chatApi.updateSettings(normalizedConversationId, serializeConversationModelSettingsUpdate(patch));
            const authoritativeConversation = parseConversationRecordForId(updated, normalizedConversationId, 'Updated conversation settings payload');
            const authoritativeSettings = serializeConversationModelSettings(authoritativeConversation.modelSettings);
            const currentConversation = this.#state.conversations.get(normalizedConversationId);
            if (!currentConversation) {
                return authoritativeSettings;
            }
            applyConversationSettingsSnapshot(currentConversation, authoritativeConversation);
            this.#state.conversations.set(normalizedConversationId, currentConversation);
            return authoritativeSettings;
        });
        return returnAuthoritativeSettings ? authoritativeSettings : undefined;
    }
    async replaceConversationMessages(conversationId: string, messages: readonly ChatMessage[]): Promise<void> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        const conversation = requireConversationStateEntry(this.#state.conversations, normalizedConversationId);
        const writeResult = await persistConversationMessagesToBackendReplace({
            apiClient: this.#dependencies.api,
            conversationId: normalizedConversationId,
            expectedLastModifiedAtMs: conversation.updatedAt,
            messages
        });
        conversation.updatedAt = Math.max(conversation.updatedAt, writeResult.lastModifiedAtMs);
        conversation.messageCount = writeResult.messageCount;
        if (conversation.history) {
            conversation.history.version = writeResult.lastModifiedAtMs;
            conversation.history.totalCount = writeResult.messageCount;
        }
    }
    async updateConversationTitle(conversationId: string, title: string): Promise<void> {
        await updateConversationTitle(this.#buildConversationMetadataOperationDependencies(), conversationId, title);
    }
    #buildConversationMetadataOperationDependencies(): ConversationMetadataOperationDependencies {
        return {
            chatApi: this.#chatApi,
            conversations: this.#state.conversations,
            ensureConversationPersisted: async (conversation: Conversation): Promise<void> => {
                await this.ensureConversationPersisted(conversation);
            },
            getCurrentConversationId: (): string | null => {
                return this.#state.getCurrentConversationId();
            },
            markConversationPersisted: (conversationId: string): void => {
                this.markConversationPersisted(conversationId);
            },
            mutationSequencer: this.#mutationSequencer
        };
    }
}
export { ChatConversationManager };
