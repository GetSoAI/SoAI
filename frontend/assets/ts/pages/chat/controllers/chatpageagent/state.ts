/* SoAI - Chat page agent state [frontend/assets/ts/pages/chat/controllers/chatpageagent/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import type { ToolCallLiveUpdatedEvent } from '@core/realtime/eventcontracts/toolLiveContracts.ts';
import type { AgentEventHandlerResult, AgentInputController } from '@features/chat/public.ts';
import { createAgentModePopupState, type AgentModePopupState } from '@pages/chat/controllers/chatpageagent/agentModePopupController.ts';

interface PendingToolLiveProjectionEvent {
    value: ToolCallLiveUpdatedEvent;
    receivedAtMs: number;
}

interface ChatPageAgentState {
    eventHandler: AgentEventHandlerResult | null;
    inputController: AgentInputController | null;
    pendingModeUpdate: Promise<void> | null;
    manualCompactionStartingConversationId: string | null;
    todoPanelCollapsed: boolean;
    canonicalTodo: AgentPlanStep[];
    canonicalTodoExplanation: string | null;
    canonicalTodoRevision: number;
    canonicalPlanRevision: number;
    canonicalPlanTitle: string | null;
    canonicalPlanMarkdown: string | null;
    planModalOpen: boolean;
    planHasUnseenUpdate: boolean;
    lastConversationId: string | null;
    cachedChatInput: HTMLTextAreaElement | null;
    cachedTodoPanelContainer: HTMLElement | null;
    pendingToolLiveProjectionEvents: Map<string, PendingToolLiveProjectionEvent>;
    lastAppliedAgentMode: AgentMode | null;
    lastAppliedAgentModeInput: HTMLTextAreaElement | null;
    agentModePopup: AgentModePopupState;
}

const createChatPageAgentState = (): ChatPageAgentState => {
    return {
        eventHandler: null,
        inputController: null,
        pendingModeUpdate: null,
        manualCompactionStartingConversationId: null,
        todoPanelCollapsed: true,
        canonicalTodo: [],
        canonicalTodoExplanation: null,
        canonicalTodoRevision: 0,
        canonicalPlanRevision: 0,
        canonicalPlanTitle: null,
        canonicalPlanMarkdown: null,
        planModalOpen: false,
        planHasUnseenUpdate: false,
        lastConversationId: null,
        cachedChatInput: null,
        cachedTodoPanelContainer: null,
        pendingToolLiveProjectionEvents: new Map<string, PendingToolLiveProjectionEvent>(),
        lastAppliedAgentMode: null,
        lastAppliedAgentModeInput: null,
        agentModePopup: createAgentModePopupState()
    };
};

export { createChatPageAgentState };
export type { ChatPageAgentState, PendingToolLiveProjectionEvent };
