/* SoAI - File Explorer UI task scheduler [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerUiTaskSchedulerController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createUiTaskScheduler, type UiTaskRoute, type UiTaskScheduler, type UiTaskSchedulerHost } from '@core/concurrency/uiTaskScheduler.ts';
import { FILE_EXPLORER_ACTION_COPY_HERE, FILE_EXPLORER_ACTION_MOVE_HERE, FILE_EXPLORER_ACTION_NEW_ENTRY, FILE_EXPLORER_ACTION_REFRESH, FILE_EXPLORER_ACTION_ROW_OPEN, FILE_EXPLORER_ACTION_SELECTION_DELETE, FILE_EXPLORER_ACTION_SELECTION_RENAME, FILE_EXPLORER_ACTION_SORT, FILE_EXPLORER_ACTION_UPLOAD_FILES } from '@features/fileexplorer/public.ts';

type FileExplorerUiTaskScheduler = UiTaskScheduler;
type FileExplorerUiTaskSchedulerHost = UiTaskSchedulerHost;

const clickOperationId = (actionId: string): string => `fileExplorer:click:${actionId}`;
const changeOperationId = (actionId: string): string => `fileExplorer:change:${actionId}`;

const FILE_EXPLORER_MUTATION_OPERATION_IDS: ReadonlySet<string> = new Set([clickOperationId(FILE_EXPLORER_ACTION_COPY_HERE), clickOperationId(FILE_EXPLORER_ACTION_MOVE_HERE), clickOperationId(FILE_EXPLORER_ACTION_SELECTION_DELETE)]);

const resolveFileExplorerUiTaskRoute = (operationId: string): UiTaskRoute => {
    if (operationId === clickOperationId(FILE_EXPLORER_ACTION_REFRESH)) {
        return { key: 'fileExplorer:refresh', policy: 'start-latest' };
    }
    if (operationId === clickOperationId(FILE_EXPLORER_ACTION_ROW_OPEN)) {
        return { key: 'fileExplorer:navigation', policy: 'start-latest' };
    }
    if (operationId === 'fileExplorer:navigate:home' || operationId === 'fileExplorer:navigate:previous' || operationId === 'fileExplorer:navigate:next' || operationId === 'fileExplorer:navigate:up' || operationId === 'fileExplorer:navigate:path') {
        return { key: 'fileExplorer:navigation', policy: 'start-latest' };
    }
    if (operationId === clickOperationId(FILE_EXPLORER_ACTION_SORT) || operationId === changeOperationId(FILE_EXPLORER_ACTION_SORT)) {
        return { key: 'fileExplorer:sort', policy: 'serialize' };
    }
    if (operationId === 'fileExplorer:search:query' || operationId === 'fileExplorer:search:clear') {
        return { key: 'fileExplorer:search', policy: 'start-latest' };
    }
    if (operationId === 'fileExplorer:listing:next') {
        return { key: 'fileExplorer:listing:next', policy: 'drop-if-busy' };
    }
    if (operationId === changeOperationId(FILE_EXPLORER_ACTION_UPLOAD_FILES)) {
        return { key: 'fileExplorer:upload', policy: 'serialize' };
    }
    if (operationId === changeOperationId(FILE_EXPLORER_ACTION_NEW_ENTRY)) {
        return { key: 'fileExplorer:newEntry', policy: 'drop-if-busy' };
    }
    if (operationId === clickOperationId(FILE_EXPLORER_ACTION_SELECTION_RENAME)) {
        return { key: 'fileExplorer:taskMutation', policy: 'drop-if-busy' };
    }
    if (FILE_EXPLORER_MUTATION_OPERATION_IDS.has(operationId)) {
        return { key: 'fileExplorer:taskMutation', policy: 'drop-if-busy' };
    }
    return { key: operationId, policy: 'serialize' };
};

const createFileExplorerUiTaskScheduler = (host: FileExplorerUiTaskSchedulerHost): FileExplorerUiTaskScheduler => {
    return createUiTaskScheduler(host, resolveFileExplorerUiTaskRoute);
};

export { createFileExplorerUiTaskScheduler };
export type { FileExplorerUiTaskScheduler, FileExplorerUiTaskSchedulerHost };
