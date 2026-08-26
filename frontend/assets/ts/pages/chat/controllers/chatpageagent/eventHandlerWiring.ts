/* SoAI - Chat page event handler wiring [frontend/assets/ts/pages/chat/controllers/chatpageagent/eventHandlerWiring.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import { createAgentEventHandler, handleExternalModeChange, type AgentEventHandlerResult } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { applyConversationPlanRealtimeState, applyConversationTodoRealtimeState } from '@pages/chat/controllers/chatpageagent/events.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

interface ChatPageAgentEventHandlerWiringEffects {
    onRenderNeeded(): void;
    onUiUpdateNeeded(): void;
    onExecutionStateChanged(conversationId: string): void;
    onToolCallDurationUpdated(toolCallId: string, toolName: string, startedAtMs: number, durationMs: number): void;
    onModeChanged(conversationId: string, mode: AgentMode): void;
    getNowMs(): number;
}

const isConversationCurrent = (host: ChatPageAgentHost, conversationId: string): boolean => {
    return host.conversation.getCurrentConversationId() === conversationId;
};

const createChatPageAgentEventHandler = (host: ChatPageAgentHost, state: ChatPageAgentState, effects: ChatPageAgentEventHandlerWiringEffects): AgentEventHandlerResult => {
    return createAgentEventHandler({
        getCurrentConversationId: () => host.conversation.getCurrentConversationId(),
        onIterationRenderNeeded: (_conversationId, _iterationIndex) => {
            effects.onRenderNeeded();
        },
        onToolCallRenderNeeded: (_conversationId, _iterationIndex) => {
            effects.onRenderNeeded();
        },
        onToolCallDurationUpdated: (_conversationId, toolCallId, toolName, startedAtMs, durationMs) => {
            effects.onToolCallDurationUpdated(toolCallId, toolName, startedAtMs, durationMs);
        },
        onTurnRunningStateChanged: (conversationId) => {
            effects.onExecutionStateChanged(conversationId);
        },
        onTurnCompleted: (_conversationId) => {
            effects.onRenderNeeded();
        },
        onTurnError: (_conversationId, _message) => {
            effects.onRenderNeeded();
        },
        onTodoUpdated: (conversationId, todo, explanation, revision) => {
            if (!isConversationCurrent(host, conversationId)) {
                return;
            }
            if (!applyConversationTodoRealtimeState(state, todo, explanation, revision)) {
                return;
            }
            effects.onUiUpdateNeeded();
        },
        onPlanUpdated: (conversationId, title, markdown, revision) => {
            if (!isConversationCurrent(host, conversationId)) {
                return;
            }
            if (!applyConversationPlanRealtimeState(state, title, markdown, revision)) {
                return;
            }
            state.planHasUnseenUpdate = state.planModalOpen ? false : true;
            effects.onUiUpdateNeeded();
        },
        onModeChanged: (conversationId, mode) => {
            handleExternalModeChange(
                {
                    getCurrentConversation: () => host.conversation.getCurrentConversation(),
                    onModeChanged: (updatedConversationId: string, newMode: AgentMode) => effects.onModeChanged(updatedConversationId, newMode)
                },
                conversationId,
                mode
            );
        },
        onSubagentRenderNeeded: (_conversationId) => {
            effects.onRenderNeeded();
        },
        getNowMs: () => effects.getNowMs()
    });
};

export { createChatPageAgentEventHandler };
export type { ChatPageAgentEventHandlerWiringEffects };
