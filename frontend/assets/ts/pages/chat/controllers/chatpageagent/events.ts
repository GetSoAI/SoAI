/* SoAI - Chat page agent events [frontend/assets/ts/pages/chat/controllers/chatpageagent/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { AgentPlanStep } from '@core/chat/agentTypes.ts';
import { agentCheckpointTargetsConversationMessageRange, rehydrateTurnStateFromCheckpoint, requestAgentCheckpointSnapshot, requestAgentPlanSnapshot, requestAgentTodoSnapshot, type Conversation } from '@features/chat/public.ts';
import { removeAgentModePopup } from '@pages/chat/controllers/chatpageagent/agentModePopupController.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { AgentExecutionStateController, type AgentTurnStateMarker } from '@pages/chat/controllers/chatpageagent/AgentExecutionStateController.ts';
import { hasPersistedAuthoritativeAssistantTimeline } from '@pages/chat/controllers/chatpageagent/persistedAssistantTimelineController.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';
import { retainPendingToolCallLiveProjectionEventsForConversation } from '@pages/chat/controllers/chatpageagent/toolLiveProjectionEventsController.ts';

const cloneTodo = (todo: AgentPlanStep[]): AgentPlanStep[] => {
    return todo.map((entry) => ({
        step: entry.step,
        status: entry.status
    }));
};

const resetConversationAgentRealtimeState = (state: ChatPageAgentState): void => {
    state.todoPanelCollapsed = true;
    state.canonicalTodo = [];
    state.canonicalTodoExplanation = null;
    state.canonicalTodoRevision = 0;
    state.canonicalPlanRevision = 0;
    state.canonicalPlanTitle = null;
    state.canonicalPlanMarkdown = null;
    state.planModalOpen = false;
    state.planHasUnseenUpdate = false;
    state.lastAppliedAgentMode = null;
    state.lastAppliedAgentModeInput = null;
    removeAgentModePopup(state.agentModePopup);
};

const applyConversationTodoRealtimeState = (state: ChatPageAgentState, todo: AgentPlanStep[], explanation: string | null, revision: number): boolean => {
    if (revision < state.canonicalTodoRevision) {
        return false;
    }
    state.canonicalTodo = cloneTodo(todo);
    state.canonicalTodoExplanation = explanation;
    state.canonicalTodoRevision = revision;
    return true;
};

const applyConversationPlanRealtimeState = (state: ChatPageAgentState, title: string | null, markdown: string | null, revision: number): boolean => {
    if (revision < state.canonicalPlanRevision) {
        return false;
    }
    state.canonicalPlanRevision = revision;
    state.canonicalPlanTitle = title;
    state.canonicalPlanMarkdown = markdown;
    return true;
};

const shouldPreferPersistedAssistantTimeline = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation): boolean => {
    const executionState = AgentExecutionStateController.resolveAgentConversationExecutionState({
        eventHandler: state.eventHandler,
        conversation: host.conversation.getConversationById(conversation.id) ?? conversation,
        conversationId: conversation.id,
        clearStaleTurnState: false
    });
    if (executionState.hasTurnState) {
        return !executionState.isRunning && executionState.hasAuthoritativeAssistantForTurn;
    }
    const currentConversation = host.conversation.getConversationById(conversation.id);
    return hasPersistedAuthoritativeAssistantTimeline(currentConversation ?? conversation);
};

const clearConversationTurnStateForPersistedAssistantTimeline = (host: ChatPageAgentHost, state: ChatPageAgentState, conversation: Conversation): boolean => {
    if (!shouldPreferPersistedAssistantTimeline(host, state, conversation)) {
        return false;
    }
    return AgentExecutionStateController.resolveAgentConversationExecutionState({
        eventHandler: state.eventHandler,
        conversation: host.conversation.getConversationById(conversation.id) ?? conversation,
        conversationId: conversation.id,
        clearStaleTurnState: true
    }).clearedStaleTurnState;
};

const syncSidebarStatusAfterTurnStateClear = (host: ChatPageAgentHost, conversationId: string, cleared: boolean): void => {
    if (cleared) {
        host.conversation.syncConversationSidebarStatus(conversationId);
    }
};

const markersMatch = (left: AgentTurnStateMarker | null, right: AgentTurnStateMarker | null): boolean => {
    if (left === null || right === null) {
        return left === right;
    }
    return left.turnId === right.turnId && left.status === right.status && left.sequence === right.sequence && left.startedAtMs === right.startedAtMs;
};

const isHydrationTurnMarkerCurrent = (state: ChatPageAgentState, conversationId: string, marker: AgentTurnStateMarker | null): boolean => {
    return markersMatch(AgentExecutionStateController.captureAgentTurnStateMarker(state.eventHandler, conversationId), marker);
};

const queueConversationAgentRealtimeHydration = (inputArguments: { conversation: Conversation; host: ChatPageAgentHost; state: ChatPageAgentState; tryRenderAgentTurnMessage(): void; updateUiForConversation(conversation: Conversation | null): void }): void => {
    const { conversation, host, state, tryRenderAgentTurnMessage, updateUiForConversation } = inputArguments;
    const activation = host.conversation.captureConversationActivationSnapshot();
    const isCurrent = (): boolean => host.conversation.isConversationActivationSnapshotCurrent(activation, conversation.id);
    const runHydrationTask = (label: string, task: Promise<void>): void => {
        void task.catch((error): void => {
            host.workflow.logWarning(label, ensureError(error));
        });
    };
    syncSidebarStatusAfterTurnStateClear(host, conversation.id, clearConversationTurnStateForPersistedAssistantTimeline(host, state, conversation));

    const hydrateCheckpoint = async (): Promise<void> => {
        const eventHandler = state.eventHandler;
        if (!eventHandler) {
            return;
        }
        if (!isCurrent()) {
            return;
        }
        const turnMarker = AgentExecutionStateController.captureAgentTurnStateMarker(eventHandler, conversation.id);
        const checkpoint = await requestAgentCheckpointSnapshot(conversation.id);
        if (!isCurrent()) {
            return;
        }
        if (state.eventHandler !== eventHandler) {
            return;
        }
        if (!isHydrationTurnMarkerCurrent(state, conversation.id, turnMarker)) {
            return;
        }
        if (!checkpoint) {
            syncSidebarStatusAfterTurnStateClear(host, conversation.id, AgentExecutionStateController.clearAgentTurnStateForMarker(eventHandler, conversation.id, turnMarker));
            if (!shouldPreferPersistedAssistantTimeline(host, state, conversation)) {
                tryRenderAgentTurnMessage();
            }
            updateUiForConversation(conversation);
            return;
        }
        if (!agentCheckpointTargetsConversationMessageRange(conversation, checkpoint)) {
            syncSidebarStatusAfterTurnStateClear(host, conversation.id, AgentExecutionStateController.clearAgentTurnStateForMarker(eventHandler, conversation.id, turnMarker));
            updateUiForConversation(conversation);
            return;
        }
        rehydrateTurnStateFromCheckpoint(eventHandler.turnStateMap, checkpoint);
        if (shouldPreferPersistedAssistantTimeline(host, state, conversation)) {
            syncSidebarStatusAfterTurnStateClear(host, conversation.id, clearConversationTurnStateForPersistedAssistantTimeline(host, state, conversation));
        } else {
            tryRenderAgentTurnMessage();
        }
        updateUiForConversation(conversation);
    };

    const hydrateTodo = async (): Promise<void> => {
        if (!isCurrent()) {
            return;
        }
        const todoState = await requestAgentTodoSnapshot(conversation.id);
        if (!isCurrent()) {
            return;
        }
        if (!applyConversationTodoRealtimeState(state, todoState.todo, todoState.explanation, todoState.revision)) {
            return;
        }
        updateUiForConversation(conversation);
    };

    const hydratePlan = async (): Promise<void> => {
        if (!isCurrent()) {
            return;
        }
        const planState = await requestAgentPlanSnapshot(conversation.id);
        if (!isCurrent()) {
            return;
        }
        if (!applyConversationPlanRealtimeState(state, planState.title, planState.markdown, planState.revision)) {
            return;
        }
        updateUiForConversation(conversation);
    };

    runHydrationTask('Failed to rehydrate agent checkpoint', hydrateCheckpoint());
    runHydrationTask('Failed to hydrate agent todo', hydrateTodo());
    runHydrationTask('Failed to hydrate agent plan', hydratePlan());
};

const handleRenderedConversationAgentRealtimeState = (inputArguments: { conversation: Conversation | null; host: ChatPageAgentHost; state: ChatPageAgentState; tryRenderAgentTurnMessage(): void; updateUiForConversation(conversation: Conversation | null): void }): void => {
    const { conversation, host, state, tryRenderAgentTurnMessage, updateUiForConversation } = inputArguments;
    const conversationId = conversation ? conversation.id : null;
    if (state.lastConversationId === conversationId) {
        return;
    }
    state.lastConversationId = conversationId;
    resetConversationAgentRealtimeState(state);
    retainPendingToolCallLiveProjectionEventsForConversation(state.pendingToolLiveProjectionEvents, conversationId);
    if (conversation) {
        syncSidebarStatusAfterTurnStateClear(host, conversation.id, clearConversationTurnStateForPersistedAssistantTimeline(host, state, conversation));
    }
    tryRenderAgentTurnMessage();
    updateUiForConversation(conversation);
    if (!conversation) {
        return;
    }
    queueConversationAgentRealtimeHydration({
        conversation,
        host,
        state,
        tryRenderAgentTurnMessage,
        updateUiForConversation
    });
};

const rehydrateCurrentConversationAgentRealtimeState = (inputArguments: { host: ChatPageAgentHost; state: ChatPageAgentState; tryRenderAgentTurnMessage(): void; updateUiForConversation(conversation: Conversation | null): void }): void => {
    const conversation = inputArguments.host.conversation.getCurrentConversation();
    if (!conversation) {
        return;
    }
    queueConversationAgentRealtimeHydration({
        conversation,
        host: inputArguments.host,
        state: inputArguments.state,
        tryRenderAgentTurnMessage: inputArguments.tryRenderAgentTurnMessage,
        updateUiForConversation: inputArguments.updateUiForConversation
    });
};

export { applyConversationPlanRealtimeState, applyConversationTodoRealtimeState, handleRenderedConversationAgentRealtimeState, rehydrateCurrentConversationAgentRealtimeState };
