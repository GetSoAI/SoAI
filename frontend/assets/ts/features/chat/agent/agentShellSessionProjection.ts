/* SoAI - Chat feature agent shell session projection [frontend/assets/ts/features/chat/agent/agentShellSessionProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { MAX_TOOL_OUTPUT_CHARS, appendCappedToolOutput } from '@features/chat/toolOutput.ts';
import { serializeShellSessionToolResult, tryParseShellSessionToolResult } from '@features/chat/agent/agentShellSessionResultParsing.ts';
import type { AgentTurnState } from '@core/chat/agentTypes.ts';

const mergeShellSessionToolResults = (existingResult: JsonValue | null | undefined | null, incomingResult: JsonValue | null | undefined | null): JsonValue | null | undefined | null => {
    if (incomingResult === null) {
        return existingResult;
    }
    if (existingResult === null) {
        return incomingResult;
    }
    const parsedExisting = tryParseShellSessionToolResult(existingResult);
    const parsedIncoming = tryParseShellSessionToolResult(incomingResult);
    if (parsedExisting === null || parsedIncoming === null) {
        return incomingResult;
    }
    if (parsedExisting.sessionId !== parsedIncoming.sessionId) {
        return incomingResult;
    }
    const output = (() => {
        if (parsedExisting.output.length > parsedIncoming.output.length) {
            return parsedExisting.output;
        }
        if (parsedIncoming.output.length > parsedExisting.output.length) {
            return parsedIncoming.output;
        }
        if (parsedIncoming.output.length === MAX_TOOL_OUTPUT_CHARS) {
            return parsedIncoming.output;
        }
        return parsedExisting.output;
    })();
    const exitCode = parsedIncoming.exitCode !== null ? parsedIncoming.exitCode : parsedExisting.exitCode;
    return serializeShellSessionToolResult({
        sessionId: parsedExisting.sessionId,
        output,
        exitCode
    });
};

const applyWriteStdinResultToShellSession = (turnState: AgentTurnState, inputArguments: { writeResult: JsonValue | null | undefined; sequence: number; startedAtMs: number | null; durationMs: number | null }): void => {
    const parsedWrite = tryParseShellSessionToolResult(inputArguments.writeResult);
    if (parsedWrite === null) {
        return;
    }
    const sessionId = parsedWrite.sessionId;
    if (!Number.isFinite(sessionId) || !Number.isInteger(sessionId) || sessionId < 0) {
        return;
    }

    type Candidate = {
        iterationIndex: number;
        toolCallIndex: number;
        startedSequence: number;
        lastSequence: number;
    };
    let selectedCandidate: Candidate | null = null;

    for (const [iterationIndex, iteration] of turnState.iterations.entries()) {
        for (let toolCallIndex = 0; toolCallIndex < iteration.toolCalls.length; toolCallIndex += 1) {
            const toolCall = iteration.toolCalls[toolCallIndex];
            if (!toolCall || toolCall.toolName !== 'shell') {
                continue;
            }
            const parsedShell = toolCall.result ? tryParseShellSessionToolResult(toolCall.result) : null;
            if (parsedShell === null || parsedShell.sessionId !== sessionId) {
                continue;
            }
            if (parsedShell.exitCode !== null) {
                continue;
            }
            const candidate: Candidate = {
                iterationIndex,
                toolCallIndex,
                startedSequence: toolCall.startedSequence,
                lastSequence: toolCall.lastSequence
            };
            if (selectedCandidate === null || candidate.startedSequence > selectedCandidate.startedSequence || (candidate.startedSequence === selectedCandidate.startedSequence && candidate.lastSequence > selectedCandidate.lastSequence)) {
                selectedCandidate = candidate;
            }
        }
    }

    if (selectedCandidate === null) {
        return;
    }

    const selectedIteration = turnState.iterations.get(selectedCandidate.iterationIndex);
    if (!selectedIteration) {
        return;
    }
    const selectedToolCall = selectedIteration.toolCalls[selectedCandidate.toolCallIndex];
    if (!selectedToolCall || !selectedToolCall.result) {
        return;
    }
    const parsedShell = tryParseShellSessionToolResult(selectedToolCall.result);
    if (parsedShell === null || parsedShell.sessionId !== sessionId || parsedShell.exitCode !== null) {
        return;
    }

    const mergedOutput = appendCappedToolOutput(parsedShell.output, parsedWrite.output);
    const mergedExitCode = parsedWrite.exitCode;
    selectedToolCall.result = serializeShellSessionToolResult({
        sessionId: sessionId,
        output: mergedOutput,
        exitCode: mergedExitCode
    });
    selectedToolCall.lastSequence = Math.max(selectedToolCall.lastSequence, inputArguments.sequence);

    if (mergedExitCode !== null) {
        selectedToolCall.status = 'completed';
        const shellStartedAtMs = selectedToolCall.startedAtMs;
        if (typeof shellStartedAtMs === 'number' && Number.isFinite(shellStartedAtMs) && inputArguments.startedAtMs !== null && inputArguments.durationMs !== null) {
            const finishedAtMs = inputArguments.startedAtMs + inputArguments.durationMs;
            selectedToolCall.durationMs = Math.max(0, finishedAtMs - Math.floor(shellStartedAtMs));
        }
        return;
    }

    selectedToolCall.status = 'running';
    selectedToolCall.durationMs = null;
};

export { applyWriteStdinResultToShellSession, mergeShellSessionToolResults };
