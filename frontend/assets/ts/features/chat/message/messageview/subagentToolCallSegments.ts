/* SoAI - Chat feature subagent tool call segments [frontend/assets/ts/features/chat/message/messageview/subagentToolCallSegments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseCodeDiffArrayLenient } from '@core/chat/codeDiffParsing.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import { readNonNegativeIntegerOrNullValue } from '@core/types/payloadNumberReaders.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { InlineToolActivitySegment } from '@features/chat/message/messageSegments.ts';

const SUBAGENT_CHILD_CALL_ID_PREFIX = 'subagent-tool-call:';

const isToolStatus = (value: JsonValue | undefined): value is InlineToolActivitySegment['status'] => {
    return value === 'pending' || value === 'running' || value === 'completed' || value === 'cancelled' || value === 'error';
};

const buildSubagentChildToolCallId = (parentCallId: string, childCallId: string): string => {
    return `${SUBAGENT_CHILD_CALL_ID_PREFIX}${encodeURIComponent(parentCallId)}:${encodeURIComponent(childCallId)}`;
};

const isSubagentChildToolCallId = (callId: string): boolean => {
    return callId.startsWith(SUBAGENT_CHILD_CALL_ID_PREFIX);
};

const cloneJsonObjectWithBoolean = (source: JsonObject, key: string, value: boolean): JsonObject => {
    const result: JsonObject = {};
    for (const [entryKey, entryValue] of Object.entries(source)) {
        result[entryKey] = entryValue;
    }
    result[key] = value;
    return result;
};

const cloneJsonObjectWithValue = (source: JsonObject, key: string, value: JsonValue): JsonObject => {
    const result: JsonObject = {};
    for (const [entryKey, entryValue] of Object.entries(source)) {
        result[entryKey] = entryValue;
    }
    result[key] = value;
    return result;
};

const buildSubagentChildToolSegment = (parentCallId: string, value: JsonValue, identity: { assistantTurnTimestamp: number; modelVariantIndex: number }): InlineToolActivitySegment => {
    if (!isJsonObject(value)) {
        throw new Error('Subagent tool result contains an invalid child tool call.');
    }
    const childCallId = value['callId'];
    const toolName = value['toolName'];
    const status = value['status'];
    if (!isString(childCallId) || !childCallId.trim()) {
        throw new Error('Subagent tool result contains a child tool call without call_id.');
    }
    if (!isString(toolName) || !toolName.trim()) {
        throw new Error('Subagent tool result contains a child tool call without tool_name.');
    }
    if (!isToolStatus(status)) {
        throw new Error('Subagent tool result contains a child tool call with invalid status.');
    }
    const syntheticCallId = buildSubagentChildToolCallId(parentCallId, childCallId.trim());
    const sequenceIndex = readNonNegativeIntegerOrNullValue(value['sequenceIndex']);
    if (sequenceIndex === null) {
        throw new Error('Subagent tool result contains a child tool call without sequence_index.');
    }
    const streamOrder = readNonNegativeIntegerOrNullValue(value['streamOrder']);
    if (streamOrder === null) {
        throw new Error('Subagent tool result contains a child tool call without stream_order.');
    }
    const contentIndexBefore = readNonNegativeIntegerOrNullValue(value['contentIndexBefore']);
    if (contentIndexBefore === null) {
        throw new Error('Subagent tool result contains a child tool call without content_index_before.');
    }
    const segment: InlineToolActivitySegment = {
        type: 'inline_tool_activity',
        callId: syntheticCallId,
        toolName: toolName.trim(),
        status,
        contentIndexBefore: contentIndexBefore,
        assistantTurnAtMs: identity.assistantTurnTimestamp,
        modelVariantIndex: identity.modelVariantIndex,
        signatureSequence: sequenceIndex,
        streamOrder: streamOrder,
        collapsed: isBoolean(value['collapsed']) ? value['collapsed'] : true
    };
    if (isJsonValue(value['arguments'])) {
        segment.inputArguments = value['arguments'];
    }
    if (isJsonValue(value['result'])) {
        segment.result = value['result'];
    }
    const codeDiffs = parseCodeDiffArrayLenient(value['codeDiffs']);
    if (codeDiffs !== null) {
        segment.codeDiffs = codeDiffs;
    }
    if (isString(value['error']) && value['error'].trim()) {
        segment.error = value['error'].trim();
    }
    const durationMs = readNonNegativeIntegerOrNullValue(value['durationMs']);
    if (durationMs !== null) {
        segment.durationMs = durationMs;
    }
    const startedAtMs = readNonNegativeIntegerOrNullValue(value['startedAtMs']);
    if (startedAtMs === null) {
        throw new Error('Subagent tool result contains a child tool call without started_at_ms.');
    }
    segment.startedAtMs = startedAtMs;
    return segment;
};

const applySubagentChildToolCollapsedOverrides = (payload: JsonValue, parentCallId: string, collapsedOverrides: Map<string, boolean>): JsonValue => {
    if (collapsedOverrides.size === 0) {
        return payload;
    }
    if (!isJsonObject(payload)) {
        return payload;
    }
    const resultRecord: JsonObject = payload;
    const streamValue = resultRecord['subagentStream'];
    if (!isJsonObject(streamValue)) {
        return payload;
    }
    const streamRecord: JsonObject = streamValue;
    const toolCalls = streamRecord['toolCalls'];
    if (!isJsonArray(toolCalls) || toolCalls.length === 0) {
        return payload;
    }
    let changed = false;
    const nextToolCalls: JsonValue[] = toolCalls.map((entry) => {
        if (!isJsonObject(entry)) {
            return entry;
        }
        const childCallId = entry['callId'];
        if (!isString(childCallId) || !childCallId.trim()) {
            return entry;
        }
        const override = collapsedOverrides.get(buildSubagentChildToolCallId(parentCallId, childCallId.trim()));
        if (override === undefined || entry['collapsed'] === override) {
            return entry;
        }
        changed = true;
        return cloneJsonObjectWithBoolean(entry, 'collapsed', override);
    });
    if (!changed) {
        return payload;
    }
    return cloneJsonObjectWithValue(resultRecord, 'subagentStream', cloneJsonObjectWithValue(streamRecord, 'toolCalls', nextToolCalls));
};

export { applySubagentChildToolCollapsedOverrides, buildSubagentChildToolCallId, buildSubagentChildToolSegment, isSubagentChildToolCallId };
