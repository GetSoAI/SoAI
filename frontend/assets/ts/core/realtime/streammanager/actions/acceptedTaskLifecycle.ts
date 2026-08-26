/* SoAI - Shared realtime accepted task lifecycle [frontend/assets/ts/core/realtime/streammanager/actions/acceptedTaskLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { emitAcceptedTaskOperation, type TaskOperationEmitter } from '@core/realtime/streammanager/actions/acceptedTaskOperation.ts';
import { buildTerminalTaskPayload, finalizeTrackedTask } from '@core/realtime/streammanager/actions/completion.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import { watchTask, type SnapshotChecker } from '@core/realtime/streammanager/actions/taskWatching.ts';
import type { StreamTaskDebugLogger, StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';
import type { OperationMetadata, StreamActionResult } from '@core/realtime/streammanager/types.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import { isMutationAcceptanceRecoveryRequiredError } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';

interface AcceptedTaskDescriptor {
    taskId: string;
    endpoint?: string;
}

interface AcceptedTaskLifecycleOptions {
    acceptedTask?: AcceptedTaskDescriptor;
    acceptTask?: () => Promise<AcceptedTaskDescriptor>;
    handlers: StreamActionHandlers;
    operation: Partial<OperationMetadata> | null;
    timeoutMs?: number | undefined;
    safe: StreamTaskSafeInvoker;
    state: StreamTaskRuntimeState;
    getTaskSnapshot: SnapshotChecker;
    emitOperation: TaskOperationEmitter;
    emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void;
    finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void;
    logWarn: StreamTaskDebugLogger;
    module: string;
    cancelTask?: ((taskId: string, reason: string | null) => Promise<TaskCancellationResponse>) | undefined;
    onError?: ((error: Error) => void) | undefined;
}

const resolveAcceptedTaskDescriptor = (descriptor: AcceptedTaskDescriptor): AcceptedTaskDescriptor => {
    const taskId = toTrimmedString(descriptor.taskId);
    if (!taskId) {
        throw new Error('Accepted task requires task_id');
    }
    if (descriptor.endpoint === undefined) {
        return { taskId };
    }
    const endpoint = toTrimmedString(descriptor.endpoint);
    if (!endpoint) {
        throw new Error(`Accepted task ${taskId} endpoint must be non-empty when provided`);
    }
    return { taskId, endpoint };
};

const isRecoverableMutationAcceptanceError = (error: Error): boolean => (error instanceof APIError && error.code === 'identity_time_skew') || isMutationAcceptanceRecoveryRequiredError(error);

const reportLifecycleWarning = (options: AcceptedTaskLifecycleOptions, message: string, error: Error): void => {
    try {
        options.logWarn(options.module, message, error);
    } catch (diagnosticError) {
        errorHandler.error(options.module, 'Accepted task diagnostic reporting failed', ensureError(diagnosticError));
    }
};

const createAcceptedOperationMetadata = (taskId: string, endpoint: string | undefined, operation: Partial<OperationMetadata> | null): OperationMetadata => {
    const operationMeta: OperationMetadata = {
        type: toTrimmedString(isObject(operation) ? operation['type'] : null) || 'unknown',
        id: taskId,
        taskId,
        startedAt: Date.now(),
        ...(endpoint ? { endpoint } : {})
    };
    if (isObject(operation)) {
        Object.assign(operationMeta, operation);
    }
    operationMeta.type = toTrimmedString(operationMeta.type) || 'unknown';
    operationMeta.id = taskId;
    operationMeta.taskId = taskId;
    if (toTrimmedString(operationMeta['operationKey'])) operationMeta['requestId'] = taskId;
    if (endpoint) {
        operationMeta.endpoint = endpoint;
    }
    return operationMeta;
};

const runAcceptedTaskLifecycle = (options: AcceptedTaskLifecycleOptions): StreamActionResult => {
    let taskId: string | null = null;
    let cancelRequested = false;
    let cancelDispatched = false;
    let pendingDetach = false;
    let settled = false;
    let watchResult: ReturnType<typeof watchTask> | null = null;
    let cancellationReason: string | null = null;
    let cancellationCompletion: ReturnType<typeof createDeferred<TaskCancellationResponse>> | null = null;

    const dispatchCancellation = (): void => {
        if (!taskId || cancelDispatched || !cancellationCompletion) return;
        cancelDispatched = true;
        const cancelTask = options.cancelTask;
        if (!cancelTask) {
            cancellationCompletion.reject(new Error('Task cancellation service is unavailable'));
            return;
        }
        void cancelTask(taskId, cancellationReason).then(cancellationCompletion.resolve, (error) => cancellationCompletion?.reject(ensureError(error)));
    };

    const requestCancellation = (reason: string | null): Promise<TaskCancellationResponse> => {
        if (settled || pendingDetach) return Promise.reject(new Error('Task is no longer cancellable'));
        if (cancellationCompletion) return cancellationCompletion.promise;
        cancelRequested = true;
        cancellationReason = reason;
        cancellationCompletion = createDeferred<TaskCancellationResponse>();
        dispatchCancellation();
        return cancellationCompletion.promise;
    };

    const cancel = (): void => {
        if (settled || pendingDetach) return;
        void requestCancellation('Cancelled').catch((error) => {
            const normalizedError = ensureError(error);
            if (normalizedError.message !== 'Maintenance') {
                reportLifecycleWarning(options, 'Cancel request failed', normalizedError);
            }
        });
    };

    const detach = (): void => {
        if (settled || cancelRequested) return;
        if (taskId && watchResult?.close) {
            pendingDetach = true;
            watchResult.close();
            return;
        }
        pendingDetach = true;
    };

    const completion = createDeferred<JsonValue | null>();
    const acceptedCompletion = createDeferred<string>();
    void acceptedCompletion.promise.catch((error) => reportLifecycleWarning(options, 'Accepted task admission failed', ensureError(error)));
    const actionResult: StreamActionResult = {
        accepted: acceptedCompletion.promise,
        finished: completion.promise,
        abort: cancel,
        close: detach,
        requestCancellation
    };

    const executeAcceptedTaskLifecycle = async (): Promise<void> => {
        try {
            let acceptedTaskDescriptor = options.acceptedTask;
            if (!acceptedTaskDescriptor) {
                if (!options.acceptTask) {
                    throw new Error('Accepted task lifecycle requires a task source');
                }
                acceptedTaskDescriptor = await options.acceptTask();
            }
            const acceptedTask = resolveAcceptedTaskDescriptor(acceptedTaskDescriptor);
            taskId = acceptedTask.taskId;
            const operationMeta = createAcceptedOperationMetadata(acceptedTask.taskId, acceptedTask.endpoint, options.operation);
            const previousMeta = options.state.trackedTasks.get(acceptedTask.taskId) ?? null;
            const acceptedOperationMeta = previousMeta ? { ...previousMeta, ...operationMeta } : operationMeta;
            options.state.trackedTasks.set(acceptedTask.taskId, acceptedOperationMeta);
            emitAcceptedTaskOperation({
                taskId: acceptedTask.taskId,
                operationMeta: acceptedOperationMeta,
                previousMeta,
                emitOperation: options.emitOperation
            });
            watchResult = watchTask({
                taskId: acceptedTask.taskId,
                handlers: options.handlers,
                ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs }),
                state: options.state,
                safe: options.safe,
                checkTaskSnapshot: options.getTaskSnapshot
            });
            performance.mark(`soai-audit:accepted:${acceptedTask.taskId}`);
            options.state.operationHandlers.set(acceptedTask.taskId, actionResult);
            acceptedCompletion.resolve(acceptedTask.taskId);
            if (pendingDetach && watchResult.close) {
                watchResult.close();
            } else if (cancelRequested) {
                dispatchCancellation();
            }
            const result = await watchResult.finished;
            performance.mark(`soai-audit:watcher-finished:${acceptedTask.taskId}`);
            const trackedTaskMeta = options.state.trackedTasks.get(acceptedTask.taskId) ?? null;
            const terminalPayload = trackedTaskMeta ? buildTerminalTaskPayload(acceptedTask.taskId, result) : null;
            if (trackedTaskMeta && terminalPayload) {
                finalizeTrackedTask({
                    taskId: acceptedTask.taskId,
                    payload: terminalPayload,
                    trackedTasks: options.state.trackedTasks,
                    hasTaskWatchers: (trackedTaskId: string) => options.state.taskWatchers.has(trackedTaskId),
                    emitOperation: options.emitOperation,
                    emitTerminalTask: options.emitTerminalTask,
                    finalizeTaskWatchers: options.finalizeTaskWatchers,
                    meta: trackedTaskMeta
                });
            }
            settled = true;
            completion.resolve(terminalPayload ?? result);
        } catch (error) {
            const normalizedError = ensureError(error);
            acceptedCompletion.reject(normalizedError);
            if (cancellationCompletion && !cancelDispatched) {
                cancellationCompletion.reject(normalizedError);
            }
            try {
                options.onError?.(normalizedError);
            } catch (cleanupError) {
                reportLifecycleWarning(options, 'Accepted task cleanup failed', ensureError(cleanupError));
            }
            if (!watchResult && !isRecoverableMutationAcceptanceError(normalizedError)) {
                options.safe(options.handlers.onError, normalizedError);
            }
            settled = true;
            completion.reject(normalizedError);
        } finally {
            if (taskId && options.state.operationHandlers.get(taskId) === actionResult) {
                options.state.operationHandlers.delete(taskId);
            }
        }
    };

    void executeAcceptedTaskLifecycle().catch((error) => {
        const runtimeError = ensureError(error);
        options.safe(options.handlers.onError, runtimeError);
        settled = true;
        completion.reject(runtimeError);
    });

    return actionResult;
};

export { runAcceptedTaskLifecycle };
export type { AcceptedTaskDescriptor };
