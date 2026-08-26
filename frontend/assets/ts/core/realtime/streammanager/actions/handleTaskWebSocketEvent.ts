/* SoAI - Shared realtime handle task WebSocket event [frontend/assets/ts/core/realtime/streammanager/actions/handleTaskWebSocketEvent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { normalizeProgressPercent } from '@core/primitives/progress.ts';
import { buildTerminalTaskPayload, finalizeTrackedTask } from '@core/realtime/streammanager/actions/completion.ts';
import { buildTaskOperation, buildTrackedTaskOperation } from '@core/realtime/streammanager/actions/taskOperations.ts';
import type { OperationMetadata } from '@core/realtime/streammanager/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES } from '@core/websocketEvents.ts';

interface EmitOperationFunction {
    (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject): void;
}

interface HandleTaskWebSocketEventOptions {
    eventType: string;
    payload: JsonObject;
    trackedTasks: Map<string, OperationMetadata>;
    hasTaskWatchers: (taskId: string) => boolean;
    emitOperation: EmitOperationFunction;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    notifyTaskProgress: (id: string, payload: JsonObject) => void;
    finalizeTaskWatchers: (id: string, payload: JsonObject) => void;
    retainTaskTerminal: (id: string, payload: JsonObject) => void;
    recoverUnknownTask: (id: string, payload: JsonObject) => void;
}

const handleTaskWebSocketEvent = (options: HandleTaskWebSocketEventOptions): void => {
    if (!isObject(options)) {
        throw new Error('handleTaskWebSocketEvent requires options');
    }
    const { eventType, payload, trackedTasks, hasTaskWatchers, emitOperation, emitTerminalTask, notifyTaskProgress, finalizeTaskWatchers, retainTaskTerminal, recoverUnknownTask } = options;

    if (eventType === WEBSOCKET_EVENT_TYPES.TASK_CREATED) {
        const trackedTask = buildTrackedTaskOperation(payload);
        if (!trackedTask) {
            return;
        }
        const operation = buildTaskOperation(payload);
        if (!operation) {
            const existing = trackedTasks.get(trackedTask.id);
            const existingType = toTrimmedString(existing?.type);
            const trackedType = toTrimmedString(trackedTask.meta.type);
            const nextType = existingType && existingType !== 'unknown' ? existingType : trackedType;
            const nextMeta = existing ? { ...existing, ...trackedTask.meta, type: nextType, id: trackedTask.id, taskId: trackedTask.id } : trackedTask.meta;
            trackedTasks.set(trackedTask.id, nextMeta);
            if (existing && nextType && nextType !== 'unknown') {
                emitOperation(trackedTask.id, nextType, 'progress', nextMeta, trackedTask.progress !== null ? { progress: trackedTask.progress } : {});
            }
            return;
        }
        const existing = trackedTasks.get(operation.id);
        if (existing) {
            const nextMeta = { ...existing, ...operation.meta };
            trackedTasks.set(operation.id, nextMeta);
            emitOperation(operation.id, operation.type, 'progress', nextMeta, operation.progress !== null ? { progress: operation.progress } : {});
            return;
        }
        trackedTasks.set(operation.id, operation.meta);
        emitOperation(operation.id, operation.type, 'start', operation.meta, operation.progress !== null ? { progress: operation.progress } : {});
        return;
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.TASK_STATUS_CHANGED) {
        const taskId = toTrimmedString(payload['task_id']);
        if (!taskId) {
            return;
        }
        const meta = trackedTasks.get(taskId);
        if (!meta) {
            return;
        }
        const statusValue = toTrimmedString(payload['new_status']);
        const statusMessageValue = toTrimmedString(payload['status_message']);
        const nextMeta = {
            ...meta,
            ...(statusValue ? { taskStatus: statusValue } : {}),
            ...(statusMessageValue ? { statusMessage: statusMessageValue } : {})
        };
        trackedTasks.set(taskId, nextMeta);
        const operationType = toTrimmedString(nextMeta.type) || 'unknown';
        if (operationType !== 'unknown') {
            emitOperation(taskId, operationType, 'progress', nextMeta, {});
        }
        return;
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.TASK_PROGRESS) {
        const taskId = toTrimmedString(payload['task_id']);
        if (!taskId) {
            return;
        }
        const percent = payload['percent'];
        const progress = isFiniteNumber(percent) ? normalizeProgressPercent(percent) : null;
        const message = toTrimmedString(payload['message']);
        const details = toTrimmedString(payload['details']);
        const normalizedData = {
            ...(progress !== null ? { progress } : {}),
            ...(message ? { message } : {}),
            ...(details ? { details } : {})
        };

        const meta = trackedTasks.get(taskId);
        if (meta) {
            const operationType = toTrimmedString(meta.type) || 'unknown';
            if (operationType !== 'unknown') {
                emitOperation(taskId, operationType, 'progress', meta, normalizedData);
            }
        } else {
            recoverUnknownTask(taskId, normalizedData);
        }
        notifyTaskProgress(taskId, { type: eventType, taskId, ...normalizedData });
        return;
    }

    if (eventType === WEBSOCKET_EVENT_TYPES.TASK_COMPLETE) {
        const taskId = toTrimmedString(payload['task_id']);
        if (!taskId) {
            return;
        }
        const terminalPayload = buildTerminalTaskPayload(taskId, payload);
        if (!terminalPayload) {
            return;
        }
        const hadTaskWatchers = hasTaskWatchers(taskId);
        performance.mark(`soai-audit:terminal-${hadTaskWatchers ? 'watched' : 'unwatched'}:${taskId}`);
        const handled = finalizeTrackedTask({
            taskId,
            payload: terminalPayload,
            trackedTasks,
            hasTaskWatchers,
            emitOperation,
            emitTerminalTask,
            finalizeTaskWatchers
        });
        if (!hadTaskWatchers) {
            retainTaskTerminal(taskId, terminalPayload);
        }
        if (!handled) {
            emitTerminalTask(taskId, terminalPayload, null);
        }
    }
};

export { handleTaskWebSocketEvent };
