/* SoAI - Chat feature agent iteration state manager [frontend/assets/ts/features/chat/agent/agentIterationStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { advanceSequence, isSequenceStale } from '@features/chat/agent/agentTurnStateManager.ts';
import type { AgentSubagentState } from '@core/chat/agentSubagentTypes.ts';
import { buildParentToolCallResultPayload } from '@features/chat/agent/agentSubagentToolResult.ts';
import type { AgentIteration, AgentIterationToolCall, AgentToolCallStatus, AgentTurnState } from '@core/chat/agentTypes.ts';

type SubagentSpawnProjection = {
    status: AgentToolCallStatus;
    result: JsonValue | null | undefined;
};

const getOrCreateIteration = (turnState: AgentTurnState, iterationIndex: number): AgentIteration => {
    const existing = turnState.iterations.get(iterationIndex);
    if (existing) {
        return existing;
    }
    const iteration: AgentIteration = {
        iterationIndex: iterationIndex,
        itemId: null,
        text: '',
        toolCalls: [],
        status: 'running'
    };
    turnState.iterations.set(iterationIndex, iteration);
    return iteration;
};

const statusRank = (status: AgentToolCallStatus): number => {
    if (status === 'pending') {
        return 0;
    }
    if (status === 'running') {
        return 1;
    }
    return 2;
};

const resolveSubagentSpawnProjection = (turnState: AgentTurnState, iterationIndex: number, toolCallId: string, existingResult: JsonValue | null | undefined | null): SubagentSpawnProjection | null => {
    let selectedSubagent: AgentSubagentState | null = null;
    let selectedRank = -1;
    for (const subagent of turnState.subagents.values()) {
        if (subagent.parentIterationIndex !== iterationIndex || subagent.parentToolCallId !== toolCallId) {
            continue;
        }
        const candidateRank = subagent.status === 'accepted' ? 0 : subagent.status === 'running' ? 1 : 2;
        if (selectedSubagent === null || candidateRank > selectedRank || (candidateRank === selectedRank && subagent.updatedAtMs >= selectedSubagent.updatedAtMs)) {
            selectedSubagent = subagent;
            selectedRank = candidateRank;
        }
    }
    if (selectedSubagent === null) {
        return null;
    }
    return {
        status: selectedSubagent.status === 'accepted' ? 'pending' : selectedSubagent.status === 'running' ? 'running' : selectedSubagent.status === 'completed' || selectedSubagent.status === 'max_iterations' ? 'completed' : selectedSubagent.status === 'cancelled' ? 'cancelled' : 'error',
        result: buildParentToolCallResultPayload(selectedSubagent, turnState.convId, existingResult)
    };
};

const resolveStartedState = (turnState: AgentTurnState, iterationIndex: number, toolCallId: string, toolName: string, existing: AgentIterationToolCall | undefined): { status: AgentToolCallStatus; result: JsonValue | null | undefined | null } => {
    if (toolName === 'subagent_spawn') {
        const subagentProjection = resolveSubagentSpawnProjection(turnState, iterationIndex, toolCallId, existing?.result ?? null);
        if (subagentProjection) {
            return {
                status: subagentProjection.status,
                result: subagentProjection.result
            };
        }
        if (!existing || statusRank(existing.status) !== 2) {
            return {
                status: 'pending',
                result: existing?.result ?? null
            };
        }
    }
    if (existing && statusRank(existing.status) === 2) {
        return {
            status: existing.status,
            result: existing.result
        };
    }
    return {
        status: 'running',
        result: existing?.result ?? null
    };
};

const applyItemStarted = (turnState: AgentTurnState, iterationIndex: number, itemId: string, itemType: string, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    if (itemType === 'assistant_message') {
        iteration.itemId = itemId;
        iteration.status = 'running';
        return true;
    }
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === itemId);
    if (existingIndex >= 0) {
        const existing = iteration.toolCalls[existingIndex];
        if (!existing) {
            return false;
        }
        const textLengthBefore = Number.isFinite(existing.textLengthBefore) && existing.textLengthBefore >= 0 ? existing.textLengthBefore : iteration.text.length;
        const startedSequence = Number.isFinite(existing.startedSequence) && existing.startedSequence > 0 ? Math.min(existing.startedSequence, sequence) : sequence;
        const startedState = resolveStartedState(turnState, iterationIndex, itemId, itemType, existing);
        iteration.toolCalls[existingIndex] = {
            toolCallId: itemId,
            toolName: itemType,
            inputArguments: existing.inputArguments,
            codeDiffs: isArray(existing.codeDiffs) ? existing.codeDiffs : [],
            status: startedState.status,
            result: startedState.result,
            textLengthBefore,
            startedSequence,
            lastSequence: Math.max(existing.lastSequence, sequence),
            startedAtMs: existing.startedAtMs,
            durationMs: existing.durationMs
        };
        return true;
    }
    const startedState = resolveStartedState(turnState, iterationIndex, itemId, itemType, undefined);
    iteration.toolCalls.push({
        toolCallId: itemId,
        toolName: itemType,
        inputArguments: null,
        codeDiffs: [],
        status: startedState.status,
        result: startedState.result,
        textLengthBefore: iteration.text.length,
        startedSequence: sequence,
        lastSequence: sequence,
        startedAtMs: null,
        durationMs: null
    });
    return true;
};

const applyItemDelta = (turnState: AgentTurnState, iterationIndex: number, textDelta: string, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    iteration.text += textDelta;
    return true;
};

const applyItemCompleted = (turnState: AgentTurnState, iterationIndex: number, itemId: string, finalText: string, sequence: number): boolean => {
    if (isSequenceStale(turnState, sequence)) {
        return false;
    }
    advanceSequence(turnState, sequence);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    if (iteration.itemId === null) {
        iteration.itemId = itemId;
        iteration.text = finalText;
        iteration.status = 'completed';
        return true;
    }
    if (itemId === iteration.itemId) {
        iteration.text = finalText;
        iteration.status = 'completed';
        return true;
    }
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === itemId);
    if (existingIndex < 0) {
        return false;
    }
    const existing = iteration.toolCalls[existingIndex];
    if (!existing) {
        return false;
    }
    const textLengthBefore = Number.isFinite(existing.textLengthBefore) && existing.textLengthBefore >= 0 ? existing.textLengthBefore : iteration.text.length;
    const startedSequence = Number.isFinite(existing.startedSequence) && existing.startedSequence > 0 ? existing.startedSequence : sequence;
    const subagentProjection = existing.toolName === 'subagent_spawn' ? resolveSubagentSpawnProjection(turnState, iterationIndex, itemId, existing.result) : null;
    const existingIsTerminal = statusRank(existing.status) === 2;
    iteration.toolCalls[existingIndex] = {
        toolCallId: itemId,
        toolName: existing.toolName,
        inputArguments: existing.inputArguments,
        codeDiffs: isArray(existing.codeDiffs) ? existing.codeDiffs : [],
        status: subagentProjection?.status ?? (existingIsTerminal ? existing.status : 'completed'),
        result: subagentProjection?.result ?? (existingIsTerminal ? (existing.result ?? finalText) : finalText),
        textLengthBefore,
        startedSequence,
        lastSequence: sequence,
        startedAtMs: existing.startedAtMs,
        durationMs: existing.durationMs
    };
    return true;
};

export { applyItemCompleted, applyItemDelta, applyItemStarted, getOrCreateIteration, resolveStartedState, resolveSubagentSpawnProjection, statusRank };
