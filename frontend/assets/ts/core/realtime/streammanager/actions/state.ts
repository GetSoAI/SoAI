/* SoAI - Shared realtime actions state [frontend/assets/ts/core/realtime/streammanager/actions/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildDetachedTaskPayload } from '@core/realtime/streammanager/actions/detachedTaskPayload.ts';
import type { StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';

const createStreamTaskRuntimeState = (): StreamTaskRuntimeState => ({
    generation: 0,
    operationListeners: new Set(),
    operationHandlers: new Map(),
    keyedTaskAdmissions: new Map(),
    trackedTasks: new Map(),
    taskWatchers: new Map(),
    taskRecoveryInFlight: new Map(),
    taskSnapshotChecksInFlight: new Map(),
    taskTerminalHandoffs: new Map(),
    taskReconnectInFlight: null,
    terminalTaskListeners: new Set()
});

const resetStreamTaskRuntimeState = (state: StreamTaskRuntimeState, safeInvoker: StreamTaskSafeInvoker): void => {
    state.generation += 1;
    const supervisedMutationTasks = new Map(
        [...state.trackedTasks].filter(([taskId, metadata]) => {
            const operationKey = metadata['operationKey'];
            const requestId = metadata['requestId'];
            return typeof operationKey === 'string' && operationKey.trim().length > 0 && requestId === taskId && state.keyedTaskAdmissions.get(operationKey)?.requestId === taskId;
        })
    );
    state.operationHandlers.forEach((handler) => {
        safeInvoker(handler.close);
    });
    state.operationHandlers.clear();
    state.taskWatchers.forEach((watchers, taskId) => {
        const payload = buildDetachedTaskPayload(taskId);
        watchers.forEach((watcher) => {
            if (watcher.settled) {
                return;
            }
            watcher.settled = true;
            if (watcher.timeoutId) {
                clearTimeout(watcher.timeoutId);
                watcher.timeoutId = null;
            }
            watcher.resolve(payload);
        });
    });
    state.trackedTasks.clear();
    for (const [taskId, metadata] of supervisedMutationTasks) state.trackedTasks.set(taskId, metadata);
    state.taskWatchers.clear();
    state.taskRecoveryInFlight.clear();
    state.taskSnapshotChecksInFlight.clear();
    state.taskTerminalHandoffs.clear();
    state.taskReconnectInFlight = null;
};

export { createStreamTaskRuntimeState, resetStreamTaskRuntimeState };
