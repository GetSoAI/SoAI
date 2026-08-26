/* SoAI - File Explorer listing task completion session [frontend/assets/ts/pages/fileexplorer/controllers/page/DirectoryListingTaskSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { createTaskFailureError } from '@core/operationErrorNotifier.ts';
import type { StreamActionResult } from '@core/realtime/streammanager/types.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';

const awaitDirectoryListingTask = async (trackTask: (taskId: string) => StreamActionResult, taskId: string, signal: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const task = trackTask(taskId);
    try {
        const terminalPayload = await raceWithAbortSignal(task.finished, signal);
        if (!isJsonObject(terminalPayload) || terminalPayload['success'] !== true) {
            throw createTaskFailureError(terminalPayload, 'Directory indexing failed.');
        }
    } finally {
        task.close?.();
    }
};

export { awaitDirectoryListingTask };
