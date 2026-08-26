/* SoAI - Shared realtime WebSocket task command [frontend/assets/ts/core/realtime/streammanager/actions/wsTaskCommand.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { toTrimmedString } from '@core/normalize.ts';
import type { TaskOperationEmitter } from '@core/realtime/streammanager/actions/acceptedTaskOperation.ts';
import { runAcceptedTaskLifecycle } from '@core/realtime/streammanager/actions/acceptedTaskLifecycle.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import type { SnapshotChecker } from '@core/realtime/streammanager/actions/taskWatching.ts';
import type { StreamTaskDebugLogger, StreamTaskRuntimeWebSocketClient, StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';
import type { OperationMetadata, StreamActionResult } from '@core/realtime/streammanager/types.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { WEBSOCKET_PROTOCOL_VERSION } from '@core/websocketclient/constants.ts';
import { createWebSocketRunId } from '@core/websocketclient/runCorrelation.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import { isWebSocketProtocolErrorEventType } from '@core/websocketEvents.ts';
import { resolveOptionalKeyedTaskAdmission } from '@core/realtime/streammanager/actions/keyedTaskAdmission.ts';
import { recoverMutationAcceptance } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';

interface CommandAcceptedWatcher {
    readonly promise: Promise<string>;
    abort(error: Error): void;
}

class CommandAcceptanceTimeoutError extends Error {
    constructor() {
        super('Command dispatch timeout');
        this.name = 'CommandAcceptanceTimeoutError';
    }
}

const buildCommandError = (payload: JsonObject): Error => {
    const messageValue = payload['message'];
    const message = isString(messageValue) && messageValue.trim() ? messageValue.trim() : 'Command failed';
    const codeValue = payload['code'];
    const code = isString(codeValue) ? codeValue.trim() : '';
    const details = payload['details'];
    const taskIdValue = isJsonObject(details) ? details['task_id'] : null;
    const taskId = isString(taskIdValue) && taskIdValue.trim() ? taskIdValue.trim() : undefined;
    const status = code === 'mutation_conflict' ? 409 : code === 'identity_time_skew' ? 422 : 0;
    return new APIError(status, message, {
        ...(code ? { code } : {}),
        ...(taskId ? { taskId } : {}),
        payload
    });
};

const createCommandAcceptedWatcher = (options: { ws: StreamTaskRuntimeWebSocketClient; runId: string; timeoutMs: number; isSettled: () => boolean; module: string; logWarn: StreamTaskDebugLogger }): CommandAcceptedWatcher => {
    const { ws, runId, timeoutMs } = options;
    let settled = false;
    let unsubscribe: (() => void) | null = null;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;
    let rejectRef: ((error: Error) => void) | null = null;
    const cleanup = (): void => {
        if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
        }
        const dispose = unsubscribe;
        unsubscribe = null;
        runCleanup(dispose, (runtimeError) => {
            options.logWarn(options.module, 'Command accepted watcher cleanup failed', runtimeError);
        });
        rejectRef = null;
    };

    const promise = new Promise<string>((resolve, reject) => {
        rejectRef = reject;
        timeoutId = setTimeout(() => {
            if (settled) return;
            settled = true;
            cleanup();
            reject(new CommandAcceptanceTimeoutError());
        }, timeoutMs);

        unsubscribe = ws.subscribeAll((eventType: string, payload: JsonValue) => {
            if (settled || options.isSettled()) return;
            if (!isObject(payload)) return;
            const payloadRunId = payload['run_id'];
            if (!isString(payloadRunId) || payloadRunId.trim() !== runId) {
                return;
            }
            if (eventType === 'command_accepted') {
                const taskIdValue = payload['task_id'];
                const taskId = isString(taskIdValue) ? taskIdValue.trim() : '';
                if (!taskId) {
                    settled = true;
                    cleanup();
                    reject(new Error('Command accepted without task_id'));
                    return;
                }
                settled = true;
                cleanup();
                resolve(taskId);
                return;
            }
            if (isWebSocketProtocolErrorEventType(eventType)) {
                settled = true;
                cleanup();
                reject(buildCommandError(payload));
            }
        });
    });

    return {
        promise,
        abort: (error: Error) => {
            if (settled) return;
            settled = true;
            const reject = rejectRef;
            cleanup();
            reject?.(error);
        }
    };
};

const runTaskCommand = (options: { command: JsonObject; action: { handlers?: StreamActionHandlers; operation?: Partial<OperationMetadata> | null; timeoutMs?: number }; ws: StreamTaskRuntimeWebSocketClient; safe: StreamTaskSafeInvoker; state: StreamTaskRuntimeState; getTaskSnapshot: SnapshotChecker; emitOperation: TaskOperationEmitter; emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void; finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void; logWarn: StreamTaskDebugLogger; module: string; cancelTask?: (taskId: string, reason: string | null) => Promise<TaskCancellationResponse> }): StreamActionResult => {
    const { command, action, ws, safe, state, getTaskSnapshot, emitOperation, emitTerminalTask, finalizeTaskWatchers, logWarn, module, cancelTask } = options;
    const { handlers = {}, operation = null, timeoutMs } = action;

    const commandTypeValue = command['type'];
    const commandType = toTrimmedString(commandTypeValue);
    if (!commandType) {
        throw new Error('Task command requires a type');
    }

    let acceptedTaskIdWatcher: CommandAcceptedWatcher | null = null;

    return runAcceptedTaskLifecycle({
        acceptTask: () =>
            resolveOptionalKeyedTaskAdmission(state.keyedTaskAdmissions, operation, async () => {
                const runId = createWebSocketRunId(`ws_${commandType}`);
                const payload: JsonObject = { ...command, 'protocol_version': WEBSOCKET_PROTOCOL_VERSION, 'run_id': runId };
                ws.connect();
                await ws.waitForConnection();
                const watcher = createCommandAcceptedWatcher({
                    ws,
                    runId,
                    timeoutMs: 15000,
                    isSettled: () => acceptedTaskIdWatcher === null,
                    module,
                    logWarn
                });
                acceptedTaskIdWatcher = watcher;
                try {
                    await ws.sendMessage(payload);
                    const acceptedTaskId = await watcher.promise;
                    acceptedTaskIdWatcher = null;
                    return { taskId: acceptedTaskId, endpoint: `ws:${commandType}` };
                } catch (error) {
                    const normalizedError = ensureError(error);
                    watcher.abort(normalizedError);
                    await watcher.promise.catch((watcherError: Error): void => {
                        const normalizedWatcherError = ensureError(watcherError);
                        if (normalizedWatcherError.message !== normalizedError.message) {
                            logWarn(module, 'Command accepted watcher abort failed', normalizedWatcherError);
                        }
                    });
                    acceptedTaskIdWatcher = null;
                    if (!(normalizedError instanceof APIError)) {
                        const recoveredTaskId = await recoverMutationAcceptance(ws, operation, normalizedError);
                        return { taskId: recoveredTaskId, endpoint: `ws:${commandType}` };
                    }
                    throw normalizedError;
                }
            }),
        handlers,
        operation,
        timeoutMs,
        safe,
        state,
        getTaskSnapshot,
        emitOperation,
        emitTerminalTask,
        finalizeTaskWatchers,
        logWarn,
        module,
        cancelTask,
        onError: (error) => {
            acceptedTaskIdWatcher?.abort(error);
            acceptedTaskIdWatcher = null;
        }
    });
};

export { runTaskCommand };
