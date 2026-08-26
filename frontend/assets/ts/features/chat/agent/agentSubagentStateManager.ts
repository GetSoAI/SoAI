/* SoAI - Chat feature agent subagent state manager [frontend/assets/ts/features/chat/agent/agentSubagentStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { appendCappedToolOutput } from '@features/chat/toolOutput.ts';
import type { AgentSubagentEventPayload, AgentSubagentSnapshot, AgentSubagentState } from '@core/chat/agentSubagentTypes.ts';
import { buildParentToolCallResultPayload } from '@features/chat/agent/agentSubagentToolResult.ts';
import type { AgentTurnState } from '@core/chat/agentTypes.ts';
import { isTerminalSubagentStatus, mergeResultText, resolveEffectiveSubagentStatus, resolveSubagentDisplayOrder, resolveSubagentStatusRank, shouldApplySubagentSnapshot } from '@features/chat/agent/agentSubagentStateRules.ts';

const syncParentToolCallStatus = (turnState: AgentTurnState, subagent: AgentSubagentState): void => {
    const parentIterationIndex = subagent.parentIterationIndex;
    const parentToolCallId = subagent.parentToolCallId;
    const iteration = turnState.iterations.get(parentIterationIndex);
    if (!iteration) {
        return;
    }
    const toolCall = iteration.toolCalls.find((entry) => entry.toolCallId === parentToolCallId);
    if (!toolCall || toolCall.toolName !== 'subagent_spawn') {
        return;
    }
    if (subagent.status === 'accepted') {
        toolCall.status = 'pending';
        toolCall.result = buildParentToolCallResultPayload(subagent, turnState.convId, toolCall.result);
        return;
    }
    if (subagent.status === 'running') {
        toolCall.status = 'running';
        toolCall.result = buildParentToolCallResultPayload(subagent, turnState.convId, toolCall.result);
        return;
    }
    if (subagent.status === 'completed' || subagent.status === 'max_iterations') {
        toolCall.status = 'completed';
    } else if (subagent.status === 'cancelled') {
        toolCall.status = 'cancelled';
    } else {
        toolCall.status = 'error';
    }
    toolCall.result = buildParentToolCallResultPayload(subagent, turnState.convId, toolCall.result);
};

const mergeSubagentsFromCheckpoint = (turnState: AgentTurnState, snapshots: AgentSubagentSnapshot[]): void => {
    for (const snapshot of snapshots) {
        const existing = turnState.subagents.get(snapshot.subagentId);
        if (!shouldApplySubagentSnapshot(existing, snapshot)) {
            continue;
        }
        const mergedResultText = mergeResultText(existing?.resultText ?? null, snapshot.resultText ?? null);
        const effectiveStatus = resolveEffectiveSubagentStatus(snapshot.status === 'running' ? 'running' : snapshot.status, mergedResultText);
        const nextState: AgentSubagentState = {
            subagentId: snapshot.subagentId,
            executionType: snapshot.executionType,
            ownerTaskId: snapshot.ownerTaskId,
            status: effectiveStatus,
            statusMessage: snapshot.statusMessage ?? existing?.statusMessage ?? null,
            mode: snapshot.mode,
            displayName: snapshot.displayName ?? existing?.displayName ?? null,
            parentTurnId: snapshot.parentTurnId,
            parentToolCallId: snapshot.parentToolCallId,
            parentIterationIndex: snapshot.parentIterationIndex,
            startedAtMs: snapshot.startedAtMs,
            updatedAtMs: snapshot.updatedAtMs,
            finishedAtMs: snapshot.finishedAtMs,
            requestedModel: snapshot.requestedModel ?? existing?.requestedModel ?? null,
            resultText: mergedResultText,
            errorMessage: snapshot.errorMessage ?? existing?.errorMessage ?? null,
            errorType: snapshot.errorType ?? existing?.errorType ?? null,
            tokenUsage: snapshot.tokenUsage ?? existing?.tokenUsage ?? null,
            displayOrder: resolveSubagentDisplayOrder(turnState, existing)
        };
        turnState.subagents.set(snapshot.subagentId, nextState);
        syncParentToolCallStatus(turnState, nextState);
    }
};

const applySubagentEvent = (turnState: AgentTurnState, payload: AgentSubagentEventPayload): boolean => {
    const existing = turnState.subagents.get(payload.subagentId);
    if (existing && isTerminalSubagentStatus(existing.status) && payload.status !== existing.status) {
        return false;
    }
    if (existing && resolveSubagentStatusRank(payload.status) < resolveSubagentStatusRank(existing.status)) {
        return false;
    }
    if (existing && payload.updatedAtMs < existing.updatedAtMs) {
        return false;
    }
    const mergedResultText = (() => {
        if (payload.status === 'running' && typeof payload.resultTextDelta === 'string' && payload.resultTextDelta.length > 0) {
            const baseOutput = typeof existing?.resultText === 'string' ? existing.resultText : '';
            return appendCappedToolOutput(baseOutput, payload.resultTextDelta);
        }
        if (payload.status === 'running') {
            if (typeof existing?.resultText === 'string' && existing.resultText.length > 0) {
                return existing.resultText;
            }
            return mergeResultText(existing?.resultText ?? null, payload.resultText ?? null);
        }
        if (payload.resultText !== null && payload.resultText.trim().length > 0) {
            return mergeResultText(existing?.resultText ?? null, payload.resultText);
        }
        return existing?.resultText ?? null;
    })();
    const effectiveStatus = resolveEffectiveSubagentStatus(payload.status, mergedResultText);
    const nextState: AgentSubagentState = {
        subagentId: payload.subagentId,
        executionType: payload.executionType,
        ownerTaskId: payload.ownerTaskId,
        status: effectiveStatus,
        statusMessage: payload.statusMessage ?? existing?.statusMessage ?? null,
        mode: payload.mode,
        displayName: payload.displayName ?? existing?.displayName ?? null,
        parentTurnId: payload.parentTurnId,
        parentToolCallId: payload.parentToolCallId,
        parentIterationIndex: payload.parentIterationIndex,
        startedAtMs: payload.startedAtMs,
        updatedAtMs: payload.updatedAtMs,
        finishedAtMs: payload.finishedAtMs,
        requestedModel: payload.requestedModel ?? existing?.requestedModel ?? null,
        resultText: mergedResultText,
        errorMessage: payload.errorMessage ?? existing?.errorMessage ?? null,
        errorType: payload.errorType ?? existing?.errorType ?? null,
        tokenUsage: payload.tokenUsage ?? existing?.tokenUsage ?? null,
        displayOrder: resolveSubagentDisplayOrder(turnState, existing)
    };
    turnState.subagents.set(payload.subagentId, nextState);
    syncParentToolCallStatus(turnState, nextState);
    return true;
};

export { applySubagentEvent, mergeSubagentsFromCheckpoint };
