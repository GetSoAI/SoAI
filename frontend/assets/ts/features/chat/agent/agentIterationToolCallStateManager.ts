/* SoAI - Chat feature agent iteration tool call state manager [frontend/assets/ts/features/chat/agent/agentIterationToolCallStateManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { tryParseShellSessionToolResult } from '@features/chat/agent/agentShellSessionResultParsing.ts';
import { applyWriteStdinResultToShellSession } from '@features/chat/agent/agentShellSessionProjection.ts';
import { buildAcceptedParentToolCallResult } from '@features/chat/agent/agentSubagentToolResult.ts';
import { getOrCreateIteration, resolveStartedState, resolveSubagentSpawnProjection } from '@features/chat/agent/agentIterationStateManager.ts';
import { countAgentTextCodePoints } from '@features/chat/agent/agentTextMetrics.ts';
import { applyTurnMessageIndex } from '@features/chat/agent/agentTurnStateManager.ts';
import type { AgentToolCallStatus, AgentTurnState } from '@core/chat/agentTypes.ts';
import type { ToolActivityCodeDiff } from '@features/chat/ChatTypes.ts';

const applyToolCallCreated = (turnState: AgentTurnState, iterationIndex: number, messageIndex: number, toolCallId: string, toolName: string, toolArguments: string | null, sequence: number): boolean => {
    applyTurnMessageIndex(turnState, messageIndex);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === toolCallId);
    const textLengthBefore = countAgentTextCodePoints(iteration.text);
    if (existingIndex >= 0) {
        const existing = iteration.toolCalls[existingIndex];
        if (existing) {
            existing.toolName = toolName;
            if (toolArguments !== null) {
                existing.inputArguments = toolArguments;
            }
            existing.status = existing.status === 'completed' || existing.status === 'cancelled' || existing.status === 'error' ? existing.status : 'pending';
            existing.startedSequence = Math.min(existing.startedSequence, sequence);
            existing.lastSequence = Math.max(existing.lastSequence, sequence);
            if (!isArray(existing.codeDiffs)) {
                existing.codeDiffs = [];
            }
            if (existing.status === 'pending') {
                existing.durationMs = null;
            }
            if (!Number.isFinite(existing.textLengthBefore) || existing.textLengthBefore < 0) {
                existing.textLengthBefore = textLengthBefore;
            }
        }
        return true;
    }
    iteration.toolCalls.push({
        toolCallId: toolCallId,
        toolName: toolName,
        inputArguments: toolArguments,
        codeDiffs: [],
        status: 'pending',
        result: null,
        textLengthBefore: textLengthBefore,
        startedSequence: sequence,
        lastSequence: sequence,
        startedAtMs: null,
        durationMs: null
    });
    return true;
};

const applyToolCallStarted = (turnState: AgentTurnState, iterationIndex: number, messageIndex: number, toolCallId: string, toolName: string, toolArguments: string | null, sequence: number, startedAtMs: number): boolean => {
    applyTurnMessageIndex(turnState, messageIndex);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === toolCallId);
    const textLengthBefore = countAgentTextCodePoints(iteration.text);
    if (existingIndex >= 0) {
        const existing = iteration.toolCalls[existingIndex];
        if (existing) {
            const startedState = resolveStartedState(turnState, iterationIndex, toolCallId, toolName, existing);
            existing.toolName = toolName;
            if (toolArguments !== null) {
                existing.inputArguments = toolArguments;
            }
            existing.status = startedState.status;
            existing.result = startedState.result;
            existing.startedSequence = Math.min(existing.startedSequence, sequence);
            existing.lastSequence = Math.max(existing.lastSequence, sequence);
            existing.startedAtMs = startedAtMs;
            if (!isArray(existing.codeDiffs)) {
                existing.codeDiffs = [];
            }
            existing.durationMs = null;
            if (!Number.isFinite(existing.textLengthBefore) || existing.textLengthBefore < 0) {
                existing.textLengthBefore = textLengthBefore;
            }
        }
        return true;
    }
    const startedState = resolveStartedState(turnState, iterationIndex, toolCallId, toolName, undefined);
    iteration.toolCalls.push({
        toolCallId: toolCallId,
        toolName: toolName,
        inputArguments: toolArguments,
        codeDiffs: [],
        status: startedState.status,
        result: startedState.result,
        textLengthBefore: textLengthBefore,
        startedSequence: sequence,
        lastSequence: sequence,
        startedAtMs: startedAtMs,
        durationMs: null
    });
    return true;
};

const applyToolCallCompleted = (turnState: AgentTurnState, iterationIndex: number, messageIndex: number, toolCallId: string, toolName: string, toolArguments: string | null, result: JsonValue | null | undefined | null, codeDiffs: ToolActivityCodeDiff[] | null, sequence: number, completionStatus: 'completed' | 'cancelled' | 'error', startedAtMs: number | null, durationMs: number | null): boolean => {
    applyTurnMessageIndex(turnState, messageIndex);
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    const canonicalAcceptedSubagentResult = toolName === 'subagent_spawn' && completionStatus === 'completed' ? buildAcceptedParentToolCallResult(result) : null;
    const treatAcceptedSubagentSpawnAsPending = toolName === 'subagent_spawn' && completionStatus === 'completed' && canonicalAcceptedSubagentResult !== null;
    const shellSessionResult = toolName === 'shell' ? tryParseShellSessionToolResult(result) : null;
    const treatShellSessionAsRunning = toolName === 'shell' && completionStatus === 'completed' && shellSessionResult !== null && shellSessionResult.exitCode === null;
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === toolCallId);
    if (existingIndex >= 0) {
        const existing = iteration.toolCalls[existingIndex];
        if (!existing) {
            return false;
        }
        const subagentProjection = toolName === 'subagent_spawn' && completionStatus === 'completed' ? resolveSubagentSpawnProjection(turnState, iterationIndex, toolCallId, existing.result) : null;
        const resolvedStatus: AgentToolCallStatus = subagentProjection?.status ?? (treatAcceptedSubagentSpawnAsPending ? 'pending' : treatShellSessionAsRunning ? 'running' : completionStatus);
        const resolvedStartedAtMs = startedAtMs === null ? existing.startedAtMs : startedAtMs;
        const existingCodeDiffs = isArray(existing.codeDiffs) ? existing.codeDiffs : [];
        const textLengthBefore = Number.isFinite(existing.textLengthBefore) && existing.textLengthBefore >= 0 ? existing.textLengthBefore : countAgentTextCodePoints(iteration.text);
        const startedSequence = Number.isFinite(existing.startedSequence) && existing.startedSequence > 0 ? existing.startedSequence : sequence;
        iteration.toolCalls[existingIndex] = {
            toolCallId: toolCallId,
            toolName: toolName,
            inputArguments: toolArguments === null ? existing.inputArguments : toolArguments,
            codeDiffs: codeDiffs === null ? existingCodeDiffs : codeDiffs,
            status: resolvedStatus,
            result: subagentProjection?.result ?? canonicalAcceptedSubagentResult ?? result ?? existing.result,
            textLengthBefore,
            startedSequence,
            lastSequence: sequence,
            startedAtMs: resolvedStartedAtMs,
            durationMs: treatShellSessionAsRunning ? null : durationMs
        };
        if (toolName === 'shell_write_stdin' && completionStatus === 'completed') {
            applyWriteStdinResultToShellSession(turnState, {
                writeResult: result,
                sequence,
                startedAtMs,
                durationMs
            });
        }
        return true;
    }
    const subagentProjection = toolName === 'subagent_spawn' && completionStatus === 'completed' ? resolveSubagentSpawnProjection(turnState, iterationIndex, toolCallId, null) : null;
    const resolvedStatus: AgentToolCallStatus = subagentProjection?.status ?? (treatAcceptedSubagentSpawnAsPending ? 'pending' : treatShellSessionAsRunning ? 'running' : completionStatus);
    iteration.toolCalls.push({
        toolCallId: toolCallId,
        toolName: toolName,
        inputArguments: toolArguments,
        codeDiffs: codeDiffs ?? [],
        status: resolvedStatus,
        result: subagentProjection?.result ?? canonicalAcceptedSubagentResult ?? result,
        textLengthBefore: countAgentTextCodePoints(iteration.text),
        startedSequence: sequence,
        lastSequence: sequence,
        startedAtMs: startedAtMs,
        durationMs: treatShellSessionAsRunning ? null : durationMs
    });
    if (toolName === 'shell_write_stdin' && completionStatus === 'completed') {
        applyWriteStdinResultToShellSession(turnState, {
            writeResult: result,
            sequence,
            startedAtMs,
            durationMs
        });
    }
    return true;
};

const applyToolCallRunning = (turnState: AgentTurnState, iterationIndex: number, toolCallId: string, sequence: number, startedAtMs: number, durationMs: number): boolean => {
    const iteration = getOrCreateIteration(turnState, iterationIndex);
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === toolCallId);
    if (existingIndex < 0) {
        return false;
    }
    const existing = iteration.toolCalls[existingIndex];
    if (!existing) {
        return false;
    }
    if (existing.status !== 'running') {
        return false;
    }
    if (!Number.isFinite(durationMs) || durationMs < 0) {
        return false;
    }
    if (!Number.isFinite(startedAtMs) || startedAtMs < 0) {
        return false;
    }
    const normalizedDurationMs = Math.floor(durationMs);
    const normalizedStartedAtMs = Math.floor(startedAtMs);
    let updatedStartedAtMs = false;
    if (existing.startedAtMs === null) {
        existing.startedAtMs = normalizedStartedAtMs;
        updatedStartedAtMs = true;
    }
    const previousDurationMs = existing.durationMs;
    if (previousDurationMs !== null && previousDurationMs >= normalizedDurationMs) {
        return updatedStartedAtMs;
    }
    existing.durationMs = normalizedDurationMs;
    existing.lastSequence = Math.max(existing.lastSequence, sequence);
    return true;
};

export { applyToolCallCompleted, applyToolCallCreated, applyToolCallRunning, applyToolCallStarted };
