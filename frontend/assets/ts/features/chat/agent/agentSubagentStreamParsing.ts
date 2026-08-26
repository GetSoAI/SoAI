/* SoAI - Chat feature agent subagent stream parsing [frontend/assets/ts/features/chat/agent/agentSubagentStreamParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseCodeDiffArrayLenient } from '@core/chat/codeDiffParsing.ts';
import { isBoolean, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

const readRequiredText = (value: JsonValue | undefined, label: string): string => {
    if (!isString(value) || !value.trim()) {
        throw new Error(`${label} must be a non-empty string.`);
    }
    return value.trim();
};

const readRequiredNonNegativeInteger = (value: JsonValue | undefined, label: string): number => {
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
        throw new Error(`${label} must be a non-negative integer.`);
    }
    return value;
};

const decodeSubagentStreamToolCall = (value: JsonValue | null, index: number): JsonObject => {
    if (!isJsonObject(value)) {
        throw new Error(`Subagent stream tool call ${index} must be an object.`);
    }
    const decoded: JsonObject = {
        callId: readRequiredText(value['call_id'], `Subagent stream tool call ${index}.call_id`),
        toolName: readRequiredText(value['tool_name'], `Subagent stream tool call ${index}.tool_name`),
        status: readRequiredText(value['status'], `Subagent stream tool call ${index}.status`),
        sequenceIndex: readRequiredNonNegativeInteger(value['sequence_index'], `Subagent stream tool call ${index}.sequence_index`),
        streamOrder: readRequiredNonNegativeInteger(value['stream_order'], `Subagent stream tool call ${index}.stream_order`),
        contentIndexBefore: readRequiredNonNegativeInteger(value['content_index_before'], `Subagent stream tool call ${index}.content_index_before`),
        startedAtMs: readRequiredNonNegativeInteger(value['started_at_ms'], `Subagent stream tool call ${index}.started_at_ms`)
    };
    if (isJsonValue(value['arguments'])) decoded['arguments'] = value['arguments'];
    if (isJsonValue(value['result'])) decoded['result'] = value['result'];
    const codeDiffs = parseCodeDiffArrayLenient(value['code_diffs']);
    if (codeDiffs !== null) {
        const serializedCodeDiffs: JsonObject[] = codeDiffs.map((entry) => ({
            path: entry.path,
            operation: entry.operation,
            diff: entry.diff,
            truncated: entry.truncated
        }));
        decoded['codeDiffs'] = serializedCodeDiffs;
    }
    if (isString(value['error'])) decoded['error'] = value['error'];
    if (isBoolean(value['collapsed'])) decoded['collapsed'] = value['collapsed'];
    if (value['duration_ms'] !== undefined && value['duration_ms'] !== null) {
        decoded['durationMs'] = readRequiredNonNegativeInteger(value['duration_ms'], `Subagent stream tool call ${index}.duration_ms`);
    }
    return decoded;
};

const decodeSubagentStreamTextBlock = (value: JsonValue | null, index: number): JsonObject => {
    if (!isJsonObject(value)) {
        throw new Error(`Subagent stream text block ${index} must be an object.`);
    }
    return {
        text: readRequiredText(value['text'], `Subagent stream text block ${index}.text`),
        startedAtMs: readRequiredNonNegativeInteger(value['started_at_ms'], `Subagent stream text block ${index}.started_at_ms`),
        blockIndex: readRequiredNonNegativeInteger(value['block_index'], `Subagent stream text block ${index}.block_index`),
        streamOrder: readRequiredNonNegativeInteger(value['stream_order'], `Subagent stream text block ${index}.stream_order`)
    };
};

const decodeSubagentStreamToolCalls = (values: ReadonlyArray<JsonValue | null>): JsonObject[] => values.map((value, index) => decodeSubagentStreamToolCall(value, index));
const decodeSubagentStreamTextBlocks = (values: ReadonlyArray<JsonValue | null>): JsonObject[] => values.map((value, index) => decodeSubagentStreamTextBlock(value, index));

export { decodeSubagentStreamTextBlocks, decodeSubagentStreamToolCalls };
