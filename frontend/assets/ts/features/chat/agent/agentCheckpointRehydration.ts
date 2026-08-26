/* SoAI - Chat feature agent checkpoint rehydration [frontend/assets/ts/features/chat/agent/agentCheckpointRehydration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { type JsonValue, isJsonObject } from '@core/types/jsonValues.ts';
import { isNumber } from '@core/typeGuards.ts';
import { parseCheckpointActivities } from '@features/chat/agent/agentCheckpointActivities.ts';
import { parseAgentCodeDiffs } from '@core/realtime/eventcontracts/agentparsing/codeDiffs.ts';
import { mergeSubagentsFromCheckpoint } from '@features/chat/agent/agentSubagentStateManager.ts';
import { buildAcceptedParentToolCallResult } from '@features/chat/agent/agentSubagentToolResult.ts';
import { applyWriteStdinResultToShellSession, mergeShellSessionToolResults } from '@features/chat/agent/agentShellSessionProjection.ts';
import { tryParseShellSessionToolResult } from '@features/chat/agent/agentShellSessionResultParsing.ts';
import { getOrCreateIteration } from '@features/chat/agent/agentIterationStateManager.ts';
import { countAgentTextCodePoints } from '@features/chat/agent/agentTextMetrics.ts';
import { applyTurnMessageIndex, getOrCreateTurnState, type AgentTurnStateMap } from '@features/chat/agent/agentTurnStateManager.ts';
import { isAgentMode } from '@features/chat/agent/agentModeState.ts';
import { normalizeToolResult, parseCheckpointToolCalls, resolveToolCallCompletionStatus } from '@features/chat/agent/agentCheckpointToolParsing.ts';
import type { AgentCheckpointResponse } from '@core/api/contracts/chatAgentContracts.ts';
import type { AgentIterationToolCall, AgentTurnStatus } from '@core/chat/agentTypes.ts';

const resolveTurnStatusFromCheckpoint = (status: AgentCheckpointResponse['status']): AgentTurnStatus => {
    if (status === 'running') {
        return 'running';
    }
    if (status === 'error' || status === 'cancelled' || status === 'abandoned') {
        return 'error';
    }
    return 'completed';
};

const upsertHydratedToolCall = (iteration: { toolCalls: AgentIterationToolCall[]; text: string }, incoming: AgentIterationToolCall): void => {
    const existingIndex = iteration.toolCalls.findIndex((entry) => entry.toolCallId === incoming.toolCallId);
    if (existingIndex < 0) {
        iteration.toolCalls.push(incoming);
        return;
    }
    const existing = iteration.toolCalls[existingIndex];
    if (!existing) {
        throw new Error(`Agent checkpoint tool call slot is missing for call ${incoming.toolCallId}`);
    }
    const preferIncoming = incoming.lastSequence >= existing.lastSequence;
    iteration.toolCalls[existingIndex] = {
        toolCallId: incoming.toolCallId,
        toolName: preferIncoming ? incoming.toolName : existing.toolName,
        inputArguments: preferIncoming ? (incoming.inputArguments ?? existing.inputArguments) : (existing.inputArguments ?? incoming.inputArguments),
        codeDiffs: incoming.codeDiffs.length > 0 ? incoming.codeDiffs : existing.codeDiffs,
        status: preferIncoming ? incoming.status : existing.status,
        result: preferIncoming ? (incoming.result ?? existing.result) : (existing.result ?? incoming.result),
        textLengthBefore: Number.isFinite(existing.textLengthBefore) && existing.textLengthBefore >= 0 ? existing.textLengthBefore : incoming.textLengthBefore,
        startedSequence: Math.min(existing.startedSequence, incoming.startedSequence),
        lastSequence: Math.max(existing.lastSequence, incoming.lastSequence),
        startedAtMs: preferIncoming ? (incoming.startedAtMs ?? existing.startedAtMs) : (existing.startedAtMs ?? incoming.startedAtMs),
        durationMs: preferIncoming ? (incoming.durationMs ?? existing.durationMs) : (existing.durationMs ?? incoming.durationMs)
    };
};

const resolveToolResultCodeDiffs = (toolResult: JsonValue | null | undefined, fallback: AgentIterationToolCall['codeDiffs']): AgentIterationToolCall['codeDiffs'] => {
    if (!isJsonObject(toolResult)) {
        return fallback;
    }
    return parseAgentCodeDiffs(toolResult['code_diffs']) ?? fallback;
};

const rehydrateTurnStateFromCheckpoint = (turnStateMap: AgentTurnStateMap, checkpoint: AgentCheckpointResponse): boolean => {
    const existingTurnState = turnStateMap.get(checkpoint.convId);
    if (existingTurnState && checkpoint.sequence < existingTurnState.lastSequence) {
        return false;
    }
    if (existingTurnState && existingTurnState.turnId !== checkpoint.turnId && checkpoint.startedAtMs < existingTurnState.turnStartedAtMs) {
        return false;
    }

    const mode = checkpoint.mode;
    if (!isAgentMode(mode)) {
        throw new Error(`Agent turn snapshot mode is invalid: ${mode}`);
    }
    const turnState = getOrCreateTurnState(turnStateMap, checkpoint.convId, checkpoint.turnId, mode, checkpoint.maxIterations, checkpoint.startedAtMs);
    if (isNumber(checkpoint.startedAtMs) && Number.isFinite(checkpoint.startedAtMs) && checkpoint.startedAtMs > 0) {
        turnState.turnStartedAtMs = Math.min(turnState.turnStartedAtMs, checkpoint.startedAtMs);
    }

    turnState.status = resolveTurnStatusFromCheckpoint(checkpoint.status);
    turnState.lastSequence = Math.max(turnState.lastSequence, checkpoint.sequence);

    const parsedActivities = parseCheckpointActivities(checkpoint.activities);
    for (const activity of parsedActivities) {
        applyTurnMessageIndex(turnState, activity.messageIndex);
        const iteration = getOrCreateIteration(turnState, activity.iterationIndex);
        upsertHydratedToolCall(iteration, {
            toolCallId: activity.toolCallId,
            toolName: activity.toolName,
            inputArguments: activity.argumentsValue,
            codeDiffs: activity.codeDiffs,
            status: activity.status,
            result: activity.result,
            textLengthBefore: activity.textLengthBefore,
            startedSequence: activity.startedSequence,
            lastSequence: activity.lastSequence,
            startedAtMs: activity.startedAtMs,
            durationMs: activity.durationMs
        });
        turnState.lastSequence = Math.max(turnState.lastSequence, activity.lastSequence);
    }

    const iteration = getOrCreateIteration(turnState, checkpoint.iterationIndex);
    const assistantText = checkpoint.assistantText;
    if (assistantText && assistantText.length > 0) {
        iteration.text = assistantText;
    }
    const iterationTextLength = countAgentTextCodePoints(iteration.text);
    const parsedToolCalls = parseCheckpointToolCalls(checkpoint.toolCalls);

    for (const parsedToolCall of parsedToolCalls) {
        upsertHydratedToolCall(iteration, {
            toolCallId: parsedToolCall.toolCallId,
            toolName: parsedToolCall.toolName,
            inputArguments: parsedToolCall.argumentsValue,
            codeDiffs: [],
            status: 'running',
            result: null,
            textLengthBefore: iterationTextLength,
            startedSequence: checkpoint.sequence,
            lastSequence: checkpoint.sequence,
            startedAtMs: parsedToolCall.startedAtMs,
            durationMs: parsedToolCall.durationMs
        });
    }

    if (checkpoint.toolResults.length > parsedToolCalls.length) {
        throw new Error('Agent checkpoint tool_results length exceeds tool_calls length.');
    }

    for (let index = 0; index < checkpoint.toolResults.length; index += 1) {
        const toolResult = checkpoint.toolResults[index];
        const parsedToolCall = parsedToolCalls[index];
        if (!parsedToolCall) {
            throw new Error(`Agent checkpoint tool result index ${index} has no matching tool call.`);
        }
        const canonicalAcceptedSubagentResult = parsedToolCall.toolName === 'subagent_spawn' ? buildAcceptedParentToolCallResult(toolResult) : null;
        const baseToolResult = canonicalAcceptedSubagentResult ?? normalizeToolResult(toolResult, parsedToolCall.toolCallId);
        const existingToolCall = iteration.toolCalls.find((entry) => entry.toolCallId === parsedToolCall.toolCallId);
        if (!existingToolCall) {
            throw new Error(`Agent checkpoint missing started tool call state for ${parsedToolCall.toolCallId}`);
        }
        const codeDiffs = resolveToolResultCodeDiffs(toolResult, existingToolCall.codeDiffs);
        const mergedShellResult = parsedToolCall.toolName === 'shell' ? mergeShellSessionToolResults(existingToolCall.result, baseToolResult) : null;
        upsertHydratedToolCall(iteration, {
            toolCallId: parsedToolCall.toolCallId,
            toolName: parsedToolCall.toolName,
            inputArguments: existingToolCall.inputArguments,
            codeDiffs: codeDiffs,
            status: resolveToolCallCompletionStatus(parsedToolCall.toolName, toolResult),
            result: mergedShellResult ?? baseToolResult,
            textLengthBefore: Number.isFinite(existingToolCall.textLengthBefore) && existingToolCall.textLengthBefore >= 0 ? existingToolCall.textLengthBefore : iterationTextLength,
            startedSequence: Number.isFinite(existingToolCall.startedSequence) && existingToolCall.startedSequence > 0 ? existingToolCall.startedSequence : checkpoint.sequence,
            lastSequence: checkpoint.sequence,
            startedAtMs: parsedToolCall.startedAtMs === null ? existingToolCall.startedAtMs : parsedToolCall.startedAtMs,
            durationMs: parsedToolCall.durationMs === null ? existingToolCall.durationMs : parsedToolCall.durationMs
        });
    }

    for (const hydratedIteration of turnState.iterations.values()) {
        for (const toolCall of hydratedIteration.toolCalls) {
            if (!toolCall || toolCall.toolName !== 'shell' || toolCall.status !== 'running' || toolCall.result === null) {
                continue;
            }
            const parsed = tryParseShellSessionToolResult(toolCall.result);
            if (parsed !== null && parsed.exitCode === null) {
                toolCall.durationMs = null;
            }
        }
    }

    turnState.todo = checkpoint.todo.map((entry) => ({
        step: entry.step,
        status: entry.status
    }));
    turnState.todoExplanation = checkpoint.todoExplanation;
    if (turnState.status !== 'running') {
        iteration.status = turnState.status;
    }

    for (const hydratedIteration of turnState.iterations.values()) {
        for (const toolCall of hydratedIteration.toolCalls) {
            if (!toolCall || toolCall.toolName !== 'shell_write_stdin' || toolCall.result === null) {
                continue;
            }
            applyWriteStdinResultToShellSession(turnState, {
                writeResult: toolCall.result,
                sequence: checkpoint.sequence,
                startedAtMs: toolCall.startedAtMs,
                durationMs: toolCall.durationMs
            });
        }
    }

    mergeSubagentsFromCheckpoint(turnState, checkpoint.subagents);
    return true;
};

export { rehydrateTurnStateFromCheckpoint };
