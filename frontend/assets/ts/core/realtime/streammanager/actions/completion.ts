/* SoAI - Shared realtime completion [frontend/assets/ts/core/realtime/streammanager/actions/completion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import { isCancelledTaskStatus, isTerminalTaskStatus, normalizeTaskStatusText } from '@core/tasks/operationPayloads.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

interface TaskOperationEmitter {
    (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject): void;
}

interface FinalizeTrackedTaskOptions {
    taskId: string;
    payload: JsonObject;
    trackedTasks: Map<string, OperationMetadata>;
    hasTaskWatchers: (taskId: string) => boolean;
    emitOperation: TaskOperationEmitter;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
    meta?: OperationMetadata | null;
}

const buildTerminalTaskPayload = (taskId: string, payload: JsonValue | null | undefined): JsonObject | null => {
    if (!isJsonObject(payload)) {
        return null;
    }
    const status = toTrimmedString(payload['status']);
    if (!status || !isTerminalTaskStatus(status)) {
        return null;
    }
    const normalizedStatus = normalizeTaskStatusText(status);
    const statusMessage = toTrimmedString(payload['status_message']);
    const errorMessage = toTrimmedString(payload['error_message']);
    const errorType = toTrimmedString(payload['error_type']);
    const message = toTrimmedString(payload['message']) || statusMessage || errorMessage || status;
    const errorCode = payload['error_code'];
    const taskPayload: JsonObject = {
        type: toTrimmedString(payload['type']) || 'TaskCompleteEvent',
        taskId,
        status,
        success: payload['success'] === true || normalizedStatus === 'completed',
        message
    };
    const userId = payload['user_id'];
    if (typeof userId === 'number') taskPayload['userId'] = userId;
    if (typeof errorCode === 'number') taskPayload['errorCode'] = errorCode;
    if (errorType) taskPayload['errorType'] = errorType;
    if (statusMessage) taskPayload['statusMessage'] = statusMessage;
    if (errorMessage) taskPayload['errorMessage'] = errorMessage;
    if (payload['cancelled'] === true || isCancelledTaskStatus(normalizedStatus)) taskPayload['cancelled'] = true;
    return taskPayload;
};

const resolveTerminalOperationStatus = (payload: JsonObject): 'cancelled' | 'complete' | 'error' => {
    const status = normalizeTaskStatusText(isString(payload['status']) ? payload['status'] : undefined);
    if (isCancelledTaskStatus(status)) {
        return 'cancelled';
    }
    if (payload['success'] === true || status === 'completed') {
        return 'complete';
    }
    return 'error';
};

const finalizeTrackedTask = (options: FinalizeTrackedTaskOptions): boolean => {
    const meta = options.meta ?? options.trackedTasks.get(options.taskId) ?? null;
    const hasWatchers = options.hasTaskWatchers(options.taskId);
    if (!meta && !hasWatchers) {
        return false;
    }

    options.trackedTasks.delete(options.taskId);
    if (meta) {
        const operationType = toTrimmedString(meta.type) || 'unknown';
        if (operationType !== 'unknown') {
            const rawStatus = toTrimmedString(options.payload['status']);
            const statusMessage = toTrimmedString(options.payload['statusMessage']);
            const errorMessage = toTrimmedString(options.payload['errorMessage']);
            const message = toTrimmedString(options.payload['message']) || errorMessage || statusMessage;
            const terminalStatus = resolveTerminalOperationStatus(options.payload);
            options.emitOperation(options.taskId, operationType, terminalStatus, rawStatus ? { ...meta, taskStatus: rawStatus, ...(statusMessage ? { statusMessage: statusMessage } : {}) } : { ...meta }, terminalStatus === 'error' && message ? { error: message } : {});
        }
    }

    options.emitTerminalTask(options.taskId, options.payload, meta);
    options.finalizeTaskWatchers(options.taskId, options.payload);
    return true;
};

export { buildTerminalTaskPayload, finalizeTrackedTask };
