/* SoAI - Centralized background task attention policy [frontend/assets/ts/core/tasks/backgroundActivityPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveEditionBackgroundActivityOperationTypes } from '@core/tasks/editionTaskCatalog.ts';
import type { TaskOperationEntry, TaskOperationFilter } from '@core/tasks/protocols.ts';
import { isString } from '@core/typeGuards.ts';

const FILE_EXPLORER_OPERATION_TYPE = 'file-explorer-op';
const FILE_EXPLORER_UPLOAD_OPERATIONS = Object.freeze(new Set<string>(['file_explorer_upload', 'file_explorer_upload_batch']));

const CORE_BACKGROUND_ACTIVITY_OPERATION_TYPES = Object.freeze(['backend-install', 'backend-update', 'backend-update-all', 'model-download', 'plugin-download', 'plugin-upload', 'plugin-clone', 'rag-document-upload', 'rag-url-fetch', 'rag-folder-scan', 'software-update', 'backup-create', 'backup-restore', FILE_EXPLORER_OPERATION_TYPE]);

const createBackgroundActivityOperationFilter = (): TaskOperationFilter => ({
    types: resolveEditionBackgroundActivityOperationTypes()
});

const isBackgroundActivityOperation = (operation: TaskOperationEntry): boolean => {
    if (!resolveEditionBackgroundActivityOperationTypes().includes(operation.type)) {
        return false;
    }
    if (operation.type !== FILE_EXPLORER_OPERATION_TYPE) {
        return true;
    }
    const operationName = operation.meta?.['operation'];
    return isString(operationName) && FILE_EXPLORER_UPLOAD_OPERATIONS.has(operationName);
};

const countBackgroundActivityOperations = (operations: readonly TaskOperationEntry[]): number => {
    let count = 0;
    for (const operation of operations) {
        if (isBackgroundActivityOperation(operation)) {
            count += 1;
        }
    }
    return count;
};

export { CORE_BACKGROUND_ACTIVITY_OPERATION_TYPES, countBackgroundActivityOperations, createBackgroundActivityOperationFilter, isBackgroundActivityOperation };
