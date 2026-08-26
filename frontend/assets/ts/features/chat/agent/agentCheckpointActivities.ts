/* SoAI - Chat feature agent checkpoint activities [frontend/assets/ts/features/chat/agent/agentCheckpointActivities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray, isBoolean, isObject } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { readInteger, readString } from '@core/types/payloadValueReaders.ts';
import { parseAgentCodeDiffsFromRecord } from '@core/realtime/eventcontracts/agentparsing/codeDiffs.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { serializeToolArguments } from '@features/chat/agent/agentCheckpointToolParsing.ts';
import type { AgentToolCallStatus } from '@core/chat/agentTypes.ts';
import type { ToolActivityCodeDiff } from '@features/chat/ChatTypes.ts';

type ParsedCheckpointActivity = {
    toolCallId: string;
    toolName: string;
    iterationIndex: number;
    messageIndex: number;
    status: AgentToolCallStatus;
    argumentsValue: string | null;
    result: JsonValue | null;
    codeDiffs: ToolActivityCodeDiff[];
    textLengthBefore: number;
    startedSequence: number;
    lastSequence: number;
    startedAtMs: number | null;
    durationMs: number | null;
};

const VALID_ACTIVITY_STATUSES = {
    pending: true,
    running: true,
    completed: true,
    cancelled: true,
    error: true
} satisfies Record<AgentToolCallStatus, true>;

const isActivityStatus = (value: string | null): value is AgentToolCallStatus => {
    return value !== null && Object.hasOwn(VALID_ACTIVITY_STATUSES, value);
};

const parseCheckpointActivities = (activities: ReadonlyArray<JsonValue | null | undefined>): ParsedCheckpointActivity[] => {
    const parsedActivities: ParsedCheckpointActivity[] = [];
    const seenToolCallIds = new Set<string>();
    for (let index = 0; index < activities.length; index += 1) {
        const value = activities[index];
        if (!isObject(value) || isArray(value)) {
            throw new Error(`Agent turn snapshot activities[${index}] is invalid.`);
        }
        const toolCallIdRaw = readString(value, 'call_id');
        const toolNameRaw = readString(value, 'tool_name');
        const iterationIndex = readInteger(value, 'iteration_index');
        const statusValue = readString(value, 'status');
        const messageIndex = readInteger(value, 'message_index');
        const sequenceIndex = readInteger(value, 'sequence_index');
        const contentIndexBefore = readInteger(value, 'content_index_before');
        const thinkingIndexBefore = readInteger(value, 'thinking_index_before');
        const startedSequence = readInteger(value, 'started_sequence');
        const lastSequence = readInteger(value, 'last_sequence');
        const textLengthBefore = readInteger(value, 'text_length_before');
        const collapsed = value['collapsed'];
        const startedAtMs = value['started_at_ms'] === undefined || value['started_at_ms'] === null ? null : readInteger(value, 'started_at_ms');
        const durationMs = value['duration_ms'] === undefined || value['duration_ms'] === null ? null : readInteger(value, 'duration_ms');
        if (!toolCallIdRaw || !toolNameRaw || iterationIndex === null || iterationIndex < 0 || !isActivityStatus(statusValue) || messageIndex === null || messageIndex < 0 || sequenceIndex === null || sequenceIndex < 0 || contentIndexBefore === null || contentIndexBefore < 0 || thinkingIndexBefore === null || thinkingIndexBefore < 0 || startedSequence === null || startedSequence < 0 || lastSequence === null || lastSequence < startedSequence || textLengthBefore === null || textLengthBefore < 0 || !isBoolean(collapsed)) {
            throw new Error(`Agent turn snapshot activities[${index}] is malformed.`);
        }
        const toolCallId = toolCallIdRaw.trim();
        const toolName = toolNameRaw.trim();
        if (!toolCallId || !toolName) {
            throw new Error(`Agent turn snapshot activities[${index}] contains blank identifiers.`);
        }
        if (seenToolCallIds.has(toolCallId)) {
            throw new Error(`Agent turn snapshot contains duplicate activity id: ${toolCallId}`);
        }
        if (startedAtMs !== null && !isEpochMsNumber(startedAtMs)) {
            throw new Error(`Agent turn snapshot activities[${index}] has invalid started_at_ms.`);
        }
        if (durationMs !== null && durationMs < 0) {
            throw new Error(`Agent turn snapshot activities[${index}] has invalid duration_ms.`);
        }
        seenToolCallIds.add(toolCallId);
        const resultValue = Object.hasOwn(value, 'result') ? (value['result'] ?? null) : null;
        parsedActivities.push({
            toolCallId,
            toolName,
            iterationIndex,
            messageIndex,
            status: statusValue,
            argumentsValue: serializeToolArguments(value['arguments'], toolCallId),
            result: isJsonValue(resultValue) ? resultValue : null,
            codeDiffs: isJsonObject(value) ? (parseAgentCodeDiffsFromRecord(value) ?? []) : [],
            textLengthBefore,
            startedSequence,
            lastSequence,
            startedAtMs,
            durationMs
        });
    }
    return parsedActivities;
};

export { parseCheckpointActivities };
export type { ParsedCheckpointActivity };
