/* SoAI - File explorer page guards implementation [frontend/assets/ts/pages/fileexplorer/guards/pageGuards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { FileExplorerApi } from '@pages/fileexplorer/types.ts';

const isFileExplorerApi = (value: FileExplorerApi | JsonValue | null | undefined): value is FileExplorerApi => {
    if (!isObject(value)) return false;
    const methods: readonly (keyof FileExplorerApi)[] = ['list', 'search', 'startListing', 'getListingPage', 'locateListingEntry', 'releaseListing', 'metadata', 'read', 'write', 'mkdir', 'delete', 'batchDelete', 'batchDeleteTask', 'move', 'batchMove', 'batchMoveTask', 'copy', 'batchCopy', 'batchCopyTask', 'hash', 'download', 'downloadSelection', 'upload', 'uploadBatch'];
    return hasFunctionProperties(value, methods);
};

export { isFileExplorerApi };
