/* SoAI - Chat feature agent checkpoint tool parsing [frontend/assets/ts/features/chat/agent/agentCheckpointToolParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { readInteger, readString } from '@core/types/payloadValueReaders.ts';
import { isShellSessionInProgressToolResult } from '@features/chat/agent/agentShellSessionResultParsing.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { tryResolveAcceptedSubagentPayloadRecord } from '@features/chat/agent/agentSubagentToolResult.ts';
import type { AgentToolCallStatus } from '@core/chat/agentTypes.ts';

type ParsedCheckpointToolCall = {
    toolCallId: string;
    toolName: string;
    argumentsValue: string | null;
    startedAtMs: number | null;
    durationMs: number | null;
};

const serializeJsonValue = (value: JsonValue | null | undefined, contextLabel: string): string => {
    const serialized = JSON.stringify(value);
    if (!isString(serialized)) {
        throw new Error(`Agent turn snapshot ${contextLabel} serialization failed.`);
    }
    return serialized;
};

const serializeToolArguments = (value: JsonValue | null | undefined, toolCallId: string): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    if (isString(value)) {
        const trimmedValue = value.trim();
        return trimmedValue ? trimmedValue : null;
    }
    if (isObject(value)) {
        return serializeJsonValue(value, `tool inputArguments for call ${toolCallId}`);
    }
    throw new Error(`Agent turn snapshot tool inputArguments for call ${toolCallId} have invalid type.`);
};

const parseCheckpointToolCalls = (toolCalls: ReadonlyArray<JsonValue | null | undefined>): ParsedCheckpointToolCall[] => {
    const parsedToolCalls: ParsedCheckpointToolCall[] = [];
    const seenToolCallIds = new Set<string>();
    for (let index = 0; index < toolCalls.length; index += 1) {
        const value = toolCalls[index];
        if (!isObject(value) || isArray(value)) {
            throw new Error(`Agent turn snapshot tool_calls[${index}] is invalid.`);
        }
        const toolCallIdRaw = readString(value, 'id');
        const toolNameRaw = readString(value, 'name');
        const startedAtMs = readInteger(value, 'started_at_ms');
        const durationMs = readInteger(value, 'duration_ms');
        if (!toolCallIdRaw || !toolNameRaw) {
            throw new Error(`Agent turn snapshot tool_calls[${index}] is missing id or name.`);
        }
        const normalizedToolCallId = toolCallIdRaw.trim();
        const normalizedToolName = toolNameRaw.trim();
        if (!normalizedToolCallId || !normalizedToolName) {
            throw new Error(`Agent turn snapshot tool_calls[${index}] contains blank id or name.`);
        }
        if (seenToolCallIds.has(normalizedToolCallId)) {
            throw new Error(`Agent turn snapshot contains duplicate tool call id: ${normalizedToolCallId}`);
        }
        if (startedAtMs !== null && !isEpochMsNumber(startedAtMs)) {
            throw new Error(`Agent turn snapshot tool_calls[${index}] has invalid started_at_ms.`);
        }
        if (durationMs !== null && durationMs < 0) {
            throw new Error(`Agent turn snapshot tool_calls[${index}] has invalid duration_ms.`);
        }
        seenToolCallIds.add(normalizedToolCallId);
        parsedToolCalls.push({
            toolCallId: normalizedToolCallId,
            toolName: normalizedToolName,
            argumentsValue: serializeToolArguments(value['arguments'], normalizedToolCallId),
            startedAtMs,
            durationMs
        });
    }
    return parsedToolCalls;
};

const normalizeToolResult = (value: JsonValue | null | undefined, _toolCallId: string): JsonValue | null | undefined => {
    return value;
};

const isAcceptedSubagentSpawnResult = (toolResult: JsonValue | null | undefined): boolean => {
    const subagentValue = tryResolveAcceptedSubagentPayloadRecord(toolResult);
    if (subagentValue === null) {
        return false;
    }
    const statusValue = subagentValue['status'];
    return isString(statusValue) && statusValue === 'accepted';
};

const resolveToolCallCompletionStatus = (toolName: string, toolResult: JsonValue | null | undefined): AgentToolCallStatus => {
    if (toolName === 'subagent_spawn' && isAcceptedSubagentSpawnResult(toolResult)) {
        return 'pending';
    }
    if (toolName === 'shell' && isShellSessionInProgressToolResult(toolResult)) {
        return 'running';
    }
    let parsedToolResult = toolResult;
    if (isString(parsedToolResult)) {
        const trimmed = parsedToolResult.trim();
        if (trimmed.startsWith('{')) {
            try {
                const parsed = parseRequiredJsonText(trimmed);
                parsedToolResult = parsed;
            } catch (error) {
                errorHandler.warn('AgentCheckpointToolParsing', 'Failed to parse checkpoint tool result JSON', ensureError(error));
                return 'completed';
            }
        }
    }
    if (!isObject(parsedToolResult) || isArray(parsedToolResult)) {
        return 'completed';
    }
    const errorValue = parsedToolResult['error'];
    if (isString(errorValue) && errorValue.trim()) {
        const codeValue = parsedToolResult['code'];
        return isString(codeValue) && codeValue.trim() === 'cancelled' ? 'cancelled' : 'error';
    }
    return 'completed';
};

export { normalizeToolResult, parseCheckpointToolCalls, resolveToolCallCompletionStatus, serializeToolArguments };
export type { ParsedCheckpointToolCall };
