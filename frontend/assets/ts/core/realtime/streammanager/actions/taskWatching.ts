/* SoAI - Shared realtime task watching [frontend/assets/ts/core/realtime/streammanager/actions/taskWatching.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { buildDetachedTaskPayload } from '@core/realtime/streammanager/actions/detachedTaskPayload.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { TaskWatcher } from '@core/realtime/streammanager/types.ts';
import { finalizeTaskWatchers, removeTaskWatcher } from '@core/realtime/streammanager/actions/events.ts';
import type { StreamTaskRuntimeState } from '@core/realtime/streammanager/actions/internalContracts.ts';
import type { StreamTaskSafeInvoker } from '@core/realtime/streammanager/actions/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveTaskWatchTimeoutMs } from '@core/realtime/streammanager/actions/taskSupervisionPolicy.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { consumeTaskTerminalHandoff } from '@core/realtime/streammanager/actions/taskTerminalHandoff.ts';

interface SnapshotChecker {
    (taskId: string): Promise<void>;
}

interface TaskWatchResult {
    finished: Promise<JsonValue | null>;
    close: () => void;
}

const watchTask = (options: { taskId: string; handlers: StreamActionHandlers; timeoutMs?: number; state: StreamTaskRuntimeState; safe: StreamTaskSafeInvoker; checkTaskSnapshot: SnapshotChecker }): TaskWatchResult => {
    const normalizedTaskId = toTrimmedString(options.taskId);
    if (!normalizedTaskId) throw new Error('Task id is required');
    const timeoutMs = resolveTaskWatchTimeoutMs(options.timeoutMs);

    const watchers = options.state.taskWatchers.get(normalizedTaskId) ?? new Set<TaskWatcher>();
    if (!options.state.taskWatchers.has(normalizedTaskId)) {
        options.state.taskWatchers.set(normalizedTaskId, watchers);
    }
    const completion = createDeferred<JsonValue | null>();
    const watcher: TaskWatcher = {
        handlers: options.handlers,
        resolve: completion.resolve,
        reject: completion.reject,
        timeoutId: null,
        settled: false
    };
    const timeoutId = setTimeout(() => {
        watcher.timeoutId = null;
        watcher.settled = true;
        removeTaskWatcher(options.state, normalizedTaskId, watcher);
        const error = new Error(`Task supervision timeout: ${normalizedTaskId}`);
        options.safe(watcher.handlers.onError, error);
        watcher.reject(error);
    }, timeoutMs);
    watcher.timeoutId = timeoutId;
    watchers.add(watcher);
    const terminalHandoff = consumeTaskTerminalHandoff(options.state, normalizedTaskId);
    if (terminalHandoff) {
        finalizeTaskWatchers(options.state, options.safe, normalizedTaskId, terminalHandoff);
    } else {
        terminateHandledPromise(options.checkTaskSnapshot(normalizedTaskId));
    }

    return {
        finished: completion.promise,
        close: () => {
            if (watcher.settled) return;
            watcher.settled = true;
            clearTimeout(timeoutId);
            watcher.timeoutId = null;
            removeTaskWatcher(options.state, normalizedTaskId, watcher);
            watcher.resolve(buildDetachedTaskPayload(normalizedTaskId));
        }
    };
};

export { type SnapshotChecker, watchTask };
