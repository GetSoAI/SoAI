/* SoAI - Frontend chat agent API boundary contracts [frontend/assets/ts/core/api/contracts/chatAgentContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { isEpochMsNumber } from '@core/time/epochMs.ts';
import { readRequiredJsonObjectArrayValue, readNullableJsonObjectValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readNullableFiniteIntegerValue, readNullableNonNegativeIntegerValue, readRequiredNonNegativeIntegerValue, readRequiredPositiveIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';

type AgentPlanStepStatus = 'pending' | 'in_progress' | 'completed';
type AgentTurnStatus = 'running' | 'completed' | 'error' | 'cancelled' | 'max_iterations' | 'abandoned';
interface AgentPlanStep {
    step: string;
    status: AgentPlanStepStatus;
}
interface AgentSubagentSnapshot {
    subagentId: string;
    executionType: string;
    ownerTaskId: string | null;
    status: AgentTurnStatus;
    statusMessage: string | null;
    mode: 'plan' | 'execute';
    displayName: string | null;
    convId: string;
    parentTurnId: string;
    parentToolCallId: string;
    parentIterationIndex: number;
    startedAtMs: number;
    updatedAtMs: number;
    finishedAtMs: number | null;
    requestedModel: string | null;
    resultText: string | null;
    errorMessage: string | null;
    errorType: string | null;
    tokenUsage: JsonObject | null;
}
interface AgentCheckpointResponse {
    convId: string;
    userId: number;
    turnId: string;
    executionType: string;
    turnScope: 'root' | 'subagent';
    parentTurnId: string | null;
    parentToolCallId: string | null;
    parentIterationIndex: number | null;
    displayName: string | null;
    requestedModel: string | null;
    ownerTaskId: string | null;
    executionToken: string;
    serverBootId: string;
    status: AgentTurnStatus;
    statusMessage: string | null;
    errorMessage: string | null;
    errorType: string | null;
    mode: AgentMode;
    maxIterations: number;
    iterationIndex: number;
    sequence: number;
    turnCancellationId: string | null;
    activeInferenceCancellationId: string | null;
    assistantText: string | null;
    toolCalls: JsonObject[];
    toolResults: JsonValue[];
    activities: JsonObject[];
    reachedMaxIterations: boolean;
    tokenUsage: JsonObject | null;
    todoRevision: number;
    todoExplanation: string | null;
    todo: AgentPlanStep[];
    startedAtMs: number;
    updatedAtMs: number;
    finishedAtMs: number | null;
    subagents: AgentSubagentSnapshot[];
}
interface AgentTodoStateResponse {
    convId: string;
    userId: number;
    revision: number;
    updatedAtMs: number | null;
    explanation: string | null;
    todo: AgentPlanStep[];
}
interface AgentPlanStateResponse {
    convId: string;
    userId: number;
    revision: number;
    updatedAtMs: number | null;
    title: string | null;
    markdown: string | null;
}
interface AgentTurnCancelResponse {
    convId: string;
    turnId: string;
    iterationIndex: number;
    sequence: number;
    status: 'already_terminal' | 'cancellation_requested';
    terminalStatus: string | null;
    cancellationIds: string[] | null;
    terminatedShellSessions: number | null;
}
interface AgentTurnCancelRequest {
    forcePendingSteers: boolean;
}
interface AgentShellToolStopResponse {
    convId: string;
    toolCallId: string;
    status: 'already_terminal' | 'cancellation_requested';
    terminalStatus: 'completed' | 'cancelled' | 'error' | null;
    ownerTaskId: string | null;
}
interface AgentMessageWriteResponse {
    lastModifiedAtMs: number;
    messageCount: number;
    messages: JsonObject[];
}
interface AgentTodoWriteRequest {
    todo: AgentPlanStep[];
    explanation: string | null;
}
interface AgentPlanWriteRequest {
    title: string | null;
    markdown: string;
}

const PLAN_STEP_STATUSES: readonly AgentPlanStepStatus[] = ['pending', 'in_progress', 'completed'];
const TURN_STATUSES: readonly AgentTurnStatus[] = ['running', 'completed', 'error', 'cancelled', 'max_iterations', 'abandoned'];
const AGENT_MODES: readonly AgentMode[] = ['chat', 'plan', 'execute'];

const decodeEpoch = (value: JsonValue | undefined, label: string): number => {
    const result = readRequiredNonNegativeIntegerValue(value, label);
    if (!isEpochMsNumber(result)) throw new TypeError(`${label} must be an epoch timestamp`);
    return result;
};

const decodeNullableEpoch = (value: JsonValue | undefined, label: string): number | null => {
    if (value === null || value === undefined) return null;
    return decodeEpoch(value, label);
};

const serializeAgentTodoWriteRequest = (request: AgentTodoWriteRequest): JsonObject => ({
    todo: request.todo.map((entry) => ({ step: entry.step, status: entry.status })),
    explanation: request.explanation
});

const serializeAgentPlanWriteRequest = (request: AgentPlanWriteRequest): JsonObject => ({
    title: request.title,
    markdown: request.markdown
});

const serializeAgentTurnCancelRequest = (request: AgentTurnCancelRequest): JsonObject => ({
    'force_pending_steers': request.forcePendingSteers
});

const decodePlanSteps = (value: JsonValue | undefined, label: string): AgentPlanStep[] => {
    if (!Array.isArray(value)) throw new TypeError(`${label} must be an array`);
    return value.map((entry, index) => {
        const entryLabel = `${label}[${String(index)}]`;
        const record = requireRecord(entry, entryLabel);
        return { step: readRequiredTrimmedStringValue(record['step'], `${entryLabel}.step`), status: readRequiredEnumValue(record['status'], `${entryLabel}.status`, PLAN_STEP_STATUSES) };
    });
};

const decodeSubagent = (value: JsonValue, index: number): AgentSubagentSnapshot => {
    const label = `Agent checkpoint subagents[${String(index)}]`;
    const record = requireRecord(value, label);
    const startedAtMs = decodeEpoch(record['started_at_ms'], `${label}.started_at_ms`);
    const updatedAtMs = decodeEpoch(record['updated_at_ms'], `${label}.updated_at_ms`);
    const finishedAtMs = decodeNullableEpoch(record['finished_at_ms'], `${label}.finished_at_ms`);
    const status = readRequiredEnumValue(record['status'], `${label}.status`, TURN_STATUSES);
    if (updatedAtMs < startedAtMs || (finishedAtMs !== null && finishedAtMs < updatedAtMs)) throw new TypeError(`${label} timestamps are inconsistent`);
    if ((status === 'running' && finishedAtMs !== null) || (status !== 'running' && finishedAtMs === null)) throw new TypeError(`${label} terminal timestamp is inconsistent`);
    return {
        subagentId: readRequiredTrimmedStringValue(record['subagent_id'], `${label}.subagent_id`),
        executionType: readRequiredTrimmedStringValue(record['execution_type'], `${label}.execution_type`),
        ownerTaskId: readNullableTrimmedStringValue(record['owner_task_id'], `${label}.owner_task_id`),
        status,
        statusMessage: readNullableTrimmedStringValue(record['status_message'], `${label}.status_message`),
        mode: readRequiredEnumValue(record['mode'], `${label}.mode`, ['plan', 'execute']),
        displayName: readNullableTrimmedStringValue(record['display_name'], `${label}.display_name`),
        convId: readRequiredTrimmedStringValue(record['conv_id'], `${label}.conv_id`),
        parentTurnId: readRequiredTrimmedStringValue(record['parent_turn_id'], `${label}.parent_turn_id`),
        parentToolCallId: readRequiredTrimmedStringValue(record['parent_tool_call_id'], `${label}.parent_tool_call_id`),
        parentIterationIndex: readRequiredNonNegativeIntegerValue(record['parent_iteration_index'], `${label}.parent_iteration_index`),
        startedAtMs: startedAtMs,
        updatedAtMs: updatedAtMs,
        finishedAtMs: finishedAtMs,
        requestedModel: readNullableTrimmedStringValue(record['requested_model'], `${label}.requested_model`),
        resultText: readNullableTrimmedStringValue(record['result_text'], `${label}.result_text`),
        errorMessage: readNullableTrimmedStringValue(record['error_message'], `${label}.error_message`),
        errorType: readNullableTrimmedStringValue(record['error_type'], `${label}.error_type`),
        tokenUsage: readNullableJsonObjectValue(record['token_usage'], `${label}.token_usage`)
    };
};

const decodeToolResults = (value: JsonValue | undefined): JsonValue[] => {
    if (!Array.isArray(value)) throw new TypeError('Agent checkpoint.tool_results must be an array');
    return [...value];
};

const decodeAgentCheckpoint = (value: ApiResponsePayload): AgentCheckpointResponse => {
    const record = requireRecord(value, 'Agent checkpoint');
    const status = readRequiredEnumValue(record['status'], 'Agent checkpoint.status', TURN_STATUSES);
    const turnScope = readRequiredEnumValue(record['turn_scope'], 'Agent checkpoint.turn_scope', ['root', 'subagent']);
    const parentTurnId = readNullableTrimmedStringValue(record['parent_turn_id'], 'Agent checkpoint.parent_turn_id');
    const parentToolCallId = readNullableTrimmedStringValue(record['parent_tool_call_id'], 'Agent checkpoint.parent_tool_call_id');
    const parentIterationIndex = readNullableFiniteIntegerValue(record['parent_iteration_index'], 'Agent checkpoint.parent_iteration_index');
    const ownerTaskId = readNullableTrimmedStringValue(record['owner_task_id'], 'Agent checkpoint.owner_task_id');
    if (parentIterationIndex !== null && parentIterationIndex < 0) throw new TypeError('Agent checkpoint.parent_iteration_index must be non-negative');
    if (turnScope === 'root' && (parentTurnId !== null || parentToolCallId !== null || parentIterationIndex !== null)) throw new TypeError('Agent checkpoint root parent fields must be null');
    if (turnScope === 'subagent' && (parentTurnId === null || parentToolCallId === null || parentIterationIndex === null || ownerTaskId === null)) throw new TypeError('Agent checkpoint subagent parent fields are required');
    const startedAtMs = decodeEpoch(record['started_at_ms'], 'Agent checkpoint.started_at_ms');
    const updatedAtMs = decodeEpoch(record['updated_at_ms'], 'Agent checkpoint.updated_at_ms');
    const finishedAtMs = decodeNullableEpoch(record['finished_at_ms'], 'Agent checkpoint.finished_at_ms');
    if (updatedAtMs < startedAtMs || (finishedAtMs !== null && finishedAtMs < updatedAtMs)) throw new TypeError('Agent checkpoint timestamps are inconsistent');
    if ((status === 'running' && finishedAtMs !== null) || (status !== 'running' && finishedAtMs === null)) throw new TypeError('Agent checkpoint terminal timestamp is inconsistent');
    return {
        convId: readRequiredTrimmedStringValue(record['conv_id'], 'Agent checkpoint.conv_id'),
        userId: readRequiredPositiveIntegerValue(record['user_id'], 'Agent checkpoint.user_id'),
        turnId: readRequiredTrimmedStringValue(record['turn_id'], 'Agent checkpoint.turn_id'),
        executionType: readRequiredTrimmedStringValue(record['execution_type'], 'Agent checkpoint.execution_type'),
        turnScope: turnScope,
        parentTurnId: parentTurnId,
        parentToolCallId: parentToolCallId,
        parentIterationIndex: parentIterationIndex,
        displayName: readNullableTrimmedStringValue(record['display_name'], 'Agent checkpoint.display_name'),
        requestedModel: readNullableTrimmedStringValue(record['requested_model'], 'Agent checkpoint.requested_model'),
        ownerTaskId: ownerTaskId,
        executionToken: readRequiredTrimmedStringValue(record['execution_token'], 'Agent checkpoint.execution_token'),
        serverBootId: readRequiredTrimmedStringValue(record['server_boot_id'], 'Agent checkpoint.server_boot_id'),
        status,
        statusMessage: readNullableTrimmedStringValue(record['status_message'], 'Agent checkpoint.status_message'),
        errorMessage: readNullableTrimmedStringValue(record['error_message'], 'Agent checkpoint.error_message'),
        errorType: readNullableTrimmedStringValue(record['error_type'], 'Agent checkpoint.error_type'),
        mode: readRequiredEnumValue(record['mode'], 'Agent checkpoint.mode', AGENT_MODES),
        maxIterations: readRequiredPositiveIntegerValue(record['max_iterations'], 'Agent checkpoint.max_iterations'),
        iterationIndex: readRequiredNonNegativeIntegerValue(record['iteration_index'], 'Agent checkpoint.iteration_index'),
        sequence: readRequiredNonNegativeIntegerValue(record['sequence'], 'Agent checkpoint.sequence'),
        turnCancellationId: readNullableTrimmedStringValue(record['turn_cancellation_id'], 'Agent checkpoint.turn_cancellation_id'),
        activeInferenceCancellationId: readNullableTrimmedStringValue(record['active_inference_cancellation_id'], 'Agent checkpoint.active_inference_cancellation_id'),
        assistantText: readNullableTrimmedStringValue(record['assistant_text'], 'Agent checkpoint.assistant_text'),
        toolCalls: readRequiredJsonObjectArrayValue(record['tool_calls'], 'Agent checkpoint.tool_calls'),
        toolResults: decodeToolResults(record['tool_results']),
        activities: readRequiredJsonObjectArrayValue(record['activities'], 'Agent checkpoint.activities'),
        reachedMaxIterations: readRequiredBooleanValue(record['reached_max_iterations'], 'Agent checkpoint.reached_max_iterations'),
        tokenUsage: readNullableJsonObjectValue(record['token_usage'], 'Agent checkpoint.token_usage'),
        todoRevision: readRequiredNonNegativeIntegerValue(record['todo_revision'], 'Agent checkpoint.todo_revision'),
        todoExplanation: readNullableTrimmedStringValue(record['todo_explanation'], 'Agent checkpoint.todo_explanation'),
        todo: decodePlanSteps(record['todo'], 'Agent checkpoint.todo'),
        startedAtMs: startedAtMs,
        updatedAtMs: updatedAtMs,
        finishedAtMs: finishedAtMs,
        subagents: readRequiredJsonObjectArrayValue(record['subagents'], 'Agent checkpoint.subagents').map(decodeSubagent)
    };
};

const decodeAgentTodoState = (value: ApiResponsePayload): AgentTodoStateResponse => {
    const record = requireRecord(value, 'Agent todo state');
    return { convId: readRequiredTrimmedStringValue(record['conv_id'], 'Agent todo state.conv_id'), userId: readRequiredPositiveIntegerValue(record['user_id'], 'Agent todo state.user_id'), revision: readRequiredNonNegativeIntegerValue(record['revision'], 'Agent todo state.revision'), updatedAtMs: decodeNullableEpoch(record['updated_at_ms'], 'Agent todo state.updated_at_ms'), explanation: readNullableTrimmedStringValue(record['explanation'], 'Agent todo state.explanation'), todo: decodePlanSteps(record['todo'], 'Agent todo state.todo') };
};

const decodeAgentPlanState = (value: ApiResponsePayload): AgentPlanStateResponse => {
    const record = requireRecord(value, 'Agent plan state');
    return { convId: readRequiredTrimmedStringValue(record['conv_id'], 'Agent plan state.conv_id'), userId: readRequiredPositiveIntegerValue(record['user_id'], 'Agent plan state.user_id'), revision: readRequiredNonNegativeIntegerValue(record['revision'], 'Agent plan state.revision'), updatedAtMs: decodeNullableEpoch(record['updated_at_ms'], 'Agent plan state.updated_at_ms'), title: readNullableTrimmedStringValue(record['title'], 'Agent plan state.title'), markdown: readNullableTrimmedStringValue(record['markdown'], 'Agent plan state.markdown') };
};

const decodeAgentTurnCancel = (value: ApiResponsePayload): AgentTurnCancelResponse => {
    const record = requireRecord(value, 'Agent turn cancel response');
    const cancellationIds = record['cancellation_ids'] === null || record['cancellation_ids'] === undefined ? null : readRequiredStringArrayValue(record['cancellation_ids'], 'Agent turn cancel response.cancellation_ids');
    return { convId: readRequiredTrimmedStringValue(record['conv_id'], 'Agent turn cancel response.conv_id'), turnId: readRequiredTrimmedStringValue(record['turn_id'], 'Agent turn cancel response.turn_id'), iterationIndex: readRequiredNonNegativeIntegerValue(record['iteration_index'], 'Agent turn cancel response.iteration_index'), sequence: readRequiredNonNegativeIntegerValue(record['sequence'], 'Agent turn cancel response.sequence'), status: readRequiredEnumValue(record['status'], 'Agent turn cancel response.status', ['already_terminal', 'cancellation_requested']), terminalStatus: readNullableTrimmedStringValue(record['terminal_status'], 'Agent turn cancel response.terminal_status'), cancellationIds: cancellationIds, terminatedShellSessions: readNullableNonNegativeIntegerValue(record['terminated_shell_sessions'], 'Agent turn cancel response.terminated_shell_sessions') };
};

const decodeAgentShellToolStop = (value: ApiResponsePayload): AgentShellToolStopResponse => {
    const record = requireRecord(value, 'Agent shell stop response');
    const terminalStatus = record['terminal_status'] === null || record['terminal_status'] === undefined ? null : readRequiredEnumValue(record['terminal_status'], 'Agent shell stop response.terminal_status', ['completed', 'cancelled', 'error']);
    return { convId: readRequiredTrimmedStringValue(record['conv_id'], 'Agent shell stop response.conv_id'), toolCallId: readRequiredTrimmedStringValue(record['tool_call_id'], 'Agent shell stop response.tool_call_id'), status: readRequiredEnumValue(record['status'], 'Agent shell stop response.status', ['already_terminal', 'cancellation_requested']), terminalStatus: terminalStatus, ownerTaskId: readNullableTrimmedStringValue(record['owner_task_id'], 'Agent shell stop response.owner_task_id') };
};

const decodeAgentMessageWrite = (value: ApiResponsePayload): AgentMessageWriteResponse => {
    const record = requireRecord(value, 'Agent message write response');
    return { lastModifiedAtMs: decodeEpoch(record['last_modified_at_ms'], 'Agent message write response.last_modified_at_ms'), messageCount: readRequiredNonNegativeIntegerValue(record['message_count'], 'Agent message write response.message_count'), messages: readRequiredJsonObjectArrayValue(record['messages'], 'Agent message write response.messages') };
};

const serializeAgentCompactionStartRequest = (model: string): JsonObject => ({ model });
const serializeAgentCompactionRegenerateRequest = (payload: { assistantTurnAtMs: number; clientId: string; clientRequestId: string; expectedLastModifiedAtMs: number }): JsonObject => ({
    'assistant_turn_at_ms': payload.assistantTurnAtMs,
    'client_id': payload.clientId,
    'client_request_id': payload.clientRequestId,
    'expected_last_modified_at_ms': payload.expectedLastModifiedAtMs
});
const serializeAgentCompactionBoundaryRemovalRequest = (request: { assistantTurnAtMs: number; modelVariantIndex: number; toolCallId: string; expectedLastModifiedAtMs: number }): JsonObject => ({ 'assistant_turn_at_ms': request.assistantTurnAtMs, 'model_variant_index': request.modelVariantIndex, 'tool_call_id': request.toolCallId, 'expected_last_modified_at_ms': request.expectedLastModifiedAtMs });
const serializeAgentShellToolStopRequest = (assistantTurnAtMs: number, modelVariantIndex: number, toolCallId: string): JsonObject => ({ 'assistant_turn_at_ms': assistantTurnAtMs, 'model_variant_index': modelVariantIndex, 'tool_call_id': toolCallId });

export { decodeAgentCheckpoint, decodeAgentMessageWrite, decodeAgentPlanState, decodeAgentShellToolStop, decodeAgentTodoState, decodeAgentTurnCancel, serializeAgentCompactionBoundaryRemovalRequest, serializeAgentCompactionRegenerateRequest, serializeAgentCompactionStartRequest, serializeAgentPlanWriteRequest, serializeAgentShellToolStopRequest, serializeAgentTodoWriteRequest, serializeAgentTurnCancelRequest };
export type { AgentCheckpointResponse, AgentMessageWriteResponse, AgentMode, AgentPlanStateResponse, AgentPlanStep, AgentPlanStepStatus, AgentPlanWriteRequest, AgentShellToolStopResponse, AgentSubagentSnapshot, AgentTodoStateResponse, AgentTodoWriteRequest, AgentTurnCancelRequest, AgentTurnCancelResponse, AgentTurnStatus };
