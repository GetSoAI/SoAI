/* SoAI - Chat page agent service [frontend/assets/ts/pages/chat/controllers/chatpageagent/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { OnceGuard } from '@core/concurrency/Once.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';
import type { AgentCanonicalPlan } from '@core/chat/agentTypes.ts';
import { createAgentInputController, resolveAgentMode, type ChatStreamTerminalUpdate } from '@features/chat/public.ts';
import { reconcileExecutionState, resolveExecutionState, type ExecutionStateReconciliationDependencies } from '@pages/chat/controllers/chatpageagent/AgentExecutionStateController.ts';
import { AgentPostRenderMaintenanceController } from '@pages/chat/controllers/chatpageagent/AgentPostRenderMaintenanceController.ts';
import { AgentRenderHydrationController } from '@pages/chat/controllers/chatpageagent/AgentRenderHydrationController.ts';
import { AgentServiceEventHandlerController } from '@pages/chat/controllers/chatpageagent/AgentServiceEventHandlerController.ts';
import { AgentToolsLockSyncController } from '@pages/chat/controllers/chatpageagent/AgentToolsLockSyncController.ts';
import { handleAgentModeSelection } from '@pages/chat/controllers/chatpageagent/agentModeSelectionController.ts';
import { removeAgentModePopup, syncAgentModePopupForInput } from '@pages/chat/controllers/chatpageagent/agentModePopupController.ts';
import { openChatPageAgentPlanModal } from '@pages/chat/controllers/chatpageagent/agentPlanModalController.ts';
import { renderAgentTurnMessage } from '@pages/chat/controllers/chatpageagent/agentTurnMessageRenderer.ts';
import { executeCompaction } from '@pages/chat/controllers/chatpageagent/compactionController.ts';
import { handleAgentCompactionRegeneration } from '@pages/chat/controllers/chatpageagent/compactionRegenerationController.ts';
import type { ChatPageAgentHost, ChatPageAgentService } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { updateAgentUiForConversation } from '@pages/chat/controllers/chatpageagent/effects.ts';
import { handleRenderedConversationAgentRealtimeState, rehydrateCurrentConversationAgentRealtimeState } from '@pages/chat/controllers/chatpageagent/events.ts';
import { subscribeChatPageAgentRealtime, type ChatPageAgentRealtimeSubscriptions } from '@pages/chat/controllers/chatpageagent/realtimeSubscriptionsManager.ts';
import { createChatPageAgentState, type ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';
import { reconcileAgentActivityDurations } from '@pages/chat/controllers/page/durations/agentActivityDurationRegistrationDomain.ts';
class ChatPageAgentServiceImpl implements ChatPageAgentService {
    #host: ChatPageAgentHost;
    #state: ChatPageAgentState = createChatPageAgentState();
    #renderHydrationController: AgentRenderHydrationController;
    #toolsLockSyncController: AgentToolsLockSyncController;
    #postRenderMaintenanceController: AgentPostRenderMaintenanceController;
    #executionReconciliation: ExecutionStateReconciliationDependencies;
    readonly #initializeOnce = new OnceGuard();
    #disposed: boolean = false;
    #realtimeSubscriptions: ChatPageAgentRealtimeSubscriptions | null = null;
    constructor(host: ChatPageAgentHost) {
        this.#host = host;
        this.#renderHydrationController = new AgentRenderHydrationController({
            host,
            isDisposed: () => this.#disposed
        });
        this.#toolsLockSyncController = new AgentToolsLockSyncController({
            host,
            isRenderingActive: (conversationId) => this.#isRenderingActive(conversationId)
        });
        this.#postRenderMaintenanceController = new AgentPostRenderMaintenanceController({
            host,
            state: this.#state,
            isDisposed: () => this.#disposed,
            reconcileActivityDurations: () => reconcileAgentActivityDurations(this.#host)
        });
        this.#executionReconciliation = {
            host,
            state: this.#state,
            clearToolsLockSync: () => this.#toolsLockSyncController.clear(),
            updateUiForCurrentConversation: () => this.#updateUiForCurrentConversation(),
            syncToolsLockState: () => this.#syncToolsLockState()
        };
    }
    #renderAndUpdateUi = (): void => {
        if (this.#disposed) {
            return;
        }
        this.#tryRenderAgentTurnMessage();
        this.#syncToolsLockState();
        this.#updateUiForCurrentConversation();
    };
    initialize(): void {
        if (this.#disposed) {
            return;
        }
        this.#initializeOnce.run(() => {
            this.#state.eventHandler = AgentServiceEventHandlerController({
                host: this.#host,
                state: this.#state,
                isDisposed: () => this.#disposed,
                renderAndUpdateUi: this.#renderAndUpdateUi,
                updateUiForCurrentConversation: () => this.#updateUiForCurrentConversation(),
                syncConversationSidebarStatus: (conversationId) => this.#host.conversation.syncConversationSidebarStatus(conversationId),
                reconcileActivityDurations: () => reconcileAgentActivityDurations(this.#host)
            });
            this.#state.inputController = createAgentInputController({
                getChatInput: () => this.#host.rendering.getChatInput(),
                cycleMode: () => this.handleModeCycle()
            });
            this.#realtimeSubscriptions = subscribeChatPageAgentRealtime({
                host: this.#host,
                state: this.#state,
                isDisposed: () => this.#disposed,
                tryRenderAgentTurnMessage: () => this.#tryRenderAgentTurnMessage(),
                onToolLiveProjectionUpdated: () => reconcileAgentActivityDurations(this.#host)
            });
        });
        this.#updateUiForCurrentConversation();
    }
    async waitForPendingModeUpdate(): Promise<void> {
        const pendingModeUpdate = this.#state.pendingModeUpdate;
        if (!pendingModeUpdate) {
            return;
        }
        await pendingModeUpdate;
    }
    updateUiForCurrentConversation(): void {
        this.#updateUiForCurrentConversation();
    }

    #updateUiForCurrentConversation(): void {
        if (this.#disposed) {
            return;
        }
        updateAgentUiForConversation(this.#host, this.#state, this.#host.conversation.getCurrentConversation());
    }
    handleConversationRendered(): void {
        if (this.#disposed) {
            return;
        }
        this.initialize();
        const conversation = this.#host.conversation.getCurrentConversation();
        const conversationId = conversation ? conversation.id : null;
        if (this.#state.lastConversationId !== conversationId) {
            this.#renderHydrationController.clear();
        }
        handleRenderedConversationAgentRealtimeState({
            conversation,
            host: this.#host,
            state: this.#state,
            tryRenderAgentTurnMessage: () => this.#tryRenderAgentTurnMessage(),
            updateUiForConversation: (nextConversation) => updateAgentUiForConversation(this.#host, this.#state, nextConversation)
        });
        reconcileAgentActivityDurations(this.#host);
        if (conversationId !== null) {
            reconcileExecutionState(this.#executionReconciliation, conversationId);
        }
        this.#syncToolsLockState();
        this.#postRenderMaintenanceController.drainPendingToolLiveProjectionEvents();
    }
    #tryRenderAgentTurnMessage(): void {
        if (this.#disposed) {
            return;
        }
        renderAgentTurnMessage(this.#host, this.#state, {
            requestMessageHydration: (conversationId, requestKey) => this.#renderHydrationController.request(conversationId, requestKey)
        });
        reconcileAgentActivityDurations(this.#host);
    }

    handleKeyDown(event: KeyboardEvent): boolean {
        if (this.#disposed) {
            return false;
        }
        const inputController = this.#state.inputController;
        if (!inputController) {
            return false;
        }
        return inputController.handleKeyDown(event);
    }
    handleModeCycle(): void {
        this.#runModeSelection(null);
    }
    handleModeSelect(mode: AgentMode): void {
        this.#runModeSelection(mode);
    }
    #runModeSelection(targetMode: AgentMode | null): void {
        handleAgentModeSelection(
            this.#host,
            this.#state,
            {
                isDisposed: () => this.#disposed,
                initialize: () => this.initialize(),
                updateUiForCurrentConversation: () => this.#updateUiForCurrentConversation(),
                showModePopup: (mode) => syncAgentModePopupForInput(this.#state.agentModePopup, this.#disposed ? null : this.#host.rendering.getChatInput(), mode)
            },
            targetMode
        );
    }
    handleCompact(): void {
        if (this.#disposed) {
            return;
        }
        this.initialize();
        executeCompaction(
            this.#host,
            this.#state,
            () => this.#tryRenderAgentTurnMessage(),
            () => this.#updateUiForCurrentConversation()
        );
    }

    async handleRegenerateCompaction(assistantTurnAtMs: number): Promise<void> {
        if (this.#disposed) {
            return;
        }
        await handleAgentCompactionRegeneration(this.#host, this.#state, assistantTurnAtMs, {
            isDisposed: () => this.#disposed,
            initialize: () => this.initialize(),
            renderAgentTurnMessage: () => this.#tryRenderAgentTurnMessage(),
            updateUiForCurrentConversation: () => this.#updateUiForCurrentConversation()
        });
    }
    handleStreamTerminalized(update: ChatStreamTerminalUpdate): void {
        if (this.#disposed) {
            return;
        }
        const conversationId = update.conversationId;
        if (this.#host.conversation.getCurrentConversationId() === conversationId) {
            this.initialize();
            rehydrateCurrentConversationAgentRealtimeState({
                host: this.#host,
                state: this.#state,
                tryRenderAgentTurnMessage: () => this.#tryRenderAgentTurnMessage(),
                updateUiForConversation: (conversation) => updateAgentUiForConversation(this.#host, this.#state, conversation)
            });
        }
        reconcileExecutionState(this.#executionReconciliation, conversationId);
    }
    handleToggleTodoPanel(): void {
        if (this.#disposed) {
            return;
        }
        this.#state.todoPanelCollapsed = !this.#state.todoPanelCollapsed;
        this.#updateUiForCurrentConversation();
    }
    handleTogglePlanBar(): void {
        if (this.#disposed) {
            return;
        }
        this.#host.planBar.setVisible(!this.#host.planBar.isVisible());
        this.#updateUiForCurrentConversation();
    }
    handleViewAgentPlan(): void {
        openChatPageAgentPlanModal(this.#host, this.#state, () => this.#disposed);
    }
    getCanonicalPlan(): AgentCanonicalPlan | null {
        const markdown = this.#state.canonicalPlanMarkdown;
        if (typeof markdown !== 'string' || !markdown.trim()) {
            return null;
        }
        return {
            markdown,
            title: this.#state.canonicalPlanTitle,
            revision: this.#state.canonicalPlanRevision > 0 ? this.#state.canonicalPlanRevision : null
        };
    }
    resolveModeForConversation(conversationId: string): AgentMode {
        const conversation = this.#host.conversation.getConversationById(conversationId);
        return resolveAgentMode(conversation);
    }
    resolveRunningTurnId(conversationId: string): string | null {
        if (this.#disposed) {
            return null;
        }
        return resolveExecutionState(this.#executionReconciliation, conversationId, false).runningTurnId;
    }
    isRenderingActive(conversationId: string): boolean {
        return this.#isRenderingActive(conversationId);
    }

    #isRenderingActive(conversationId: string): boolean {
        if (this.#disposed) {
            return false;
        }
        return resolveExecutionState(this.#executionReconciliation, conversationId, false).isRunning;
    }

    #syncToolsLockState(): void {
        this.#toolsLockSyncController.sync();
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        removeAgentModePopup(this.#state.agentModePopup);
        this.#initializeOnce.dispose();
        this.#state.eventHandler?.dispose();
        this.#state.eventHandler = null;
        this.#state.inputController = null;
        this.#state.pendingModeUpdate = null;
        this.#state.lastConversationId = null;
        this.#renderHydrationController.clear();
        this.#toolsLockSyncController.clear();
        if (this.#realtimeSubscriptions) {
            this.#realtimeSubscriptions.webSocketConnected();
            this.#realtimeSubscriptions.toolLiveUpdated();
            this.#realtimeSubscriptions = null;
        }
    }
}
const createChatPageAgentService = (host: ChatPageAgentHost): ChatPageAgentService => new ChatPageAgentServiceImpl(host);
export { createChatPageAgentService };
