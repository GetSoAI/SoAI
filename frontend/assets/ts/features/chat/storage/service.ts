/* SoAI - Chat feature storage service [frontend/assets/ts/features/chat/storage/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { cloneChatParameters, resolveStoredParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import type { ChatParameters, ChatStorageMessageRecord, Conversation, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';
import { deleteMessageByCursor, loadConversationCatalogFromBackend, loadConversationMessages, resubmitUserMessage, syncConversation, saveAndSync } from '@features/chat/storage/actions.ts';
import { refreshRunningActivitySnapshot } from '@features/chat/storage/messageWindowLoading.ts';
import { refreshConversationList } from '@features/chat/storage/conversationListRefresh.ts';
import { requireConversationId } from '@features/chat/validation/ids.ts';
import { LocalMessageWriteEchoRegistry } from '@features/chat/storage/localMessageWriteEchoRegistry.ts';
import { MessageWindowRequestRuntime } from '@features/chat/storage/messageWindowRequestRuntime.ts';
import { loadState, saveChatState, savePreferences } from '@features/chat/storage/persistence.ts';
import { buildPreferencesSnapshot } from '@features/chat/storage/state.ts';
import { subscribeToConversationEvents } from '@features/chat/storage/events.ts';
import type { ChatStorageManagerDependencies, ChatStorageManagerOptions, ErrorHandler, SaveAndSyncOptions, ChatStorageChatStreamService } from '@features/chat/storage/contracts.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isJsonObject, type JsonRecord, type JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import { validateStoredMessageTimestamps } from '@features/chat/storage/messageTimestampValidation.ts';
import { readCompleteConversationSnapshot } from '@features/chat/storage/conversationSnapshotLoading.ts';

class ChatStorageManager {
    errorHandler: ErrorHandler | null;
    storage: ChatUiStorage;
    api: ChatPageApi;
    chatStreamService: ChatStorageChatStreamService;
    state: ChatStorageManagerDependencies['state'];
    conversationManager: ChatStorageManagerDependencies['conversationManager'];
    initialized = false;
    lastSerializedPreferences: string | null = null;
    #disposed = false;
    readonly #websocketSubscriptions = new ResourceTracker();
    #runWithBoundary: ChatStorageManagerDependencies['runWithBoundary'];
    #isMobileSidebarViewport: ChatStorageManagerDependencies['isMobileSidebarViewport'];
    #invalidateChatMarkup: ChatStorageManagerDependencies['invalidateChatMarkup'];
    #refreshConversationListUI: ChatStorageManagerDependencies['refreshConversationListUI'];
    #refreshConversationMetadataUI: ChatStorageManagerDependencies['refreshConversationMetadataUI'];
    #refreshConversationsUI: ChatStorageManagerDependencies['refreshConversationsUI'];
    #clearConversationSelection: ChatStorageManagerDependencies['clearConversationSelection'];
    #handleConversationDeleted: ChatStorageManagerDependencies['handleConversationDeleted'];
    #handleConversationSettingsAuthorityChanged: ChatStorageManagerDependencies['handleConversationSettingsAuthorityChanged'];
    #stopStreaming: ChatStorageManagerDependencies['stopStreaming'];
    #showNotification: ChatStorageManagerDependencies['showNotification'];
    readonly #localMessageWrites = new LocalMessageWriteEchoRegistry();
    readonly messageWindowRequests = new MessageWindowRequestRuntime();
    #conversationSyncTails: Map<string, Promise<void>> = new Map();

    constructor(dependencies: ChatStorageManagerDependencies, options: ChatStorageManagerOptions = {}) {
        this.storage = dependencies.storage;
        this.api = dependencies.api;
        this.state = dependencies.state;
        this.conversationManager = dependencies.conversationManager;
        this.chatStreamService = dependencies.chatStreamService;
        this.#runWithBoundary = dependencies.runWithBoundary;
        this.#isMobileSidebarViewport = dependencies.isMobileSidebarViewport;
        this.#invalidateChatMarkup = dependencies.invalidateChatMarkup;
        this.#refreshConversationListUI = dependencies.refreshConversationListUI;
        this.#refreshConversationMetadataUI = dependencies.refreshConversationMetadataUI;
        this.#refreshConversationsUI = dependencies.refreshConversationsUI;
        this.#clearConversationSelection = dependencies.clearConversationSelection;
        this.#handleConversationDeleted = dependencies.handleConversationDeleted;
        this.#handleConversationSettingsAuthorityChanged = dependencies.handleConversationSettingsAuthorityChanged;
        this.#stopStreaming = dependencies.stopStreaming;
        this.#showNotification = dependencies.showNotification;
        this.errorHandler = options.errorHandler === undefined ? null : options.errorHandler;
    }

    resolveUserKey(): string {
        const raw = this.storage.session?.username;
        const normalized = toTrimmedString(raw);
        if (!normalized) {
            throw new Error('Chat storage manager requires an authenticated username');
        }
        return normalized;
    }

    isActive(): boolean {
        return !this.#disposed;
    }

    resolveStoredPreferences(storedPreferences: JsonValue): ChatParameters {
        const normalizedStoredPreferences = isJsonObject(storedPreferences) ? storedPreferences : {};
        const resolvedParameters = resolveStoredParameters(normalizedStoredPreferences);
        return cloneChatParameters(resolvedParameters);
    }

    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T> {
        return this.#runWithBoundary(name, functionValue);
    }

    async loadState(): Promise<void> {
        await loadState(this);
    }

    getPreferencesSnapshot(): JsonRecord {
        return buildPreferencesSnapshot(this);
    }

    saveState(force = false): void {
        this.saveChatState(force);
        this.savePreferences(force);
    }

    saveChatState(force = false): void {
        return saveChatState(this, force);
    }

    savePreferences(force = false): void {
        return savePreferences(this, force);
    }

    isMobileSidebarViewport(): boolean {
        return this.#isMobileSidebarViewport();
    }

    validateStoredMessageTimestamps(): void {
        validateStoredMessageTimestamps(this.state.getConversations());
    }

    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void {
        return this.#invalidateChatMarkup(scope);
    }

    refreshConversationListUI(): Promise<void> {
        return this.#refreshConversationListUI();
    }

    refreshConversationMetadataUI(): Promise<void> {
        return this.#refreshConversationMetadataUI();
    }

    refreshConversationList(): Promise<void> {
        return refreshConversationList(this);
    }

    refreshConversationsUI(): Promise<void> {
        return this.#refreshConversationsUI();
    }

    clearConversationSelection(): Promise<void> {
        return this.#clearConversationSelection();
    }

    handleConversationDeleted(conversationId: string): Promise<void> {
        return this.#handleConversationDeleted(conversationId);
    }

    handleConversationSettingsAuthorityChanged(conversationId: string): void {
        this.#handleConversationSettingsAuthorityChanged(conversationId);
    }

    stopStreaming(reason?: string): void {
        this.#stopStreaming(reason);
    }

    showNotification(message: string, type: NotificationType, duration?: number): void {
        this.#showNotification(message, type, duration);
    }

    async runSerializedConversationSync<T>(conversationId: string, operation: () => Promise<T>): Promise<T> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        const previous = this.#conversationSyncTails.get(normalizedConversationId) ?? null;
        const startAfter = previous
            ? previous.catch((error) => {
                  const runtimeError = ensureError(error);
                  this.errorHandler?.warn?.('ChatStorage', 'Prior conversation sync failed; continuing with the latest sync request', runtimeError);
              })
            : null;
        const operationPromise = startAfter ? startAfter.then(operation) : operation();
        const tail = operationPromise.then(
            () => {},
            () => {}
        );
        this.#conversationSyncTails.set(normalizedConversationId, tail);
        try {
            return await operationPromise;
        } finally {
            const currentTail = this.#conversationSyncTails.get(normalizedConversationId);
            if (currentTail === tail) {
                this.#conversationSyncTails.delete(normalizedConversationId);
            }
        }
    }

    markLocalMessageWrite(conversationId: string, messageCount: number, lastModifiedAtMs: number): void {
        this.#localMessageWrites.mark(conversationId, messageCount, lastModifiedAtMs);
    }

    consumeMatchingLocalMessageWrite(conversationId: string, messageCount: number, lastModifiedAtMs: number): boolean {
        return this.#localMessageWrites.consume(conversationId, messageCount, lastModifiedAtMs);
    }

    async loadConversationCatalogFromBackend(): Promise<void> {
        await loadConversationCatalogFromBackend(this);
    }

    async loadConversationMessages(conversationId: string, options: LoadConversationMessagesOptions = {}): Promise<void> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        await this.runSerializedConversationSync(normalizedConversationId, async () => {
            await loadConversationMessages(this, normalizedConversationId, options);
        });
    }

    evictConversationMessages(conversationId: string): void {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        this.messageWindowRequests.invalidateConversation(normalizedConversationId);
        const conversation = this.state.getConversations().get(normalizedConversationId);
        if (!conversation) return;
        conversation.messages = [];
        conversation.messagesHydrated = false;
        delete conversation.history;
    }

    async readConversationSnapshot(conversationId: string, signal?: AbortSignal): Promise<Conversation> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        return await readCompleteConversationSnapshot(this, normalizedConversationId, signal);
    }

    async refreshRunningActivitySnapshot(conversationId: string): Promise<void> {
        const normalizedConversationId = requireConversationId(conversationId, 'Conversation');
        await refreshRunningActivitySnapshot(this, normalizedConversationId);
    }

    async syncConversation(conversation: Conversation): Promise<void> {
        await syncConversation(this, conversation, 'replace');
    }

    async saveAndSync(conversation: ConversationContract | null, options: SaveAndSyncOptions = {}): Promise<void> {
        const force = options.force === true;
        const sync = options.sync !== false;
        const messageSyncMode = options.messageSyncMode === 'append_tail' ? 'append_tail' : 'replace';
        await saveAndSync(this, conversation, force, sync, messageSyncMode);
    }

    async resubmitUserMessage(conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }): Promise<void> {
        await resubmitUserMessage(this, conversation, inputArguments);
    }

    async deleteMessageByCursor(conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }): Promise<void> {
        await deleteMessageByCursor(this, conversation, inputArguments);
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        this.cleanupConversationEventSubscriptions();
        this.#localMessageWrites.clear();
        this.messageWindowRequests.clear();
        this.#conversationSyncTails.clear();
        this.initialized = false;
    }

    subscribeToConversationEvents(): void {
        if (this.#disposed) {
            throw new Error('Chat storage manager is inactive');
        }
        this.cleanupConversationEventSubscriptions();
        subscribeToConversationEvents(this, this.#websocketSubscriptions);
    }

    cleanupConversationEventSubscriptions(): void {
        this.#websocketSubscriptions.cleanup();
    }
}

export { ChatStorageManager };
