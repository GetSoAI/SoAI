/* SoAI - Shared realtime HTTP task action [frontend/assets/ts/core/realtime/streammanager/actions/httpTaskAction.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { runAcceptedTaskLifecycle } from '@core/realtime/streammanager/actions/acceptedTaskLifecycle.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import type { SnapshotChecker } from '@core/realtime/streammanager/actions/taskWatching.ts';
import type { StreamTaskActionPayload, StreamTaskDebugLogger, StreamTaskRequest, StreamTaskSafeInvoker, StreamTaskWebSocketProvider } from '@core/realtime/streammanager/actions/types.ts';
import type { TaskOperationEmitter } from '@core/realtime/streammanager/actions/acceptedTaskOperation.ts';
import type { OperationMetadata, StreamActionResult } from '@core/realtime/streammanager/types.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { TaskCancellationResponse } from '@core/api/contracts/systemContracts.ts';
import { resolveOptionalKeyedTaskAdmission } from '@core/realtime/streammanager/actions/keyedTaskAdmission.ts';
import { isNetworkError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { recoverMutationAcceptance } from '@core/realtime/streammanager/actions/mutationAcceptanceRecovery.ts';

const runTaskAction = (options: { endpoint: string; action: StreamTaskActionPayload; request: StreamTaskRequest; getWebSocket: StreamTaskWebSocketProvider; safe: StreamTaskSafeInvoker; state: StreamTaskRuntimeState; getTaskSnapshot: SnapshotChecker; emitOperation: TaskOperationEmitter; emitTerminalTask: (taskId: string, payload: JsonObject, meta?: OperationMetadata | null) => void; finalizeTaskWatchers: (taskId: string, payload: JsonObject) => void; logWarn: StreamTaskDebugLogger; module: string; cancelTask?: (taskId: string, reason: string | null) => Promise<TaskCancellationResponse> }): StreamActionResult => {
    const { endpoint, action, request, safe, state, getTaskSnapshot, emitOperation, emitTerminalTask, finalizeTaskWatchers, logWarn, module, cancelTask } = options;
    const { method = 'POST', body = null, headers = {}, handlers = {}, operation = null, allowDiscovery, timeoutMs } = action;

    return runAcceptedTaskLifecycle({
        acceptTask: () =>
            resolveOptionalKeyedTaskAdmission(state.keyedTaskAdmissions, operation, async () => {
                let response: Response | null;
                try {
                    response = await request(endpoint, {
                        method,
                        body,
                        headers,
                        ...(typeof allowDiscovery === 'boolean' ? { allowDiscovery } : {})
                    });
                } catch (error) {
                    const normalizedError = ensureError(error);
                    if (!isNetworkError(normalizedError)) throw normalizedError;
                    errorHandler.warn('StreamTaskAction', 'Task admission response interrupted; reconciling by mutation identity', normalizedError);
                    const recoveredTaskId = await recoverMutationAcceptance(options.getWebSocket(), operation, normalizedError);
                    return { taskId: recoveredTaskId, endpoint };
                }
                const taskId = toTrimmedString(response?.headers?.get('X-SoAI-Task-Id'));
                if (!taskId) {
                    const missingTaskError = new Error('Task action response missing task_id');
                    const recoveredTaskId = await recoverMutationAcceptance(options.getWebSocket(), operation, missingTaskError);
                    return { taskId: recoveredTaskId, endpoint };
                }
                return { taskId, endpoint };
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
        cancelTask
    });
};

export { runTaskAction };
