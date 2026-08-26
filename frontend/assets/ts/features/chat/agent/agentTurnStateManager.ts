/* SoAI - Chat feature agent turn state manager [frontend/assets/ts/features/chat/agent/agentTurnStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAgentMode } from '@features/chat/agent/agentModeState.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';
import type { AgentIteration, AgentPlanStep, AgentTurnState } from '@core/chat/agentTypes.ts';
type AgentTurnStateMap = Map<string, AgentTurnState>;
const createAgentTurnStateMap = (): AgentTurnStateMap => new Map<string, AgentTurnState>();

const getOrCreateTurnState = (stateMap: AgentTurnStateMap, convId: string, turnId: string, mode: string, maxIterations: number, turnStartedAtMs: number): AgentTurnState => {
    const existing = stateMap.get(convId);
    if (existing && existing.turnId === turnId) {
        return existing;
    }
    const resolvedMode: AgentMode = isAgentMode(mode) ? mode : 'chat';
    const turnState: AgentTurnState = {
        turnId: turnId,
        convId: convId,
        mode: resolvedMode,
        maxIterations: maxIterations,
        messageIndex: null,
        turnStartedAtMs: turnStartedAtMs,
        iterations: new Map<number, AgentIteration>(),
        subagents: new Map(),
        subagentDisplayCounter: 0,
        lastSequence: 0,
        status: 'running',
        todo: [],
        todoExplanation: null
    };
    stateMap.set(convId, turnState);
    return turnState;
};

const isSequenceStale = (turnState: AgentTurnState, sequence: number): boolean => sequence <= turnState.lastSequence;

const advanceSequence = (turnState: AgentTurnState, sequence: number): void => {
    if (sequence > turnState.lastSequence) {
        turnState.lastSequence = sequence;
    }
};
const applyTurnMessageIndex = (turnState: AgentTurnState, messageIndex: number): void => {
    if (!Number.isInteger(messageIndex) || messageIndex < 0) {
        throw new Error('Agent turn messageIndex must be a non-negative integer');
    }
    if (turnState.messageIndex !== null && turnState.messageIndex !== messageIndex) {
        throw new Error('Agent turn received conflicting messageIndex values');
    }
    turnState.messageIndex = messageIndex;
};
const applyTurnCompleted = (turnState: AgentTurnState, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    turnState.status = 'completed';
    for (const iteration of turnState.iterations.values()) {
        if (iteration.status === 'running') {
            iteration.status = 'completed';
        }
    }
    return true;
};
const applyTurnError = (turnState: AgentTurnState, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    turnState.status = 'error';
    return true;
};
const applyTodoUpdated = (turnState: AgentTurnState, todo: AgentPlanStep[], explanation: string | null, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    turnState.todo = todo.map((entry) => ({
        step: entry.step,
        status: entry.status
    }));
    turnState.todoExplanation = explanation;
    return true;
};
const getTurnStateForConversation = (stateMap: AgentTurnStateMap, convId: string): AgentTurnState | null => {
    const turnState = stateMap.get(convId);
    return turnState === undefined ? null : turnState;
};

export { createAgentTurnStateMap, getOrCreateTurnState };
export { advanceSequence, applyTurnCompleted, applyTurnError, applyTodoUpdated, applyTurnMessageIndex, getTurnStateForConversation, isSequenceStale };
export type { AgentTurnStateMap };
