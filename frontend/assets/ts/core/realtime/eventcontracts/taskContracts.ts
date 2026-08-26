/* SoAI - Frontend task WebSocket event contracts [frontend/assets/ts/core/realtime/eventcontracts/taskContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { defineWebSocketEventContract } from '@core/realtime/eventcontracts/contracts.ts';
import { readNullableFiniteIntegerValue, readRequiredFiniteNumberValue, readRequiredNonNegativeIntegerValue } from '@core/types/payloadNumberReaders.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredStringValue, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface TaskEventBase {
    eventId: string;
    timestamp: number;
}
interface TaskCreatedEvent extends TaskEventBase {
    taskId: string;
    taskType: string;
    ownerId: string;
    ownerType: string;
    userId: number;
    status: string;
    statusMessage: string | null;
    metadata: OpaqueJsonObject;
    progressCurrent: number | null;
    progressTotal: number | null;
}
interface TaskCompleteEvent extends TaskEventBase {
    success: boolean;
    message: string;
    taskId: string | null;
    userId: number | null;
    status: string | null;
    errorCode: number | null;
    errorType: string | null;
    errorMessage: string | null;
}

const decodeTaskBase = (payload: JsonValue): TaskEventBase => {
    const record = requireRecord(payload, 'Task event');
    const timestamp = readRequiredFiniteNumberValue(record['timestamp'], 'Task event.timestamp');
    if (timestamp <= 0) throw new TypeError('Task event.timestamp must be positive');
    return { eventId: readRequiredTrimmedStringValue(record['event_id'], 'Task event.event_id'), timestamp };
};

const decodeTaskCreated = (payload: JsonValue): TaskCreatedEvent => {
    const record = requireRecord(payload, 'Task created event');
    const userId = readRequiredNonNegativeIntegerValue(record['user_id'], 'Task created event.user_id');
    return {
        ...decodeTaskBase(payload),
        taskId: readRequiredTrimmedStringValue(record['task_id'], 'Task created event.task_id'),
        taskType: readRequiredTrimmedStringValue(record['task_type'], 'Task created event.task_type'),
        ownerId: readRequiredTrimmedStringValue(record['owner_id'], 'Task created event.owner_id'),
        ownerType: readRequiredTrimmedStringValue(record['owner_type'], 'Task created event.owner_type'),
        userId,
        status: readRequiredTrimmedStringValue(record['status'], 'Task created event.status'),
        statusMessage: readNullableTrimmedStringValue(record['status_message'], 'Task created event.status_message'),
        metadata: requireRecord(record['metadata'], 'Task created event.metadata'),
        progressCurrent: readNullableFiniteIntegerValue(record['progress_current'], 'Task created event.progress_current'),
        progressTotal: readNullableFiniteIntegerValue(record['progress_total'], 'Task created event.progress_total')
    };
};

const decodeTaskComplete = (payload: JsonValue): TaskCompleteEvent => {
    const record = requireRecord(payload, 'Task complete event');
    const userId = readNullableFiniteIntegerValue(record['user_id'], 'Task complete event.user_id');
    if (userId !== null && userId < 0) throw new TypeError('Task complete event.user_id must be non-negative or null');
    return {
        ...decodeTaskBase(payload),
        success: readRequiredBooleanValue(record['success'], 'Task complete event.success'),
        message: readRequiredStringValue(record['message'], 'Task complete event.message'),
        taskId: readNullableTrimmedStringValue(record['task_id'], 'Task complete event.task_id'),
        userId,
        status: readNullableTrimmedStringValue(record['status'], 'Task complete event.status'),
        errorCode: readNullableFiniteIntegerValue(record['error_code'], 'Task complete event.error_code'),
        errorType: readNullableTrimmedStringValue(record['error_type'], 'Task complete event.error_type'),
        errorMessage: readNullableTrimmedStringValue(record['error_message'], 'Task complete event.error_message')
    };
};

const TASK_EVENT_CONTRACTS = Object.freeze({
    created: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TASK_CREATED, decodeTaskCreated),
    complete: defineWebSocketEventContract(WEBSOCKET_EVENT_TYPES.TASK_COMPLETE, decodeTaskComplete)
});

export { TASK_EVENT_CONTRACTS };
export type { TaskCompleteEvent, TaskCreatedEvent };
