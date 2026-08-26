/* SoAI - Chat conversation rendering and preparation ownership [frontend/assets/ts/pages/chat/controllers/chatpage/conversations/ChatConversationViewController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { initializeChatSearch, refreshConversationsUI, renderCurrentConversationView, type ChatConversationListRenderDependencies, type ChatConversationRenderOutcome, type ChatCurrentConversationRenderDependencies, type ChatSearchDependencies } from '@pages/chat/controllers/page/view.ts';
import { CHAT_SELECTORS, ChatPageEmptyState, resolveConversationChatStreaming, resolveConversationExecutionState, type Conversation } from '@features/chat/public.ts';
import type { ChatConversationActionsContract } from '@pages/chat/controllers/chatconversationactionscontroller/contracts.ts';
import { replaceChatConversationRoute } from '@pages/chat/controllers/navigation/routeSynchronization.ts';
import { invalidateCurrentConversationMarkup } from '@pages/chat/controllers/page/renderer/chatMarkupInvalidationController.ts';
import { getCurrentConversation, reportRequestFailure } from '@pages/chat/controllers/page/state.ts';
import type { ChatConversationTerminalIndicator } from '@core/chat/protocols.ts';
import type { ChatConversationViewContract, ConversationSidebarStatus, ConversationSidebarStatusSyncOptions, SidebarListReadiness } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { ChatConfigurationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConfigurationRuntime.ts';
import type { ChatComposerSurfaceRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatComposerSurfaceRuntime.ts';
import type { ChatConversationRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatConversationRuntime.ts';
import type { ChatTurnRuntimeOwner } from '@pages/chat/controllers/chatpage/runtime/ChatTurnRuntime.ts';
import type { ChatConversationStateHost } from '@pages/chat/state/ChatConversationStateManager.ts';
import type { ChatSettingsStateHost } from '@pages/chat/state/ChatSettingsStateManager.ts';
import type { ChatViewStateHost } from '@pages/chat/state/ChatViewStateManager.ts';
import type { ChatRuntimeServicesHost } from '@pages/chat/state/ChatRuntimeServiceManager.ts';
import type { ChatUiTaskScopeHost } from '@pages/chat/controllers/chatpage/runtime/ChatUiTaskScopeManager.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import type { SelectionState } from '@core/selection/state.ts';
import type { ChatModelSessionContract } from '@pages/chat/controllers/chatpage/models/contracts.ts';
import type { ChatPagePresentationContract } from '@pages/chat/controllers/chatpage/presentation/contracts.ts';
import { updateHeaderFavoriteButton, updateHeaderToolsToggleButton } from '@pages/chat/controllers/chatUiBehaviors.ts';
import { initializeEmptyStateNav } from '@pages/chat/controllers/page/renderer/emptyState.ts';
import { ConversationListPresentationController } from '@pages/chat/controllers/page/renderer/ConversationListPresentationController.ts';
import { syncCurrentConversationColorAttribute } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';

interface ChatConversationViewStatePort extends ChatComposerSurfaceRuntimeOwner, ChatConfigurationRuntimeOwner, ChatConversationRuntimeOwner, ChatTurnRuntimeOwner, ChatConversationStateHost, ChatSettingsStateHost, ChatViewStateHost, ChatRuntimeServicesHost {}

interface ChatConversationViewRuntimePort extends ChatUiTaskScopeHost, PageServicesOwnerHost, PageLifecycleOwnerHost, PageDomOwnerHost, PageFeedbackOwnerHost {}

interface ChatConversationViewDependencies extends ChatConversationViewStatePort, ChatConversationViewRuntimePort {
    router: Parameters<typeof replaceChatConversationRoute>[0]['router'];
    pageContext: { sanitizer: SanitizerApi };
    modelSession: ChatModelSessionContract;
    presentation: ChatPagePresentationContract;
    conversationSelection: SelectionState;
}

class ChatConversationViewController implements ChatConversationViewContract {
    readonly #dependencies: ChatConversationViewDependencies;
    readonly #listRender: ChatConversationListRenderDependencies;
    readonly #currentRender: ChatCurrentConversationRenderDependencies;
    readonly #search: ChatSearchDependencies;
    readonly #renderedHandlers = new Set<(outcome: ChatConversationRenderOutcome) => void>();
    readonly #emptyState = new ChatPageEmptyState();
    readonly #listPresentation: ConversationListPresentationController;
    #actions: ChatConversationActionsContract | null = null;

    constructor(dependencies: ChatConversationViewDependencies) {
        this.#dependencies = dependencies;
        this.#listRender = {
            conversationRuntime: dependencies.conversationRuntime,
            conversationState: dependencies.conversationState,
            settings: dependencies.settings,
            viewState: dependencies.viewState,
            taskScope: dependencies.taskScope,
            conversationView: this,
            conversationToolbarSession: {
                isConversationSelected: (conversationId) => dependencies.conversationSelection.has(conversationId)
            },
            presentation: dependencies.presentation,
            pageDom: dependencies.pageDom,
            pageContext: dependencies.pageContext
        };
        this.#currentRender = {
            composerSurface: dependencies.composerSurface,
            conversationRuntime: dependencies.conversationRuntime,
            turnRuntime: dependencies.turnRuntime,
            conversationState: dependencies.conversationState,
            viewState: dependencies.viewState,
            conversationView: this,
            modelSession: dependencies.modelSession,
            presentation: dependencies.presentation,
            taskScope: dependencies.taskScope,
            pageDom: dependencies.pageDom,
            pageLifecycle: dependencies.pageLifecycle,
            pageContext: dependencies.pageContext,
            emptyState: this.#emptyState
        };
        this.#listPresentation = new ConversationListPresentationController(this.#listRender);
        this.#search = {
            viewState: dependencies.viewState,
            services: dependencies.services,
            pageDom: dependencies.pageDom,
            renderConversationList: () => this.#renderList()
        };
    }

    initializeSearch(): void {
        initializeChatSearch(this.#search);
    }

    dispose(): void {
        this.#actions?.dispose();
        this.#actions = null;
        this.#listPresentation.dispose();
        this.#emptyState.dispose();
        this.#renderedHandlers.clear();
    }

    onRendered(handler: (outcome: ChatConversationRenderOutcome) => void): () => void {
        this.#renderedHandlers.add(handler);
        return () => this.#renderedHandlers.delete(handler);
    }

    #emitRendered(outcome: ChatConversationRenderOutcome): void {
        for (const handler of this.#renderedHandlers) handler(outcome);
    }

    initializeActions(actions: ChatConversationActionsContract): void {
        if (this.#actions) {
            actions.dispose();
            return;
        }
        this.#actions = actions;
    }

    initializeEmptyStateNavigation(container: Element): void {
        initializeEmptyStateNav(this.#currentRender, container);
    }

    async refresh(): Promise<void> {
        const outcome = await refreshConversationsUI({
            renderList: () => this.#renderList(),
            current: this.#currentRender,
            updateHeaderActions: () => this.#updateHeaderActions()
        });
        this.#emitRendered(outcome);
    }

    async refreshListAndHeader(): Promise<void> {
        await this.#renderList();
        const messagesContainer = this.#dependencies.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
        if (messagesContainer) syncCurrentConversationColorAttribute(this.#currentRender, messagesContainer, this.current());
        this.#updateHeaderActions();
    }

    #updateHeaderActions(): void {
        const headerHost = {
            presentation: {
                pageDom: this.#dependencies.pageDom,
                getCachedIcon: (name: Parameters<ChatPagePresentationContract['cachedIcon']>[0], options: Parameters<ChatPagePresentationContract['cachedIcon']>[1]) => this.#dependencies.presentation.cachedIcon(name, options)
            },
            conversations: {
                getCurrentConversationId: () => this.#dependencies.conversationState.currentConversationId,
                getConversationById: (conversationId: string) => this.#dependencies.conversationState.conversations.get(conversationId) ?? null,
                isConversationExecuting: (conversationId: string) => this.isExecuting(conversationId)
            }
        };
        updateHeaderFavoriteButton(headerHost);
        updateHeaderToolsToggleButton(headerHost);
    }

    async renderList(): Promise<void> {
        await this.#renderList();
    }

    async revealInList(conversationId: string): Promise<boolean> {
        return await this.#listPresentation.revealConversation(conversationId);
    }

    async #renderList(): Promise<void> {
        await this.#listPresentation.render();
    }

    async syncSidebarListVisibility(visible: boolean): Promise<SidebarListReadiness> {
        return await this.#listPresentation.syncVisibility(visible);
    }

    async renderCurrent(): Promise<void> {
        const outcome = await renderCurrentConversationView(this.#currentRender);
        this.#emitRendered(outcome);
    }

    async prepareMessages(conversationId: string): Promise<void> {
        const conversation = this.#dependencies.conversationState.conversations.get(conversationId) ?? null;
        if (!conversation) throw new Error(`Conversation not found: ${conversationId}`);
        const activation = this.#dependencies.taskScope.concurrency.captureConversationActivationSnapshot();
        await this.#dependencies.conversationRuntime.requireMessages().preRenderConversationAssistantBodies(conversation, { signal: activation.signal });
    }

    current(): Conversation | null {
        return getCurrentConversation(this.#dependencies);
    }

    invalidate(scope: 'current' | 'list' | 'both' = 'both'): void {
        if (scope !== 'list') invalidateCurrentConversationMarkup(this.#dependencies);
        if (scope !== 'current') this.#listPresentation.invalidate();
    }

    refreshWorkerRendering(): void {
        this.#dependencies.taskScope.concurrency.bumpWorkerRenderEpoch();
        this.#dependencies.conversationRuntime.requireMessages().refreshRenderWorkerResources();
        this.invalidate('both');
    }

    invalidateMessagePresentation(): void {
        this.#dependencies.taskScope.concurrency.bumpWorkerRenderEpoch();
        this.#dependencies.conversationRuntime.requireMessages().invalidatePresentationRendering();
        this.invalidate('current');
    }

    requireActions(): ChatConversationActionsContract {
        if (!this.#actions) throw new Error('Chat conversation actions controller is not initialized');
        return this.#actions;
    }

    replaceRoute(conversationId: string | null, options: { signal?: AbortSignal | null } = {}): Promise<void> {
        return replaceChatConversationRoute(this.#dependencies, conversationId, options);
    }

    isStreaming(conversationId: string): boolean {
        return resolveConversationChatStreaming({
            activeChatConversationIds: this.#dependencies.conversationState.activeChatConversationIds,
            conversationId,
            isStreamingConversation: (candidateConversationId) => this.#dependencies.turnRuntime.requireStreaming().isStreamingConversation(candidateConversationId)
        });
    }

    resolveSidebarStatus(conversationId: string): ConversationSidebarStatus {
        const execution = resolveConversationExecutionState({
            activeChatConversationIds: this.#dependencies.conversationState.activeChatConversationIds,
            conversationId,
            isStreamingConversation: (candidateConversationId) => this.#dependencies.turnRuntime.requireStreaming().isStreamingConversation(candidateConversationId),
            isAgentRenderingActive: (candidateConversationId) => this.#dependencies.turnRuntime.requireAgent().isRenderingActive(candidateConversationId)
        });
        return {
            executionStatus: execution.executionStatus,
            terminalStatus: execution.isExecuting ? null : this.terminalIndicator(conversationId),
            attentionStatus: 'none',
            isExecuting: execution.isExecuting,
            isChatStreaming: execution.isChatStreaming
        };
    }

    isExecuting(conversationId: string): boolean {
        return this.resolveSidebarStatus(conversationId).isExecuting;
    }

    syncSidebarStatus(conversationId: string, options: ConversationSidebarStatusSyncOptions): boolean {
        const status = this.resolveSidebarStatus(conversationId);
        if (status.isExecuting && this.#dependencies.viewState.activeColorPickerConversationId === conversationId) {
            this.#dependencies.presentation.hideConversationColorPicker();
        }
        if (this.#dependencies.conversationState.currentConversationId === conversationId) {
            this.#dependencies.configurationRuntime.optionalConversationSettings()?.handleCurrentConversationToolsLockStateChange();
            this.#dependencies.configurationRuntime.requireParameters().updateParameterUI();
            this.#dependencies.turnRuntime.requireAgent().updateUiForCurrentConversation();
            this.#dependencies.modelSession.updateUi();
        }
        if (options.scheduleConversationListRender) {
            this.#dependencies.taskScope.run('chat:renderConversationList', () => this.renderList());
        }
        return this.#dependencies.conversationState.currentConversationId === conversationId;
    }

    terminalIndicator(conversationId: string): ChatConversationTerminalIndicator | null {
        return this.#dependencies.runtimeServices.attention.getConversationTerminalIndicator(conversationId);
    }

    acknowledgeTerminalAttentionIfViewed(conversationId: string | null, assistantAtMs: number | null = null): void {
        const normalized = typeof conversationId === 'string' ? conversationId.trim() : '';
        if (!normalized || !this.#dependencies.runtimeServices.presence.isActivelyViewingConversation(normalized) || this.isExecuting(normalized)) return;
        if (assistantAtMs !== null) {
            this.#dependencies.runtimeServices.attention.markConversationSeen(normalized, assistantAtMs);
            return;
        }
        this.#dependencies.runtimeServices.attention.markTrackedConversationSeen(normalized);
    }

    refreshActivityClock(): void {
        this.#dependencies.turnRuntime.requireStreaming().refreshCurrentConversationActivityClock();
    }

    activeComparisonRun(conversationId: string): { assistantTurnTimestamp: number; variantCount: number } | null {
        return this.#dependencies.turnRuntime.requireStreaming().getActiveComparisonRun(conversationId);
    }

    reportFailure(error: Error): void {
        reportRequestFailure(this.#dependencies, error);
    }

    openEnsuringLoaded(conversationId: string): void {
        this.requireActions().openConversationEnsuringLoaded(conversationId);
    }

    async refreshSidebar(): Promise<void> {
        await this.#dependencies.conversationRuntime.requireStorage().refreshConversationList();
    }
}

export { ChatConversationViewController };
export type { ChatConversationViewContract } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
export type { ChatConversationViewHost } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
export type { ChatConversationViewDependencies };
