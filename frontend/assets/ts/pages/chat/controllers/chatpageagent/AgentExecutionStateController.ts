/* SoAI - Chat page agent execution state reconciliation [frontend/assets/ts/pages/chat/controllers/chatpageagent/AgentExecutionStateController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { canResolveAssistantMessageByLogicalIndex, getTurnStateForConversation, hasTerminalAssistantState, isChatMessage, resolveAssistantMessageByLogicalIndex, type AgentEventHandlerResult, type ChatMessage, type Conversation } from '@features/chat/public.ts';
import type { ChatPageAgentHost } from '@pages/chat/controllers/chatpageagent/contracts.ts';
import { isPersistedAuthoritativeAssistantMessage, resolvePersistedAuthoritativeAssistantMessage } from '@pages/chat/controllers/chatpageagent/persistedAssistantTimelineController.ts';
import type { ChatPageAgentState } from '@pages/chat/controllers/chatpageagent/state.ts';

interface AgentConversationExecutionState {
    isRunning: boolean;
    runningTurnId: string | null;
    clearedStaleTurnState: boolean;
    hasTurnState: boolean;
    hasAuthoritativeAssistantForTurn: boolean;
}

interface AgentExecutionStateArguments {
    eventHandler: AgentEventHandlerResult | null;
    conversation: Conversation | null;
    conversationId: string;
    clearStaleTurnState: boolean;
}

interface AgentTurnStateMarker {
    turnId: string;
    status: string;
    sequence: number;
    startedAtMs: number;
}

interface ExecutionStateReconciliationDependencies {
    host: ChatPageAgentHost;
    state: ChatPageAgentState;
    clearToolsLockSync(): void;
    updateUiForCurrentConversation(): void;
    syncToolsLockState(): void;
}

const missingAgentExecutionState = (): AgentConversationExecutionState => ({
    isRunning: false,
    runningTurnId: null,
    clearedStaleTurnState: false,
    hasTurnState: false,
    hasAuthoritativeAssistantForTurn: false
});

const captureTurnMarker = (turnState: NonNullable<ReturnType<typeof getTurnStateForConversation>>): AgentTurnStateMarker => ({
    turnId: turnState.turnId,
    status: turnState.status,
    sequence: turnState.lastSequence,
    startedAtMs: turnState.turnStartedAtMs
});

const captureAgentTurnStateMarker = (eventHandler: AgentEventHandlerResult | null, conversationId: string): AgentTurnStateMarker | null => {
    if (eventHandler === null) {
        return null;
    }
    const turnState = getTurnStateForConversation(eventHandler.turnStateMap, conversationId);
    return turnState === null ? null : captureTurnMarker(turnState);
};

const isTurnMarkerCurrent = (eventHandler: AgentEventHandlerResult, conversationId: string, marker: AgentTurnStateMarker): boolean => {
    const current = getTurnStateForConversation(eventHandler.turnStateMap, conversationId);
    return current !== null && current.turnId === marker.turnId && current.status === marker.status && current.lastSequence === marker.sequence && current.turnStartedAtMs === marker.startedAtMs;
};

const resolveMessageTimestamp = (message: ChatMessage): number | null => {
    const value = message.assistantTurnAtMs ?? message.timestamp;
    return typeof value === 'number' && Number.isFinite(value) ? value : null;
};

const resolveLatestUserMessageIndex = (conversation: Conversation): number => {
    for (let index = conversation.messages.length - 1; index >= 0; index -= 1) {
        const message = conversation.messages[index];
        if (isChatMessage(message) && message.role === 'user') {
            return index;
        }
    }
    return -1;
};

const isMessageAfterLatestUserMessage = (conversation: Conversation, message: ChatMessage): boolean => {
    const messageIndex = conversation.messages.indexOf(message);
    if (messageIndex < 0) {
        return false;
    }
    const latestUserIndex = resolveLatestUserMessageIndex(conversation);
    return latestUserIndex >= 0 && messageIndex > latestUserIndex;
};

const resolveAssistantMessageForTurn = (conversation: Conversation, turnState: NonNullable<ReturnType<typeof getTurnStateForConversation>>): ChatMessage | null => {
    if (turnState.messageIndex !== null) {
        if (!canResolveAssistantMessageByLogicalIndex(conversation.messages, turnState.messageIndex)) {
            return null;
        }
        return resolveAssistantMessageByLogicalIndex(conversation.messages, turnState.messageIndex);
    }
    const candidate = resolvePersistedAuthoritativeAssistantMessage(conversation);
    if (candidate === null) {
        return null;
    }
    if (isMessageAfterLatestUserMessage(conversation, candidate)) {
        return candidate;
    }
    const timestamp = resolveMessageTimestamp(candidate);
    if (timestamp === null || timestamp < turnState.turnStartedAtMs) {
        return null;
    }
    return candidate;
};

const isTerminalAuthoritativeAssistantForTurn = (message: ChatMessage | null): boolean => {
    return message !== null && isPersistedAuthoritativeAssistantMessage(message) && hasTerminalAssistantState(message);
};

const isAuthoritativeAssistantForTurn = (message: ChatMessage | null): boolean => {
    return message !== null && isPersistedAuthoritativeAssistantMessage(message);
};

const clearAgentTurnStateForMarker = (eventHandler: AgentEventHandlerResult, conversationId: string, marker: AgentTurnStateMarker | null): boolean => {
    if (marker === null) {
        return false;
    }
    if (!isTurnMarkerCurrent(eventHandler, conversationId, marker)) {
        return false;
    }
    return eventHandler.clearConversationTurnState(conversationId);
};

const resolveAgentConversationExecutionState = (inputArguments: AgentExecutionStateArguments): AgentConversationExecutionState => {
    const eventHandler = inputArguments.eventHandler;
    if (eventHandler === null || inputArguments.conversation === null) {
        return missingAgentExecutionState();
    }
    const turnState = getTurnStateForConversation(eventHandler.turnStateMap, inputArguments.conversationId);
    if (turnState === null) {
        return missingAgentExecutionState();
    }
    const marker = captureTurnMarker(turnState);
    const assistantMessage = resolveAssistantMessageForTurn(inputArguments.conversation, turnState);
    const hasAuthoritativeAssistantForTurn = isAuthoritativeAssistantForTurn(assistantMessage);
    const shouldClearRunningTurn = turnState.status === 'running' && isTerminalAuthoritativeAssistantForTurn(assistantMessage);
    const shouldClearSettledTurn = turnState.status !== 'running' && hasAuthoritativeAssistantForTurn;
    const shouldClear = shouldClearRunningTurn || shouldClearSettledTurn;
    const cleared = shouldClear && inputArguments.clearStaleTurnState ? clearAgentTurnStateForMarker(eventHandler, inputArguments.conversationId, marker) : false;
    if (turnState.status === 'running' && !shouldClearRunningTurn) {
        return {
            isRunning: true,
            runningTurnId: turnState.turnId,
            clearedStaleTurnState: false,
            hasTurnState: true,
            hasAuthoritativeAssistantForTurn
        };
    }
    return {
        isRunning: false,
        runningTurnId: null,
        clearedStaleTurnState: cleared,
        hasTurnState: true,
        hasAuthoritativeAssistantForTurn
    };
};

const resolveExecutionState = (dependencies: ExecutionStateReconciliationDependencies, conversationId: string, clearStaleTurnState: boolean): AgentConversationExecutionState => {
    const resolved = resolveAgentConversationExecutionState({
        eventHandler: dependencies.state.eventHandler,
        conversation: dependencies.host.conversation.getConversationById(conversationId),
        conversationId,
        clearStaleTurnState
    });
    if (resolved.clearedStaleTurnState) {
        dependencies.clearToolsLockSync();
    }
    return resolved;
};

const reconcileExecutionState = (dependencies: ExecutionStateReconciliationDependencies, conversationId: string): AgentConversationExecutionState => {
    const resolved = resolveExecutionState(dependencies, conversationId, true);
    if (resolved.clearedStaleTurnState) {
        dependencies.host.conversation.syncConversationSidebarStatus(conversationId);
        if (dependencies.host.conversation.getCurrentConversationId() === conversationId) {
            dependencies.updateUiForCurrentConversation();
            dependencies.syncToolsLockState();
        }
    }
    return resolved;
};

const AgentExecutionStateController = Object.freeze({
    captureAgentTurnStateMarker,
    clearAgentTurnStateForMarker,
    reconcileExecutionState,
    resolveExecutionState,
    resolveAgentConversationExecutionState
});

export { AgentExecutionStateController, reconcileExecutionState, resolveExecutionState };
export type { AgentConversationExecutionState, AgentTurnStateMarker, ExecutionStateReconciliationDependencies };
