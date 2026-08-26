/* SoAI - Shared realtime actions service [frontend/assets/ts/core/realtime/streammanager/actions/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { handleTaskWebSocketEvent } from '@core/realtime/streammanager/actions/handleTaskWebSocketEvent.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ApiServiceInterface, OperationEvent, OperationListener, OperationMetadata, StreamActionResult, TaskTerminalListener } from '@core/realtime/streammanager/types.ts';
import { type StreamActionHandlers } from '@core/types/streamTypes.ts';
import { runTaskAction } from '@core/realtime/streammanager/actions/httpTaskAction.ts';
import { runTaskCommand } from '@core/realtime/streammanager/actions/wsTaskCommand.ts';
import { checkTaskSnapshot, recoverTaskFromSnapshot, reconnectOperations } from '@core/realtime/streammanager/actions/effects.ts';
import { emitTaskOperation, emitTerminalTaskEvent, finalizeTaskWatchers, notifyTaskProgress, subscribeOperationListener, subscribeTerminalTaskListener } from '@core/realtime/streammanager/actions/events.ts';
import { resetStreamTaskRuntimeState, createStreamTaskRuntimeState } from '@core/realtime/streammanager/actions/state.ts';
import type { StreamTaskExecutionRuntime, StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import { type StreamTaskRuntimeContract } from '@core/realtime/streammanager/actions/contracts.ts';
import type { StreamTaskSafeInvoker, StreamTaskRequest, StreamTaskRuntimeOptions, StreamTaskWebSocketProvider } from '@core/realtime/streammanager/actions/types.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runAcceptedTaskLifecycle } from '@core/realtime/streammanager/actions/acceptedTaskLifecycle.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import { finalizeKeyedTaskAdmission, getKeyedTaskAdmissionId } from '@core/realtime/streammanager/actions/keyedTaskAdmission.ts';
import { hasActiveTrackedOperationType } from '@core/realtime/streammanager/actions/trackedTaskQueries.ts';
import { retainTaskTerminalHandoff } from '@core/realtime/streammanager/actions/taskTerminalHandoff.ts';

const logOperationDispatchError = (module: string, message: string, error: Error): void => {
    errorHandler.debug(module, message, error);
};

class StreamTaskRuntime implements StreamTaskRuntimeContract {
    #module: string;
    #eventTarget: EventTarget;
    #apiClient: ApiServiceInterface;
    #request: StreamTaskRequest;
    #getWebSocket: StreamTaskWebSocketProvider;
    #safe: StreamTaskSafeInvoker;
    #state: StreamTaskRuntimeState;

    constructor(options: StreamTaskRuntimeOptions) {
        if (!isObject(options)) {
            throw new Error('StreamTaskRuntime requires options');
        }
        const module = toTrimmedString(options.module);
        if (!module) throw new Error('StreamTaskRuntime requires module name');
        if (!(options.eventTarget instanceof EventTarget)) throw new Error('StreamTaskRuntime requires eventTarget');
        if (!isObject(options.apiClient) || !isFunction(options.apiClient.request)) {
            throw new Error('StreamTaskRuntime requires apiClient');
        }
        if (!isFunction(options.request)) throw new Error('StreamTaskRuntime requires request function');
        if (!isFunction(options.getWebSocket)) throw new Error('StreamTaskRuntime requires websocket accessor');
        if (!isFunction(options.safe)) throw new Error('StreamTaskRuntime requires safe()');

        this.#module = module;
        this.#eventTarget = options.eventTarget;
        this.#apiClient = options.apiClient;
        this.#request = options.request;
        this.#getWebSocket = options.getWebSocket;
        this.#safe = options.safe;
        this.#state = createStreamTaskRuntimeState();
    }

    #emitOperation(id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject): void {
        emitTaskOperation({
            module: this.#module,
            eventTarget: this.#eventTarget,
            state: this.#state,
            safeInvoker: this.#safe,
            logDebug: logOperationDispatchError,
            id,
            type,
            status,
            meta,
            data
        });
    }

    #emitTerminalTask(taskId: string, payload: JsonObject, meta?: OperationMetadata | null): void {
        finalizeKeyedTaskAdmission(this.#state.keyedTaskAdmissions, taskId);
        emitTerminalTaskEvent({
            module: this.#module,
            eventTarget: this.#eventTarget,
            state: this.#state,
            safeInvoker: this.#safe,
            logDebug: logOperationDispatchError,
            taskId,
            payload,
            ...(meta ? { meta } : {})
        });
    }

    #checkTaskSnapshot(taskId: string): Promise<void> {
        return checkTaskSnapshot({
            module: this.#module,
            taskId,
            state: this.#state,
            getWebSocket: this.#getWebSocket,
            logDebug: errorHandler.debug,
            emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => this.#emitOperation(id, type, status, meta, data),
            emitTerminalTask: (taskIdForCompletion: string, payload: JsonObject, meta?: OperationMetadata | null) => this.#emitTerminalTask(taskIdForCompletion, payload, meta),
            finalizeTaskWatchers: (taskIdForCompletion: string, payload: JsonObject) => finalizeTaskWatchers(this.#state, this.#safe, taskIdForCompletion, payload)
        });
    }

    #createTaskExecutionRuntime(): StreamTaskExecutionRuntime {
        const runtime = {
            safe: this.#safe,
            state: this.#state,
            module: this.#module,
            logWarn: errorHandler.warn,
            getTaskSnapshot: (taskId: string) => this.#checkTaskSnapshot(taskId),
            emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => this.#emitOperation(id, type, status, meta, data),
            emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => this.#emitTerminalTask(taskId, payload, meta),
            finalizeTaskWatchers: (taskId: string, payload: JsonObject) => finalizeTaskWatchers(this.#state, this.#safe, taskId, payload)
        };
        const cancelTask = this.#apiClient.system.cancelTask;
        if (!cancelTask) {
            return runtime;
        }
        return {
            ...runtime,
            cancelTask: (taskId: string, reason: string | null): Promise<TaskCancellationResponse> => this.#requestTaskCancellation(taskId, reason)
        };
    }

    async #requestTaskCancellation(taskId: string, reason: string | null): Promise<TaskCancellationResponse> {
        const cancelTask = this.#apiClient.system.cancelTask;
        if (!cancelTask) {
            throw new Error('Task cancellation service is unavailable');
        }
        const cancellation = await cancelTask(taskId, reason);
        if (toTrimmedString(cancellation.taskId) !== taskId) {
            throw new Error(`Task cancellation response identifier mismatch for ${taskId}`);
        }
        return cancellation;
    }

    reset(): void {
        this.#state.trackedTasks.forEach((meta, id) => {
            const operationType = toTrimmedString(meta.type);
            if (!operationType || operationType === 'unknown') {
                return;
            }
            this.#emitOperation(id, operationType, 'detached', { ...meta, taskStatus: 'detached' }, {});
        });
        resetStreamTaskRuntimeState(this.#state, this.#safe);
    }

    handleTaskWebSocketEvent(eventType: string, payload: JsonObject): void {
        handleTaskWebSocketEvent({
            eventType,
            payload,
            trackedTasks: this.#state.trackedTasks,
            hasTaskWatchers: (taskId: string) => this.#state.taskWatchers.has(taskId),
            emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => this.#emitOperation(id, type, status, meta, data),
            emitTerminalTask: (taskId: string, terminalPayload: JsonObject, meta?: OperationMetadata | null) => this.#emitTerminalTask(taskId, terminalPayload, meta),
            notifyTaskProgress: (taskId: string, update: JsonObject) => notifyTaskProgress(this.#state, this.#safe, taskId, update),
            finalizeTaskWatchers: (taskId: string, update: JsonObject) => finalizeTaskWatchers(this.#state, this.#safe, taskId, update),
            retainTaskTerminal: (taskId: string, terminalPayload: JsonObject) => retainTaskTerminalHandoff(this.#state, taskId, terminalPayload),
            recoverUnknownTask: (taskId: string, update: JsonObject) => {
                terminateHandledPromise(
                    recoverTaskFromSnapshot({
                        taskId,
                        payload: update,
                        module: this.#module,
                        state: this.#state,
                        getWebSocket: this.#getWebSocket,
                        emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => this.#emitOperation(id, type, status, meta, data),
                        emitTerminalTask: (taskIdForCompletion: string, payload: JsonObject, meta?: OperationMetadata | null) => this.#emitTerminalTask(taskIdForCompletion, payload, meta),
                        finalizeTaskWatchers: (taskIdForCompletion: string, payload: JsonObject) => finalizeTaskWatchers(this.#state, this.#safe, taskIdForCompletion, payload),
                        logDebug: errorHandler.debug
                    })
                );
            }
        });
    }

    notifyOperationListeners(event: OperationEvent): void {
        this.#state.operationListeners.forEach((listener) => this.#safe(() => listener(event)));
        try {
            this.#eventTarget.dispatchEvent(new CustomEvent('operation', { detail: event }));
        } catch (error) {
            const normalizedError = ensureError(error);
            errorHandler.debug(this.#module, 'Operation listener notification failed', normalizedError);
        }
    }

    subscribeOperations(listener: OperationListener): () => void {
        return subscribeOperationListener(this.#state, listener);
    }

    subscribeTerminalTasks(listener: TaskTerminalListener): () => void {
        return subscribeTerminalTaskListener(this.#state, listener);
    }

    taskAction(
        endpoint: string,
        options: {
            method?: string;
            body?: ApiRequestBody;
            headers?: Record<string, string>;
            handlers?: StreamActionHandlers;
            operation?: Partial<OperationMetadata> | null;
            allowDiscovery?: boolean;
            timeoutMs?: number;
        } = {}
    ): StreamActionResult {
        return runTaskAction({
            endpoint,
            action: options,
            request: this.#request,
            getWebSocket: this.#getWebSocket,
            ...this.#createTaskExecutionRuntime()
        });
    }

    taskCommand(
        command: JsonObject,
        options: {
            handlers?: StreamActionHandlers;
            operation?: Partial<OperationMetadata> | null;
            timeoutMs?: number;
        } = {}
    ): StreamActionResult {
        const ws = this.#getWebSocket();
        if (!ws) {
            throw new Error('WebSocket client is unavailable');
        }
        return runTaskCommand({
            command,
            action: options,
            ws,
            ...this.#createTaskExecutionRuntime()
        });
    }

    trackAcceptedTask(
        taskId: string,
        options: {
            handlers?: StreamActionHandlers;
            operation?: Partial<OperationMetadata> | null;
            timeoutMs?: number;
        } = {}
    ): StreamActionResult {
        const normalizedTaskId = toTrimmedString(taskId);
        if (!normalizedTaskId) {
            throw new Error('Accepted task id is required');
        }
        const taskHandle = runAcceptedTaskLifecycle({
            acceptedTask: { taskId: normalizedTaskId },
            handlers: options.handlers ?? {},
            operation: options.operation ?? null,
            ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs }),
            ...this.#createTaskExecutionRuntime()
        });
        return taskHandle;
    }

    async reconnectOperations(): Promise<void> {
        await reconnectOperations({
            state: this.#state,
            getWebSocket: this.#getWebSocket,
            emitOperation: (id: string, type: string, status: string, meta: OperationMetadata, data: JsonObject) => this.#emitOperation(id, type, status, meta, data),
            emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => this.#emitTerminalTask(taskId, payload, meta),
            finalizeTaskWatchers: (taskId: string, payload: JsonObject) => finalizeTaskWatchers(this.#state, this.#safe, taskId, payload)
        });
    }

    async requestTaskCancellation(taskId: string, reason: string | null): Promise<TaskCancellationResponse> {
        const normalizedTaskId = toTrimmedString(taskId);
        if (!normalizedTaskId) throw new Error('Task id required');
        const handler = this.#state.operationHandlers.get(normalizedTaskId);
        if (handler?.requestCancellation) {
            return await handler.requestCancellation(reason);
        }
        return await this.#requestTaskCancellation(normalizedTaskId, reason);
    }

    hasActiveOperationsOfType(types: string | string[]): boolean {
        return hasActiveTrackedOperationType(this.#state.trackedTasks, types);
    }

    getActiveOperationTaskId(operationKey: string): string | null {
        return getKeyedTaskAdmissionId(this.#state.keyedTaskAdmissions, operationKey);
    }
}

export { StreamTaskRuntime };
