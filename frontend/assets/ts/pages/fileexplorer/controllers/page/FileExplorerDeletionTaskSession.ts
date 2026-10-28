/* SoAI - File deletion task result reconciliation [frontend/assets/ts/pages/fileexplorer/controllers/page/FileExplorerDeletionTaskSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeTaskResponse } from '@core/api/contracts/taskContracts.ts';
import { createAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import type { StreamTaskRuntimeContract } from '@core/realtime/streammanager/actions/contracts.ts';
import type { StreamWebSocketClient } from '@core/realtime/streammanager/types.ts';
import { isCancelledTaskStatus, isTerminalTaskStatus } from '@core/tasks/operationPayloads.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

interface FileExplorerDeletionTaskRuntime {
    tasks: Pick<StreamTaskRuntimeContract, 'trackAcceptedTask'>;
    connection: { readonly webSocket: Pick<StreamWebSocketClient, 'requestSnapshot'> | null };
}

const awaitFileExplorerDeletionTask = async (runtime: FileExplorerDeletionTaskRuntime, taskId: string, signal: AbortSignal): Promise<JsonObject | null> => {
    throwIfAborted(signal);
    const task = runtime.tasks.trackAcceptedTask(taskId);
    try {
        const terminal = await raceWithAbortSignal(task.finished, signal);
        throwIfAborted(signal);
        if (!isJsonObject(terminal) || terminal['taskId'] !== taskId || typeof terminal['status'] !== 'string' || !isTerminalTaskStatus(terminal['status'])) {
            throw new Error('File deletion task completion does not match its accepted operation');
        }
        if (isJsonObject(terminal['result'])) return terminal['result'];
        const transport = runtime.connection.webSocket;
        if (!transport) throw new Error('File deletion task result transport is unavailable');
        const snapshot = await transport.requestSnapshot('tasks.by_id', { 'task_id': taskId }, { signal });
        throwIfAborted(signal);
        if (!snapshot || snapshot.data === null) throw new Error('File deletion task result is unavailable');
        const completed = decodeTaskResponse(snapshot.data);
        if (completed.taskId !== taskId || !isTerminalTaskStatus(completed.status)) {
            throw new Error('File deletion task result does not match its terminal operation');
        }
        if (completed.result === null && isCancelledTaskStatus(completed.status)) {
            throw createAbortError('File deletion task was cancelled without item results');
        }
        return completed.result;
    } finally {
        task.close?.();
    }
};

export { awaitFileExplorerDeletionTask };
