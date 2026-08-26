/* SoAI - Frontend subagent wire decoding [frontend/assets/ts/core/realtime/eventcontracts/agentparsing/subagentFields.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isObject } from '@core/typeGuards.ts';
import { readInteger, readOptionalTrimmedString, readString } from '@core/types/payloadValueReaders.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import type { AgentSubagentEventPayload, AgentSubagentSnapshot, AgentSubagentStatus } from '@core/chat/agentSubagentTypes.ts';
import { toTrimmedString } from '@core/normalize.ts';

const SUBAGENT_EVENT_TYPES: Record<AgentSubagentEventPayload['eventType'], true> = {
    'subagent/spawned': true,
    'subagent/running': true,
    'subagent/completed': true,
    'subagent/error': true,
    'subagent/cancelled': true,
    'subagent/max_iterations': true,
    'subagent/abandoned': true
};

const SUBAGENT_EVENT_STATUS: Record<AgentSubagentEventPayload['eventType'], AgentSubagentStatus> = {
    'subagent/spawned': 'accepted',
    'subagent/running': 'running',
    'subagent/completed': 'completed',
    'subagent/error': 'error',
    'subagent/cancelled': 'cancelled',
    'subagent/max_iterations': 'max_iterations',
    'subagent/abandoned': 'abandoned'
};

const VALID_SUBAGENT_STATUSES: ReadonlySet<string> = new Set<string>(['accepted', 'running', 'completed', 'error', 'cancelled', 'max_iterations', 'abandoned']);
const VALID_SUBAGENT_MODES: ReadonlySet<string> = new Set<string>(['plan', 'execute']);

const VALID_SNAPSHOT_STATUSES: Record<AgentSubagentSnapshot['status'], true> = {
    running: true,
    completed: true,
    error: true,
    cancelled: true,
    'max_iterations': true,
    abandoned: true
};

const isSubagentStatusValue = (value: string): value is AgentSubagentStatus => {
    return VALID_SUBAGENT_STATUSES.has(value);
};

const isSubagentModeValue = (value: string | null): value is AgentSubagentSnapshot['mode'] => {
    return value !== null && VALID_SUBAGENT_MODES.has(value);
};

const isSubagentEventTypeValue = (value: string): value is AgentSubagentEventPayload['eventType'] => {
    return Object.hasOwn(SUBAGENT_EVENT_TYPES, value);
};

const isSubagentSnapshotStatusValue = (value: string | null): value is AgentSubagentSnapshot['status'] => {
    return value !== null && Object.hasOwn(VALID_SNAPSHOT_STATUSES, value);
};

const requireOptionalTokenUsage = (value: JsonValue | null | undefined, errorMessage: string): Record<string, JsonValue | null | undefined> | null => {
    if (value === null) {
        return null;
    }
    if (!isObject(value) || isArray(value)) {
        throw new Error(errorMessage);
    }
    return value;
};

const parseAgentSubagentEventPayload = (data: JsonValue | null | undefined): AgentSubagentEventPayload | null => {
    if (!isObject(data) || isArray(data)) {
        return null;
    }
    const userId = readInteger(data, 'user_id');
    const convIdRaw = readString(data, 'conv_id');
    const parentIterationIndex = readInteger(data, 'parent_iteration_index');
    const executionType = readString(data, 'execution_type');
    const ownerTaskId = readOptionalTrimmedString(data, 'owner_task_id');
    const displayName = readOptionalTrimmedString(data, 'display_name');
    const statusMessage = readOptionalTrimmedString(data, 'status_message');
    const startedAtMs = readInteger(data, 'started_at_ms');
    const updatedAtMs = readInteger(data, 'updated_at_ms');
    const finishedAtRaw = data['finished_at_ms'];
    const finishedAtMs = finishedAtRaw === null ? null : readInteger(data, 'finished_at_ms');
    const requestedModel = readOptionalTrimmedString(data, 'requested_model');
    const resultText = readOptionalTrimmedString(data, 'result_text');
    const resultTextDeltaValue = data['result_text_delta'];
    const resultTextDelta = typeof resultTextDeltaValue === 'string' && resultTextDeltaValue.length > 0 ? resultTextDeltaValue : null;
    const errorMessage = readOptionalTrimmedString(data, 'error_message');
    const errorType = readOptionalTrimmedString(data, 'error_type');
    const tokenUsage = data['token_usage'];

    const convId = toTrimmedString(convIdRaw);
    const parentTurnId = readOptionalTrimmedString(data, 'parent_turn_id') ?? '';
    const parentToolCallId = readOptionalTrimmedString(data, 'parent_tool_call_id') ?? '';
    const subagentId = readOptionalTrimmedString(data, 'subagent_id') ?? '';
    const mode = readOptionalTrimmedString(data, 'mode') ?? '';
    const eventType = readOptionalTrimmedString(data, 'event_type') ?? '';
    const status = readOptionalTrimmedString(data, 'status') ?? '';

    if (userId === null || userId <= 0 || !convId || !parentTurnId || !parentToolCallId || parentIterationIndex === null || parentIterationIndex < 0 || !subagentId || executionType !== 'subagent' || !VALID_SUBAGENT_MODES.has(mode) || startedAtMs === null || !isEpochMsNumber(startedAtMs) || updatedAtMs === null || !isEpochMsNumber(updatedAtMs) || updatedAtMs < startedAtMs || (finishedAtMs !== null && (!isEpochMsNumber(finishedAtMs) || finishedAtMs < updatedAtMs)) || ((status === 'accepted' || status === 'running') && finishedAtMs !== null) || ((status === 'accepted' || status === 'running') && ownerTaskId === null) || (status !== 'accepted' && status !== 'running' && finishedAtMs === null) || !isSubagentEventTypeValue(eventType) || !isSubagentStatusValue(status) || SUBAGENT_EVENT_STATUS[eventType] !== status) {
        return null;
    }

    if (tokenUsage !== null && (!isObject(tokenUsage) || isArray(tokenUsage))) {
        return null;
    }

    return {
        userId,
        convId,
        parentTurnId,
        parentToolCallId,
        parentIterationIndex,
        subagentId,
        executionType,
        ownerTaskId,
        displayName,
        mode: mode === 'plan' ? 'plan' : 'execute',
        statusMessage,
        startedAtMs,
        updatedAtMs,
        finishedAtMs,
        requestedModel,
        resultText,
        resultTextDelta,
        errorMessage,
        errorType,
        tokenUsage,
        eventType,
        status
    };
};

const parseAgentSubagentSnapshotRecord = (value: JsonValue | null | undefined): AgentSubagentSnapshot | null => {
    if (!isObject(value) || isArray(value)) {
        return null;
    }
    const subagentId = readOptionalTrimmedString(value, 'subagent_id');
    const executionType = readOptionalTrimmedString(value, 'execution_type');
    const ownerTaskId = readOptionalTrimmedString(value, 'owner_task_id');
    const status = readString(value, 'status');
    const statusMessage = readOptionalTrimmedString(value, 'status_message');
    const mode = readString(value, 'mode');
    const displayName = readOptionalTrimmedString(value, 'display_name');
    const parentTurnId = readOptionalTrimmedString(value, 'parent_turn_id');
    const parentToolCallId = readOptionalTrimmedString(value, 'parent_tool_call_id');
    const parentIterationIndex = readInteger(value, 'parent_iteration_index');
    const startedAtMs = readInteger(value, 'started_at_ms');
    const updatedAtMs = readInteger(value, 'updated_at_ms');
    const finishedAtRaw = value['finished_at_ms'];
    const finishedAtMs = finishedAtRaw === null ? null : readInteger(value, 'finished_at_ms');
    const requestedModel = readOptionalTrimmedString(value, 'requested_model');
    const resultText = readOptionalTrimmedString(value, 'result_text');
    const errorMessage = readOptionalTrimmedString(value, 'error_message');
    const errorType = readOptionalTrimmedString(value, 'error_type');

    if (subagentId === null || executionType !== 'subagent' || parentTurnId === null || parentToolCallId === null || parentIterationIndex === null || parentIterationIndex < 0 || startedAtMs === null || !isEpochMsNumber(startedAtMs) || updatedAtMs === null || !isEpochMsNumber(updatedAtMs) || updatedAtMs < startedAtMs || (finishedAtMs !== null && (!isEpochMsNumber(finishedAtMs) || finishedAtMs < updatedAtMs)) || (status === 'running' && finishedAtMs !== null) || (status !== 'running' && finishedAtMs === null) || (status === 'running' && ownerTaskId === null) || !isSubagentSnapshotStatusValue(status) || !isSubagentModeValue(mode)) {
        return null;
    }

    const tokenUsageValue = value['token_usage'];
    if (tokenUsageValue !== null && (!isObject(tokenUsageValue) || isArray(tokenUsageValue))) {
        return null;
    }

    return {
        subagentId,
        executionType,
        ownerTaskId,
        status,
        statusMessage,
        mode: mode === 'plan' ? 'plan' : 'execute',
        displayName,
        parentTurnId,
        parentToolCallId,
        parentIterationIndex,
        startedAtMs,
        updatedAtMs,
        finishedAtMs,
        requestedModel,
        resultText,
        errorMessage,
        errorType,
        tokenUsage: tokenUsageValue
    };
};

export { isSubagentModeValue, isSubagentStatusValue, parseAgentSubagentEventPayload, parseAgentSubagentSnapshotRecord, requireOptionalTokenUsage };
