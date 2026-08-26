/* SoAI - Agent event turn application gate [frontend/assets/ts/features/chat/agent/agentEventTurnGate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentTurnState } from '@core/chat/agentTypes.ts';
import type { AgentTurnStateMap } from '@features/chat/agent/agentTurnStateManager.ts';

interface AgentTurnEventPayload {
    convId: string;
    turnId: string;
}

interface AgentParentTurnEventPayload {
    convId: string;
    parentTurnId: string;
}

interface AgentEventConversationScope {
    getCurrentConversationId(): string | null;
}

interface ApplyAgentTurnEventOptions {
    turnStateMap: AgentTurnStateMap;
    payload: AgentTurnEventPayload;
    scope: AgentEventConversationScope;
    apply(turnState: AgentTurnState): boolean;
    render(convId: string): void;
}

interface ApplyAgentParentTurnEventOptions {
    turnStateMap: AgentTurnStateMap;
    payload: AgentParentTurnEventPayload;
    scope: AgentEventConversationScope;
    apply(turnState: AgentTurnState): boolean;
    render(convId: string): void;
}

const isCurrentAgentEventConversation = (scope: AgentEventConversationScope, convId: string): boolean => scope.getCurrentConversationId() === convId;

const resolveMatchingTurnState = (turnStateMap: AgentTurnStateMap, payload: AgentTurnEventPayload): AgentTurnState | null => {
    const turnState = turnStateMap.get(payload.convId);
    if (!turnState || turnState.turnId !== payload.turnId) {
        return null;
    }
    return turnState;
};

const resolveMatchingParentTurnState = (turnStateMap: AgentTurnStateMap, payload: AgentParentTurnEventPayload): AgentTurnState | null => {
    const turnState = turnStateMap.get(payload.convId);
    if (!turnState || turnState.turnId !== payload.parentTurnId) {
        return null;
    }
    return turnState;
};

const applyAgentTurnEvent = (options: ApplyAgentTurnEventOptions): void => {
    const turnState = resolveMatchingTurnState(options.turnStateMap, options.payload);
    if (!turnState) {
        return;
    }
    const applied = options.apply(turnState);
    if (applied && isCurrentAgentEventConversation(options.scope, options.payload.convId)) {
        options.render(options.payload.convId);
    }
};

const applyAgentParentTurnEvent = (options: ApplyAgentParentTurnEventOptions): void => {
    const turnState = resolveMatchingParentTurnState(options.turnStateMap, options.payload);
    if (!turnState) {
        return;
    }
    const applied = options.apply(turnState);
    if (applied && isCurrentAgentEventConversation(options.scope, options.payload.convId)) {
        options.render(options.payload.convId);
    }
};

export { applyAgentParentTurnEvent, applyAgentTurnEvent, isCurrentAgentEventConversation, resolveMatchingTurnState };
export type { AgentEventConversationScope, AgentParentTurnEventPayload, AgentTurnEventPayload };
