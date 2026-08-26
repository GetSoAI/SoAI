/* SoAI - Shared parsers for task operation payloads [frontend/assets/ts/core/tasks/operationPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireJsonResponsePayload } from '@core/api/jsonResponsePayload.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { isArray, isFiniteNumber, isString } from '@core/typeGuards.ts';
import type { TaskResponse } from '@core/api/contracts/taskContracts.ts';

type TaskProgressState = 'pending' | 'downloading' | 'success' | 'error' | 'info';

type OperationDryRunPayload = {
    plannedCommands: readonly string[];
    predictedEffects: readonly string[];
    warnings: readonly string[];
};

type AcceptedTaskWithDeadlinePayload = {
    taskId: string;
    commitDeadlineTsMs: number;
};

type TaskProgressSnapshotPayload = {
    status: string;
    percent: number;
    message: string;
};

const TERMINAL_TASK_STATUSES: ReadonlySet<string> = new Set(['completed', 'failed', 'cancelled', 'canceled']);
const TERMINAL_OPERATION_STATUSES: ReadonlySet<string> = new Set(['complete', 'completed', 'error', 'failed', 'cancelled', 'canceled', 'detached']);
const CANCELLED_TASK_STATUSES: ReadonlySet<string> = new Set(['cancelled', 'canceled']);

const normalizeTaskStatusText = (value: string | null | undefined): string => toTrimmedLower(value);

const isTerminalTaskStatus = (value: string | null | undefined): boolean => TERMINAL_TASK_STATUSES.has(normalizeTaskStatusText(value));

const isTerminalOperationStatus = (value: string | null | undefined): boolean => TERMINAL_OPERATION_STATUSES.has(normalizeTaskStatusText(value));

const isCancelledTaskStatus = (value: string | null | undefined): boolean => CANCELLED_TASK_STATUSES.has(normalizeTaskStatusText(value));

const resolveTaskProgressState = (status: string | null | undefined): TaskProgressState => {
    const normalized = normalizeTaskStatusText(status);
    if (normalized === 'queued' || normalized === 'pending') {
        return 'pending';
    }
    if (normalized === 'failed' || normalized === 'error' || isCancelledTaskStatus(normalized)) {
        return 'error';
    }
    return 'info';
};

const resolveTaskOperationConversationId = (meta: JsonObject | null | undefined): string => {
    const direct = toTrimmedString(meta?.['convId']);
    if (direct) {
        return direct;
    }
    const ownerType = toTrimmedLower(meta?.['ownerType']);
    const ownerId = toTrimmedString(meta?.['ownerId']);
    if (ownerType === 'conversation' && ownerId) {
        return ownerId;
    }
    return '';
};

const requireOperationRecord = (payload: ApiResponsePayload, label: string): JsonObject => {
    return requireRecord(requireJsonResponsePayload(payload, label), label);
};

const parseSuccessfulOperationPayload = (payload: ApiResponsePayload, label: string): JsonObject => {
    const record = requireOperationRecord(payload, label);
    if (record['success'] !== true) {
        throw new Error(`${label} success payload is invalid.`);
    }
    return record;
};

const parseCommandSegments = (value: JsonValue | null | undefined, label: string, index: number): string => {
    if (!isArray(value)) {
        throw new Error(`${label}.planned_commands[${String(index)}] must be a string array.`);
    }
    const segments: string[] = [];
    value.forEach((segment, segmentIndex) => {
        if (!isString(segment)) {
            throw new Error(`${label}.planned_commands[${String(index)}][${String(segmentIndex)}] must be a string.`);
        }
        segments.push(segment);
    });
    return segments.join(' ');
};

const parseCommandLines = (value: JsonValue | null | undefined, label: string): readonly string[] => {
    if (!isArray(value)) {
        throw new Error(`${label}.planned_commands must be an array.`);
    }
    return value.map((entry, index) => parseCommandSegments(entry, label, index));
};

const parseStringList = (value: JsonValue | null | undefined, label: string, field: string): readonly string[] => {
    if (!isArray(value)) {
        throw new Error(`${label}.${field} must be an array.`);
    }
    return value.map((entry, index) => {
        if (!isString(entry)) {
            throw new Error(`${label}.${field}[${String(index)}] must be a string.`);
        }
        return entry;
    });
};

const parseOperationDryRunPayload = (payload: ApiResponsePayload, label: string): OperationDryRunPayload => {
    const record = requireOperationRecord(payload, label);
    if (record['dry_run'] !== true) {
        throw new Error(`${label} dry-run payload is invalid.`);
    }
    return {
        plannedCommands: parseCommandLines(record['planned_commands'], label),
        predictedEffects: parseStringList(record['predicted_effects'], label, 'predicted_effects'),
        warnings: parseStringList(record['warnings'], label, 'warnings')
    };
};

const parseAcceptedTaskId = (payload: ApiResponsePayload, label: string): string => {
    const record = requireOperationRecord(payload, label);
    if (record['status'] !== 'accepted' || !isString(record['task_id'])) {
        throw new Error(`${label} accepted payload is invalid.`);
    }
    const taskId = toTrimmedString(record['task_id']);
    if (!taskId) {
        throw new Error(`${label}.task_id is required.`);
    }
    return taskId;
};

const parseAcceptedTaskWithDeadlinePayload = (payload: ApiResponsePayload, label: string): AcceptedTaskWithDeadlinePayload => {
    const record = requireOperationRecord(payload, label);
    const taskId = parseAcceptedTaskId(payload, label);
    if (!isFiniteNumber(record['commit_deadline_ts_ms'])) {
        throw new Error(`${label}.commit_deadline_ts_ms is required.`);
    }
    return {
        taskId,
        commitDeadlineTsMs: record['commit_deadline_ts_ms']
    };
};

const parseTaskProgressSnapshotPayload = (payload: TaskResponse): TaskProgressSnapshotPayload => {
    const status = normalizeTaskStatusText(payload.status);
    const percent = payload.progressPercent === null ? 0 : clampPercent(payload.progressPercent);
    const message = payload.statusMessage ?? '';
    return { status, percent, message };
};

export { isCancelledTaskStatus, isTerminalOperationStatus, isTerminalTaskStatus, normalizeTaskStatusText, parseAcceptedTaskId, parseAcceptedTaskWithDeadlinePayload, parseOperationDryRunPayload, parseSuccessfulOperationPayload, parseTaskProgressSnapshotPayload, resolveTaskOperationConversationId, resolveTaskProgressState };
export type { AcceptedTaskWithDeadlinePayload, OperationDryRunPayload, TaskProgressSnapshotPayload, TaskProgressState };
