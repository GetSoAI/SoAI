/* SoAI - Shared realtime actions events [frontend/assets/ts/core/realtime/streammanager/actions/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OperationEvent, OperationMetadata, TaskTerminalEvent, TaskTerminalListener, TaskWatcher } from '@core/realtime/streammanager/types.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import type { StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';
import { isCancelledTaskStatus, normalizeTaskStatusText } from '@core/tasks/operationPayloads.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isFunction, isString } from '@core/typeGuards.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { ensureError } from '@core/errors/coerce.ts';

const emitTaskOperation = (options: { module: string; eventTarget: EventTarget; state: StreamTaskRuntimeState; safeInvoker: StreamTaskSafeInvoker; logDebug: (module: string, message: string, error: Error) => void; id: string; type: string; status: string; meta: OperationMetadata; data: JsonObject }): void => {
    const { module, eventTarget, state, safeInvoker, logDebug, id, type, status, meta, data } = options;
    const event: OperationEvent = {
        id,
        type,
        status,
        meta: { ...meta },
        data,
        timestamp: Date.now()
    };
    state.operationListeners.forEach((listener) => {
        safeInvoker(() => listener(event));
    });
    try {
        eventTarget.dispatchEvent(new CustomEvent('operation', { detail: event }));
    } catch (error) {
        const normalizedError = ensureError(error);
        logDebug(module, 'Operation event dispatch failed', normalizedError);
    }
};

const subscribeOperationListener = (state: StreamTaskRuntimeState, listener: (event: OperationEvent) => void): (() => void) => {
    if (isFunction(listener)) {
        state.operationListeners.add(listener);
    }

    return () => {
        state.operationListeners.delete(listener);
    };
};

const buildTerminalTaskEvent = (taskId: string, payload: JsonObject, meta: OperationMetadata | null): TaskTerminalEvent => {
    const status = toTrimmedString(payload['status']) || (payload['success'] === true ? 'completed' : 'failed');
    const statusMessage = toTrimmedString(payload['statusMessage']);
    const errorMessage = toTrimmedString(payload['errorMessage']);
    const message = toTrimmedString(payload['message']) || statusMessage || errorMessage || status;
    const rawErrorCode = payload['errorCode'];
    const errorCode = isFiniteNumber(rawErrorCode) ? rawErrorCode : null;
    return {
        ...payload,
        type: 'TaskCompleteEvent',
        taskId,
        status,
        success: payload['success'] === true || normalizeTaskStatusText(status) === 'completed',
        message,
        ...(errorCode !== null ? { errorCode } : {}),
        ...(errorMessage ? { errorMessage: errorMessage } : {}),
        ...(meta ? { meta } : {})
    };
};

const emitTerminalTaskEvent = (options: { module: string; eventTarget: EventTarget; state: StreamTaskRuntimeState; safeInvoker: StreamTaskSafeInvoker; logDebug: (module: string, message: string, error: Error) => void; taskId: string; payload: JsonObject; meta?: OperationMetadata | null }): void => {
    const event = buildTerminalTaskEvent(options.taskId, options.payload, options.meta ?? null);
    options.state.terminalTaskListeners.forEach((listener) => {
        options.safeInvoker(() => listener(event));
    });
    try {
        options.eventTarget.dispatchEvent(new CustomEvent('task-terminal', { detail: event }));
    } catch (error) {
        const normalizedError = ensureError(error);
        options.logDebug(options.module, 'Task terminal event dispatch failed', normalizedError);
    }
};

const subscribeTerminalTaskListener = (state: StreamTaskRuntimeState, listener: TaskTerminalListener): (() => void) => {
    if (isFunction(listener)) {
        state.terminalTaskListeners.add(listener);
    }
    return () => {
        state.terminalTaskListeners.delete(listener);
    };
};

const removeTaskWatcher = (state: StreamTaskRuntimeState, taskId: string, watcher: TaskWatcher): void => {
    const watchers = state.taskWatchers.get(taskId);
    performance.mark(`soai-audit:finalize-${watchers?.size ?? 0}:${taskId}`);
    if (!watchers) return;
    watchers.delete(watcher);
    if (!watchers.size) {
        state.taskWatchers.delete(taskId);
    }
};

const notifyTaskProgress = (state: StreamTaskRuntimeState, safeInvoker: StreamTaskSafeInvoker, taskId: string, payload: JsonObject): void => {
    const watchers = state.taskWatchers.get(taskId);
    if (!watchers) return;

    watchers.forEach((watcher) => {
        if (watcher.settled) return;
        safeInvoker(watcher.handlers.onUpdate, payload);
        safeInvoker(watcher.handlers.onProgress, payload);
    });
};

const finalizeTaskWatchers = (state: StreamTaskRuntimeState, safeInvoker: StreamTaskSafeInvoker, taskId: string, payload: JsonObject): void => {
    const watchers = state.taskWatchers.get(taskId);
    if (!watchers) return;
    state.taskWatchers.delete(taskId);

    const status = normalizeTaskStatusText(isString(payload['status']) ? payload['status'] : undefined);
    const isCancelled = isCancelledTaskStatus(status);
    const isSuccess = payload['success'] === true || status === 'completed';
    const terminalPayload = isCancelled ? { ...payload, cancelled: true } : payload;

    watchers.forEach((watcher) => {
        if (watcher.settled) return;
        watcher.settled = true;
        if (watcher.timeoutId) {
            clearTimeout(watcher.timeoutId);
            watcher.timeoutId = null;
        }
        if (isSuccess) safeInvoker(watcher.handlers.onComplete, terminalPayload);
        else safeInvoker(watcher.handlers.onStreamError, terminalPayload);
        watcher.resolve(terminalPayload);
    });
};

export { buildTerminalTaskEvent, emitTaskOperation, emitTerminalTaskEvent, removeTaskWatcher, notifyTaskProgress, finalizeTaskWatchers, subscribeOperationListener, subscribeTerminalTaskListener };
