/* SoAI - Chat feature agent subagent tool result [frontend/assets/ts/features/chat/agent/agentSubagentToolResult.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isArray, isPlainObject } from '@core/typeGuards.ts';
import { readNullableTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { AgentSubagentState } from '@core/chat/agentSubagentTypes.ts';
import { decodeSubagentStreamTextBlocks, decodeSubagentStreamToolCalls } from '@features/chat/agent/agentSubagentStreamParsing.ts';
import { isSubagentModeValue, isSubagentStatusValue } from '@core/realtime/eventcontracts/agentparsing/subagentFields.ts';

type BackendSubagentToolResultParseOutcome = { ok: true; subagentRecord: JsonObject; toolCalls: ReadonlyArray<JsonValue | null>; textBlocks: ReadonlyArray<JsonValue | null> } | { ok: false; error: Error };
type SubagentStreamPayload = { toolCalls: ReadonlyArray<JsonValue | null>; textBlocks: ReadonlyArray<JsonValue | null> };

const buildCanonicalParentToolCallResultPayload = (subagentPayload: JsonObject, toolCalls: ReadonlyArray<JsonValue | null> = [], textBlocks: ReadonlyArray<JsonValue | null> = []): JsonObject => {
    return {
        subagent: subagentPayload,
        subagentStream: {
            toolCalls: [...toolCalls],
            textBlocks: [...textBlocks]
        }
    };
};

const buildSubagentPayloadFromState = (subagent: AgentSubagentState, convId: string): JsonObject => {
    const subagentPayload: JsonObject = {
        subagentId: subagent.subagentId,
        executionType: subagent.executionType,
        ownerTaskId: subagent.ownerTaskId,
        mode: subagent.mode,
        status: subagent.status,
        convId: convId,
        parentTurnId: subagent.parentTurnId,
        parentToolCallId: subagent.parentToolCallId,
        parentIterationIndex: subagent.parentIterationIndex,
        startedAtMs: subagent.startedAtMs,
        updatedAtMs: subagent.updatedAtMs,
        finishedAtMs: subagent.finishedAtMs
    };
    if (subagent.statusMessage !== null) {
        subagentPayload['statusMessage'] = subagent.statusMessage;
    }
    if (subagent.displayName !== null) {
        subagentPayload['displayName'] = subagent.displayName;
    }
    if (subagent.requestedModel !== null) {
        subagentPayload['requestedModel'] = subagent.requestedModel;
    }
    if (subagent.resultText !== null) {
        subagentPayload['resultText'] = subagent.resultText;
    }
    if (subagent.errorMessage !== null) {
        subagentPayload['errorMessage'] = subagent.errorMessage;
    }
    if (subagent.errorType !== null) {
        subagentPayload['errorType'] = subagent.errorType;
    }
    if (subagent.tokenUsage !== null) {
        subagentPayload['tokenUsage'] = subagent.tokenUsage;
    }
    return subagentPayload;
};

const resolveExistingSubagentStreamPayload = (existingResult: JsonValue | null): SubagentStreamPayload => {
    if (!isPlainObject(existingResult)) {
        return { toolCalls: [], textBlocks: [] };
    }
    const streamValue = existingResult['subagentStream'];
    if (!isPlainObject(streamValue)) {
        return { toolCalls: [], textBlocks: [] };
    }
    const toolCalls = streamValue['toolCalls'];
    const textBlocks = streamValue['textBlocks'];
    return {
        toolCalls: isArray(toolCalls) ? toolCalls : [],
        textBlocks: isArray(textBlocks) ? textBlocks : []
    };
};

const buildParentToolCallResultPayload = (subagent: AgentSubagentState, convId: string, existingResult: JsonValue | null = null): JsonObject => {
    const streamPayload = resolveExistingSubagentStreamPayload(existingResult);
    return buildCanonicalParentToolCallResultPayload(buildSubagentPayloadFromState(subagent, convId), streamPayload.toolCalls, streamPayload.textBlocks);
};

const readOptionalSubagentText = (value: JsonValue | undefined, label: string): string | null | undefined => {
    if (value === undefined || value === null) return value;
    if (typeof value !== 'string') throw new Error(`Subagent tool result field ${label} is invalid.`);
    return value.trim();
};

const readRequiredSubagentText = (value: JsonValue | undefined, label: string): string | undefined => {
    if (value === undefined) return undefined;
    const normalizedValue = toTrimmedString(value);
    if (!normalizedValue) throw new Error(`Subagent tool result field ${label} is invalid.`);
    return normalizedValue;
};

const readSubagentNonNegativeInteger = (value: JsonValue | undefined, label: string): number | undefined => {
    if (value === undefined) return undefined;
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) throw new Error(`Subagent tool result field ${label} is invalid.`);
    return value;
};

const readSubagentFinishedAtMs = (value: JsonValue | undefined): number | null | undefined => {
    if (value === undefined || value === null) return value;
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) throw new Error('Subagent tool result field finished_at_ms is invalid.');
    return value;
};

const tryResolveBackendSubagentToolResultRecord = (toolResult: JsonValue | null | undefined): BackendSubagentToolResultParseOutcome => {
    let parsedToolResult = toolResult;
    if (typeof parsedToolResult === 'string') {
        const trimmed = parsedToolResult.trim();
        if (!trimmed) {
            return { ok: false, error: new Error('Subagent tool result must not be empty.') };
        }
        try {
            const parsed = parseRequiredJsonText(trimmed);
            parsedToolResult = parsed;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('AgentSubagentToolResult', 'Failed to parse subagent tool result JSON', runtimeError);
            return { ok: false, error: new Error('Subagent tool result JSON is invalid.', { cause: runtimeError }) };
        }
    }
    if (!isPlainObject(parsedToolResult)) {
        return { ok: false, error: new Error('Subagent tool result must be an object.') };
    }
    const subagentValue = parsedToolResult['subagent'];
    if (!isPlainObject(subagentValue)) {
        return { ok: false, error: new Error('Subagent tool result is missing subagent.') };
    }
    const subagentStreamValue = parsedToolResult['subagent_stream'];
    if (!isPlainObject(subagentStreamValue)) {
        return { ok: false, error: new Error('Subagent tool result is missing subagent_stream.') };
    }
    const toolCallsValue = subagentStreamValue['tool_calls'];
    if (!isArray(toolCallsValue)) {
        return { ok: false, error: new Error('Subagent tool result is missing subagent_stream.tool_calls.') };
    }
    const textBlocksValue = subagentStreamValue['text_blocks'];
    if (!isArray(textBlocksValue)) {
        return { ok: false, error: new Error('Subagent tool result is missing subagent_stream.text_blocks.') };
    }
    return {
        ok: true,
        subagentRecord: subagentValue,
        toolCalls: toolCallsValue,
        textBlocks: textBlocksValue
    };
};

const tryResolveAcceptedSubagentPayloadRecord = (toolResult: JsonValue | null | undefined): JsonObject | null => {
    if (!isPlainObject(toolResult) || !isPlainObject(toolResult['subagent']) || !isPlainObject(toolResult['subagentStream'])) return null;
    const streamValue = toolResult['subagentStream'];
    return isArray(streamValue['toolCalls']) && isArray(streamValue['textBlocks']) ? toolResult['subagent'] : null;
};

const buildCanonicalSubagentToolResult = (toolResult: JsonValue | null | undefined): JsonObject => {
    const resolved = tryResolveBackendSubagentToolResultRecord(toolResult);
    if (!resolved.ok) {
        throw resolved.error;
    }
    const subagentValue = resolved.subagentRecord;
    const subagentId = toTrimmedString(subagentValue['subagent_id']);
    const ownerTaskId = readNullableTrimmedStringValue(subagentValue['owner_task_id'], 'Subagent tool result field owner_task_id');
    const mode = readNullableTrimmedStringValue(subagentValue['mode'], 'Subagent tool result field mode');
    const status = toTrimmedString(subagentValue['status']);
    if (!subagentId || !isSubagentModeValue(mode) || !isSubagentStatusValue(status) || ((status === 'accepted' || status === 'running') && ownerTaskId === null)) throw new Error('Subagent tool result identity is invalid.');
    const subagentPayload: JsonObject = { subagentId, ownerTaskId, mode, status };
    const executionType = readRequiredSubagentText(subagentValue['execution_type'], 'execution_type');
    if (executionType !== undefined) {
        if (executionType !== 'subagent') throw new Error('Subagent tool result field execution_type is invalid.');
        subagentPayload['executionType'] = executionType;
    }
    const statusMessage = readOptionalSubagentText(subagentValue['status_message'], 'status_message');
    const displayName = readOptionalSubagentText(subagentValue['display_name'], 'display_name');
    const requestedModel = readOptionalSubagentText(subagentValue['requested_model'], 'requested_model');
    const resultText = readOptionalSubagentText(subagentValue['result_text'], 'result_text');
    const errorMessage = readOptionalSubagentText(subagentValue['error_message'], 'error_message');
    const errorType = readOptionalSubagentText(subagentValue['error_type'], 'error_type');
    if (statusMessage !== undefined) subagentPayload['statusMessage'] = statusMessage;
    if (displayName !== undefined) subagentPayload['displayName'] = displayName;
    if (requestedModel !== undefined) subagentPayload['requestedModel'] = requestedModel;
    if (resultText !== undefined) subagentPayload['resultText'] = resultText;
    if (errorMessage !== undefined) subagentPayload['errorMessage'] = errorMessage;
    if (errorType !== undefined) subagentPayload['errorType'] = errorType;
    const convId = readRequiredSubagentText(subagentValue['conv_id'], 'conv_id');
    const parentTurnId = readRequiredSubagentText(subagentValue['parent_turn_id'], 'parent_turn_id');
    const parentToolCallId = readRequiredSubagentText(subagentValue['parent_tool_call_id'], 'parent_tool_call_id');
    if (convId !== undefined) subagentPayload['convId'] = convId;
    if (parentTurnId !== undefined) subagentPayload['parentTurnId'] = parentTurnId;
    if (parentToolCallId !== undefined) subagentPayload['parentToolCallId'] = parentToolCallId;
    const parentIterationIndex = readSubagentNonNegativeInteger(subagentValue['parent_iteration_index'], 'parent_iteration_index');
    const startedAtMs = readSubagentNonNegativeInteger(subagentValue['started_at_ms'], 'started_at_ms');
    const updatedAtMs = readSubagentNonNegativeInteger(subagentValue['updated_at_ms'], 'updated_at_ms');
    if (parentIterationIndex !== undefined) subagentPayload['parentIterationIndex'] = parentIterationIndex;
    if (startedAtMs !== undefined) subagentPayload['startedAtMs'] = startedAtMs;
    if (updatedAtMs !== undefined) subagentPayload['updatedAtMs'] = updatedAtMs;
    const finishedAtMs = readSubagentFinishedAtMs(subagentValue['finished_at_ms']);
    if (finishedAtMs !== undefined) subagentPayload['finishedAtMs'] = finishedAtMs;
    const tokenUsage = subagentValue['token_usage'];
    if (tokenUsage !== undefined) {
        if (tokenUsage !== null && !isPlainObject(tokenUsage)) throw new Error('Subagent tool result field token_usage is invalid.');
        subagentPayload['tokenUsage'] = tokenUsage;
    }
    return buildCanonicalParentToolCallResultPayload(subagentPayload, decodeSubagentStreamToolCalls(resolved.toolCalls), decodeSubagentStreamTextBlocks(resolved.textBlocks));
};

const buildAcceptedParentToolCallResult = (toolResult: JsonValue | null | undefined): JsonObject | null => {
    try {
        const canonicalResult = buildCanonicalSubagentToolResult(toolResult);
        const subagentPayload = canonicalResult['subagent'];
        if (!isPlainObject(subagentPayload) || subagentPayload['status'] !== 'accepted') return null;
        return canonicalResult;
    } catch (error) {
        errorHandler.warn('AgentSubagentToolResult', 'Failed to canonicalize accepted subagent tool result payload', ensureError(error));
        return null;
    }
};

export { buildAcceptedParentToolCallResult, buildCanonicalSubagentToolResult, buildParentToolCallResultPayload, tryResolveAcceptedSubagentPayloadRecord };
