/* SoAI - Chat feature storage contracts [frontend/assets/ts/features/chat/storage/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ChatUiStorage } from '@core/chat/protocols.ts';
import type { ChatPageApi } from '@features/chat/pagecontracts/types.ts';
import type { ChatStreamMessageSavedReconciliation } from '@features/chat/chatstreamservice/messageSavedReconciliation.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatParameters, Conversation } from '@features/chat/storage/storageModels.ts';

interface ChatStorageConversationManager {
    isConversationPersisted(conversationId: string): boolean;
    ensureConversationPersisted(conversation: Conversation): Promise<void>;
    markConversationPersisted(conversationId: string): void;
    markAllConversationsPersisted(): void;
}

interface ChatStorageChatStreamService {
    isStreaming(conversationId: string): boolean;
    getActiveAssistantMessage(conversationId: string): ChatMessage | null;
    reconcileMessageSaved(conversationId: string): Promise<ChatStreamMessageSavedReconciliation>;
}

interface ChatStorageManagerState {
    getConversations(): Map<string, Conversation>;
    setConversations(conversations: Map<string, Conversation>): void;
    getCurrentConversationId(): string | null;
    setCurrentConversationId(conversationId: string | null): void;
    getCurrentModel(): string | null;
    setCurrentModel(modelId: string | null): void;
    getParameters(): ChatParameters;
    setParameters(parameters: ChatParameters): void;
    getSidebarOpen(): boolean;
    setSidebarOpen(open: boolean): void;
    getShowFavoritesAtTop(): boolean;
    setShowFavoritesAtTop(show: boolean): void;
}

interface ChatStorageManagerDependencies {
    storage: ChatUiStorage;
    api: ChatPageApi;
    state: ChatStorageManagerState;
    conversationManager: ChatStorageConversationManager;
    chatStreamService: ChatStorageChatStreamService;
    isMobileSidebarViewport(): boolean;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    refreshConversationListUI(): Promise<void>;
    refreshConversationMetadataUI(): Promise<void>;
    refreshConversationsUI(): Promise<void>;
    clearConversationSelection(): Promise<void>;
    handleConversationDeleted(conversationId: string): Promise<void>;
    handleConversationSettingsAuthorityChanged(conversationId: string): void;
    stopStreaming(reason?: string): void;
    runWithBoundary<T>(name: string, functionValue: () => Promise<T>): Promise<T>;
    showNotification(message: string, type: NotificationType, duration?: number): void;
}

interface ErrorHandler {
    warn?(scope: string, message: string, error?: Error): void;
}

interface ChatStorageManagerOptions {
    errorHandler?: ErrorHandler;
}

interface SaveAndSyncOptions {
    force?: boolean;
    sync?: boolean;
    messageSyncMode?: 'replace' | 'append_tail';
}

export type { ChatStorageChatStreamService, ChatStorageConversationManager, ChatStorageManagerDependencies, ChatStorageManagerOptions, ChatStorageManagerState, ErrorHandler, SaveAndSyncOptions };
