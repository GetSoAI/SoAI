/* SoAI - Shared frontend API contract boundary task contracts [frontend/assets/ts/core/api/contracts/taskContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { readRequiredNonNegativeIntegerValue, readNullableFiniteNumberValue, readNullableNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { readNullableJsonObjectValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface TaskResponse {
    taskId: string;
    taskType: string;
    status: string;
    userId: number;
    ownerId: string;
    ownerType: string;
    createdAtMs: number;
    updatedAtMs: number;
    completedAtMs: number | null;
    progressCurrent: number | null;
    progressTotal: number | null;
    progressPercent: number | null;
    statusMessage: string | null;
    metadata: JsonObject;
    result: JsonObject | null;
    errorCode: number | null;
    errorType: string | null;
    errorMessage: string | null;
}

interface TaskListResponse {
    tasks: TaskResponse[];
    totalCount: number;
    limit: number;
    offset: number;
}

const decodeTaskResponse = (value: ApiResponsePayload | JsonValue): TaskResponse => {
    const record = requireRecord(value, 'Task response');
    return {
        taskId: readRequiredTrimmedString(record, 'task_id', 'Task response.task_id'),
        taskType: readRequiredTrimmedString(record, 'task_type', 'Task response.task_type'),
        status: readRequiredTrimmedString(record, 'status', 'Task response.status'),
        userId: readRequiredNonNegativeIntegerValue(record['user_id'], 'Task response.user_id'),
        ownerId: readRequiredTrimmedString(record, 'owner_id', 'Task response.owner_id'),
        ownerType: readRequiredTrimmedString(record, 'owner_type', 'Task response.owner_type'),
        createdAtMs: readRequiredNonNegativeIntegerValue(record['created_at_ms'], 'Task response.created_at_ms'),
        updatedAtMs: readRequiredNonNegativeIntegerValue(record['updated_at_ms'], 'Task response.updated_at_ms'),
        completedAtMs: readNullableNonNegativeIntegerValue(record['completed_at_ms'], 'Task response.completed_at_ms'),
        progressCurrent: readNullableNonNegativeIntegerValue(record['progress_current'], 'Task response.progress_current'),
        progressTotal: readNullableNonNegativeIntegerValue(record['progress_total'], 'Task response.progress_total'),
        progressPercent: readNullableFiniteNumberValue(record['progress_percent'], 'Task response.progress_percent'),
        statusMessage: readNullableTrimmedStringValue(record['status_message'], 'Task response.status_message'),
        metadata: requireRecord(record['metadata'], 'Task response.metadata'),
        result: readNullableJsonObjectValue(record['result'], 'Task response.result'),
        errorCode: readNullableNonNegativeIntegerValue(record['error_code'], 'Task response.error_code'),
        errorType: readNullableTrimmedStringValue(record['error_type'], 'Task response.error_type'),
        errorMessage: readNullableTrimmedStringValue(record['error_message'], 'Task response.error_message')
    };
};

const decodeTaskListResponse = (value: ApiResponsePayload): TaskListResponse => {
    const record = requireRecord(value, 'Task list response');
    const tasks = record['tasks'];
    if (!Array.isArray(tasks)) {
        throw new TypeError('Task list response.tasks must be an array.');
    }
    return {
        tasks: tasks.map((task) => decodeTaskResponse(task)),
        totalCount: readRequiredNonNegativeIntegerValue(record['total_count'], 'Task list response.total_count'),
        limit: readRequiredNonNegativeIntegerValue(record['limit'], 'Task list response.limit'),
        offset: readRequiredNonNegativeIntegerValue(record['offset'], 'Task list response.offset')
    };
};

export { decodeTaskListResponse, decodeTaskResponse };
export type { TaskListResponse, TaskResponse };
