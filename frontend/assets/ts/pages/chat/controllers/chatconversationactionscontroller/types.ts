/* SoAI - Chat conversation actions controller contracts [frontend/assets/ts/pages/chat/controllers/chatconversationactionscontroller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatParameters, ComposerDraftTransferMode, Conversation, LoadConversationMessagesOptions, MessageCursor } from '@features/chat/public.ts';
import type { ChatConcurrencyController } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';
import type { ChatConversationSettingsManagerContract, ConversationDeleteFallbackSnapshot } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
import type { SelectedConversationHydrationState } from '@pages/chat/state/chatConversationHydrationState.ts';
import type { ChatConversationRenameState } from '@pages/chat/state/chatConversationRenameState.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface ConversationManager {
    isConversationPersisted: (conversationId: string) => boolean;
    ensureConversationPersisted: (conversation: Conversation) => Promise<void>;
    switchConversation: (conversationId: string) => { storedModelKey?: string | null };
    deleteConversations: (conversationIds: readonly string[]) => Promise<readonly string[]>;
    forgetConversation: (conversationId: string) => void;
    createNewConversation: () => Promise<Conversation>;
    updateConversationColor: (conversationId: string, color: string | null) => Promise<void>;
    toggleConversationFavorite: (conversationId: string) => Promise<void>;
    setArchived: (conversationId: string, isArchived: boolean) => Promise<void>;
    ensureConversationLoaded: (conversationId: string) => Promise<void>;
    updateConversationTitle: (conversationId: string, title: string) => Promise<void>;
}

interface ChatStreamingController {
    isStreamingConversation: (conversationId: string) => boolean;
    syncConversationStatus: (conversationId: string) => Promise<void>;
    refreshCurrentConversationActivityClock: () => void;
}

interface StorageManager {
    saveChatState: (force?: boolean) => void;
    loadConversationMessages: (conversationId: string, options?: LoadConversationMessagesOptions) => Promise<void>;
    evictConversationMessages: (conversationId: string) => void;
}

interface UiManager {
    beginConversationTransition: (transitionId: number) => void;
    completeConversationTransition: (transitionId: number) => void;
    isConversationTransitionActive: () => boolean;
    setAutoScrollEnabled: (enabled: boolean) => void;
    rememberCurrentConversationScrollPosition: () => void;
    prepareConversationScrollRestore: (conversationId: string) => boolean;
    resolveConversationScrollRestoreCursor: (conversationId: string) => MessageCursor | null;
    forgetConversationScrollPosition: (conversationId: string) => void;
    applyExecutionControls: () => void;
}

type ChatConversationSettingsManager = ChatConversationSettingsManagerContract;

interface ComposerDraftManager {
    beginComposerTransfer(conversationId: string | null, options: { mode: ComposerDraftTransferMode; signal?: AbortSignal }): { complete(): Promise<void>; cancel(): void };
    discardConversation(conversationId: string): void;
}

interface MessageDeleteManager {
    resumePausedDeletesForConversation(conversation: Conversation): void;
}

interface ConversationActionsStateAccess {
    hasConversation: (conversationId: string) => boolean;
    getConversation: (conversationId: string) => Conversation | null;
    getConversations: () => ReadonlyMap<string, Conversation>;
    getCurrentConversationId: () => string | null;
    setCurrentConversationId: (conversationId: string | null) => void;
    getSelectedConversationHydrationState: () => SelectedConversationHydrationState;
    setSelectedConversationHydrationState: (state: SelectedConversationHydrationState) => void;
    setCurrentModel: (modelId: string | null) => void;
    hasModels: () => boolean;
    resolveModelKey: (candidate: string | null | undefined) => string | null;
    getParameters: () => ChatParameters;
    setParameters: (parameters: ChatParameters) => void;
    getSidebarOpen: () => boolean;
    setSidebarOpen: (open: boolean) => void;
    getViewportWidth: () => number;
    getConversationRenameState: () => ChatConversationRenameState | null;
    setConversationRenameState: (renameState: ChatConversationRenameState | null) => void;
}

interface ConversationActionsWorkflowPort extends PageFeedbackOwnerHost {
    runWithBoundary: <T>(name: string, functionValue: () => Promise<T>) => Promise<T>;
    runUiTask: (operationId: string, task: () => Promise<void>) => void;
    handleError?: (error: Error, title: string, options?: { notify?: boolean }) => void;
    notifySaveChanged: () => void;
}

interface ConversationActionsRenderPort {
    getCurrentConversation: () => Conversation | null;
    prepareConversationMessages: (conversationId: string) => Promise<void>;
    getConversationTitleElement: () => HTMLElement | null;
    getConversationTitleInputElement: () => HTMLInputElement | null;
    getConversationListTitleInputElement: () => HTMLInputElement | null;
    refreshConversationsUI: () => Promise<void>;
    refreshConversationListAndHeader: () => Promise<void>;
    renderConversationList: () => Promise<void>;
    revealConversationInList: (conversationId: string) => Promise<boolean>;
    renderCurrentConversation: () => Promise<void>;
    flushDOMUpdates: () => void;
    invalidateChatMarkup: (scope: 'current' | 'list' | 'both') => void;
    updateModelUI: () => void;
    refreshParameterUI: () => void;
    refreshTokenCounterPreview: () => void;
    applyInputActionVisibility: () => void;
    applySidebarState: () => void;
}

interface ConversationActionsNavigationPort {
    replaceConversationRoute: (conversationId: string | null, options?: { signal?: AbortSignal | null }) => Promise<void>;
    captureConversationDeleteFallbackSnapshot: (activeConversationId: string | null) => ConversationDeleteFallbackSnapshot;
    resolveConversationDeleteFallbackId: (snapshot: ConversationDeleteFallbackSnapshot, deletedConversationIds: ReadonlySet<string>) => string | null;
}

interface ConversationActionsHost {
    workflow: ConversationActionsWorkflowPort;
    view: ConversationActionsRenderPort;
    navigation: ConversationActionsNavigationPort;
}

interface ChatConversationActionsControllerRuntime {
    host: ConversationActionsHost;
    state: ConversationActionsStateAccess;
    conversationManager: ConversationManager;
    storageManager: StorageManager;
    uiManager: UiManager;
    chatStreamingController: ChatStreamingController;
    conversationSettingsManager: ChatConversationSettingsManager | null;
    getComposerDraftManager(): ComposerDraftManager | null;
    getMessageDeleteManager(): MessageDeleteManager | null;
    concurrencyScope: ChatConcurrencyController;
}

export type { ChatConversationActionsControllerRuntime, ChatConversationSettingsManager, ChatStreamingController, ComposerDraftManager, ConversationActionsHost, ConversationActionsStateAccess, ConversationManager, MessageDeleteManager, StorageManager, UiManager };
