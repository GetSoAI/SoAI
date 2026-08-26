/* SoAI - File explorer page control layer service [frontend/assets/ts/pages/fileexplorer/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFileExplorerApi } from '@pages/fileexplorer/guards/pageGuards.ts';
import type { FileExplorerControllerHost } from '@pages/fileexplorer/types.ts';

const createFileExplorerControllerHost = (
    apiCandidate: FileExplorerControllerHost['api'] | JsonValue | null | undefined,
    dependencies: {
        showNotification: (message: string, type: NotificationType) => void;
        handleError: (error: Error, context: string, options?: { notify?: boolean }) => void;
        getIconSync: FileExplorerControllerHost['getIconSync'];
        awaitTask: FileExplorerControllerHost['awaitTask'];
    }
): FileExplorerControllerHost => {
    if (!isFileExplorerApi(apiCandidate)) {
        throw new Error('File Explorer API client is not available');
    }
    return {
        api: apiCandidate,
        awaitTask: dependencies.awaitTask,
        showNotification: dependencies.showNotification,
        handleError: dependencies.handleError,
        getIconSync: dependencies.getIconSync
    };
};

export { createFileExplorerControllerHost };
