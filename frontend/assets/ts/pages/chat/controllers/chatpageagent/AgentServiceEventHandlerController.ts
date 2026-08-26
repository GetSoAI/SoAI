/* SoAI - Chat page agent service event handler controller [frontend/assets/ts/pages/chat/controllers/chatpageagent/AgentServiceEventHandlerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { syncAgentModePopupForInput } from '@pages/chat/controllers/chatpageagent/agentModePopupController.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import { createChatPageAgentEventHandler } from '@pages/chat/controllers/chatpageagent/eventHandlerWiring.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

interface AgentServiceEventHandlerDependencies {
    host: ChatPageAgentHost;
    state: ChatPageAgentState;
    isDisposed(): boolean;
    renderAndUpdateUi(): void;
    updateUiForCurrentConversation(): void;
    syncConversationSidebarStatus(conversationId: string): void;
    reconcileActivityDurations(): void;
}

const AgentServiceEventHandlerController = (dependencies: AgentServiceEventHandlerDependencies): NonNullable<ChatPageAgentState['eventHandler']> => {
    return createChatPageAgentEventHandler(dependencies.host, dependencies.state, {
        onRenderNeeded: dependencies.renderAndUpdateUi,
        onUiUpdateNeeded: () => {
            if (dependencies.isDisposed()) {
                return;
            }
            const conversationId = dependencies.host.conversation.getCurrentConversationId();
            if (conversationId) {
                dependencies.host.interaction.syncToolsEnabledParameterFromConversation(conversationId);
            }
            dependencies.updateUiForCurrentConversation();
        },
        onExecutionStateChanged: (conversationId) => {
            if (dependencies.isDisposed()) {
                return;
            }
            dependencies.syncConversationSidebarStatus(conversationId);
        },
        onToolCallDurationUpdated: (_toolCallId, _toolName, _startedAtMs, _durationMs) => {
            if (dependencies.isDisposed()) {
                return;
            }
            dependencies.reconcileActivityDurations();
        },
        onModeChanged: (conversationId, newMode) => {
            if (dependencies.isDisposed()) {
                return;
            }
            dependencies.host.interaction.syncToolsEnabledParameterFromConversation(conversationId);
            dependencies.host.interaction.handleCurrentConversationToolsLockStateChange();
            dependencies.updateUiForCurrentConversation();
            dependencies.host.interaction.updateInputState();
            dependencies.host.interaction.updateParameterUI();
            syncAgentModePopupForInput(dependencies.state.agentModePopup, dependencies.host.rendering.getChatInput(), newMode);
        },
        getNowMs: serverEpochMs
    });
};

export { AgentServiceEventHandlerController };
