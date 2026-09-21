/* SoAI - Chat feature manager contracts [frontend/assets/ts/features/chat/storage/managerContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { JsonRecord, JsonValue } from '@core/types/jsonValues.ts';
import type { ConversationContract } from '@features/chat/ChatTypes.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import type { ChatStorageChatStreamService, ChatStorageConversationManager, ChatStorageManagerState } from '@features/chat/storage/contracts.ts';
import type { MessageWindowRequestRuntime } from '@features/chat/storage/messageWindowRequestRuntime.ts';
import type { ChatParameters, ChatStorageMessageRecord, Conversation, LoadConversationMessagesOptions } from '@features/chat/storage/storageModels.ts';

interface ChatStorageManagerContract {
    api: ChatPageApi;
    storage: ChatUiStorage;
    state: ChatStorageManagerState;
    conversationManager: ChatStorageConversationManager;
    chatStreamService: ChatStorageChatStreamService;
    messageWindowRequests: MessageWindowRequestRuntime;
    initialized: boolean;
    lastSerializedPreferences: string | null;
    errorHandler: { warn?: (scope: string, message: string, error?: Error) => void } | null;
    isActive(): boolean;

    resolveStoredPreferences(storedPreferences: JsonValue): ChatParameters;
    getPreferencesSnapshot(): JsonRecord;
    isMobileSidebarViewport(): boolean;

    showNotification(message: string, type: NotificationType, duration?: number): void;
    refreshConversationListUI(): Promise<void>;
    refreshConversationMetadataUI(): Promise<void>;
    refreshConversationList(): Promise<void>;
    refreshConversationsUI(): Promise<void>;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    clearConversationSelection(): Promise<void>;
    handleConversationDeleted(conversationId: string): Promise<void>;
    handleConversationSettingsAuthorityChanged(conversationId: string): void;
    stopStreaming(reason?: string): void;

    saveChatState(force?: boolean): void;
    savePreferences(force?: boolean): void;
    saveState(force?: boolean): void;
    validateStoredMessageTimestamps(): void;

    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    markLocalMessageWrite(conversationId: string, messageCount: number, lastModifiedAtMs: number): void;
    consumeMatchingLocalMessageWrite(conversationId: string, messageCount: number, lastModifiedAtMs: number): boolean;
    runSerializedConversationSync<T>(conversationId: string, operation: () => Promise<T>): Promise<T>;

    loadConversationCatalogFromBackend(): Promise<void>;
    loadConversationMessages(conversationId: string, options?: LoadConversationMessagesOptions): Promise<void>;
    evictConversationMessages(conversationId: string): void;
    refreshRunningActivitySnapshot(conversationId: string): Promise<void>;
    syncConversation(conversation: Conversation): Promise<void>;
    saveAndSync(conversation: ConversationContract | null, options?: { force?: boolean; sync?: boolean; messageSyncMode?: 'replace' | 'append_tail' }): Promise<void>;
    resubmitUserMessage(conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number; message: ChatStorageMessageRecord }): Promise<void>;
    deleteMessageByCursor(conversation: ConversationContract, inputArguments: { createdAtMs: number; messageId: number }): Promise<void>;
}

export type { ChatStorageManagerContract };
