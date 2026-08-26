/* SoAI - Chat page agent contracts [frontend/assets/ts/pages/chat/controllers/chatpageagent/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';
import type { ChatMessage, ChatMessageManager, ChatPageApi, ChatPostRenderRequestType, ChatStreamTerminalUpdate, Conversation, LoadConversationMessagesOptions, ToolImageHydrationCoordinator } from '@features/chat/public.ts';
import type { ConversationActivationSnapshot } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface AgentConversationManager {
    ensureConversationPersisted(conversation: Conversation): Promise<void>;
    updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
    deleteConversation(conversationId: string): Promise<void>;
}

interface AgentMessageHost extends Pick<ChatMessageManager, 'renderMessage' | 'resolveMessageRenderPresentation'> {
    postRender(container: Element | null): void;
    postRenderRequest(container: Element | null, type: ChatPostRenderRequestType): void;
    renderMarkdownContent(content: string): string;
    escapeHtml(value: string): string;
    escapeAttribute(value: string): string;
    invalidateMessageCache(message: ChatMessage | null | undefined): void;
    invalidateMessageProjectionCache(message: ChatMessage | null | undefined): void;
    resolveRunningActivityRefreshDelayMs(message: ChatMessage, nowMs: number): number | null;
}

interface ChatAgentConversationPort {
    getApi(): ChatPageApi;
    getConversations(): Map<string, Conversation>;
    getCurrentConversation(): Conversation | null;
    getConversationById(conversationId: string): Conversation | null;
    getToolImageHydrationCoordinator(): ToolImageHydrationCoordinator;
    getCurrentConversationId(): string | null;
    captureConversationActivationSnapshot(): ConversationActivationSnapshot;
    isConversationActivationSnapshotCurrent(activation: ConversationActivationSnapshot, expectedConversationId: string): boolean;
    setCurrentConversationId(conversationId: string | null): void;
    replaceConversationRoute(conversationId: string | null): Promise<void>;
    switchConversationById(conversationId: string): void;
    refreshConversationsUI(): Promise<void>;
    loadConversationMessages(conversationId: string, options?: LoadConversationMessagesOptions): Promise<void>;
    getCurrentModel(): string | null;
    setCurrentModel(modelId: string | null): void;
    manager: AgentConversationManager;
    isChatStreamingConversation(conversationId: string): boolean;
    isConversationExecuting(conversationId: string): boolean;
    syncConversationSidebarStatus(conversationId: string): void;
}

interface ChatAgentRenderingPort {
    messages: AgentMessageHost;
    getChatInput(): HTMLTextAreaElement | null;
    clearChatInput(): void;
    queryDocumentUI(selector: string): Element[];
    setButtonLoading?(target: string | Element, loading: boolean, options?: SetButtonLoadingOptions): void;
    getCachedIcon(iconName: IconName, options?: IconOptions): TrustedHtml;
    sanitizeAttribute(value: string): string;
    scheduleStreamingTimelineRender(conversationId: string, message: ChatMessage): void;
    updateConversationRenderCache?(conversationId: string, messageDomId: string, signature: string): void;
    invalidateChatMarkup(scope: 'current' | 'list' | 'both'): void;
    rerenderCurrentConversation(): Promise<void>;
    scheduleConversationRender(): Promise<void>;
}

interface ChatAgentInteractionPort {
    hasClipboardSupport(): boolean;
    copyToClipboard(text: string, options?: { notify?: (message: string, type: NotificationType) => void }): Promise<void>;
    syncToolsEnabledParameterFromConversation(conversationId: string): void;
    handleCurrentConversationToolsLockStateChange(): void;
    refreshTokenCounterPreview(): void;
    updateInputState(): void;
    updateParameterUI(): void;
    updateInputQueuePreview(): void;
}

interface ChatAgentPlanBarPort {
    isVisible(): boolean;
    setVisible(visible: boolean): void;
}

interface ChatAgentWorkflowPort extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    runWithBoundary<T>(scope: string, functionValue: () => Promise<T>): Promise<T>;
    logWarning(message: string, error: Error): void;
}

interface ChatPageAgentHost {
    conversation: ChatAgentConversationPort;
    rendering: ChatAgentRenderingPort;
    interaction: ChatAgentInteractionPort;
    planBar: ChatAgentPlanBarPort;
    workflow: ChatAgentWorkflowPort;
}

interface ChatPageAgentService {
    initialize(): void;
    waitForPendingModeUpdate(): Promise<void>;
    updateUiForCurrentConversation(): void;
    handleConversationRendered(): void;
    handleKeyDown(event: KeyboardEvent): boolean;
    handleModeCycle(): void;
    handleModeSelect(mode: AgentMode): void;
    handleCompact(): void;
    handleRegenerateCompaction(assistantTurnAtMs: number): Promise<void>;
    handleStreamTerminalized(update: ChatStreamTerminalUpdate): void;
    handleToggleTodoPanel(): void;
    handleTogglePlanBar(): void;
    handleViewAgentPlan(): void;
    getCanonicalPlan(): AgentCanonicalPlan | null;
    resolveModeForConversation(conversationId: string): AgentMode;
    resolveRunningTurnId(conversationId: string): string | null;
    isRenderingActive(conversationId: string): boolean;
    dispose(): void;
}

export type { AgentConversationManager, AgentMessageHost, ChatAgentPlanBarPort, ChatPageAgentHost, ChatPageAgentService };
