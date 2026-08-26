/* SoAI - File explorer page control layer HTTP error controller [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasApiStatusNotification } from '@core/api/httpStatusNotifications.ts';
import { FILE_EXPLORER_HTTP_STATUS_MESSAGES } from '@core/api/statusMessageCatalog.ts';
import { resolveFileExplorerBrowserStatusMessage } from '@core/fileexplorerbrowser/errorMessages.ts';
import { i18n } from '@core/i18n/index.ts';
import { showHostedOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';

interface FileExplorerHttpErrorHost {
    showNotification(message: string, type: 'error'): void;
}

const resolveFileExplorerBrowserErrorMessage = (error: Error): string => {
    return resolveFileExplorerBrowserStatusMessage(error, {
        ...FILE_EXPLORER_HTTP_STATUS_MESSAGES,
        fallback: (): string => i18n.t('fileExplorer.status.error')
    });
};

const notifyFileExplorerHttpError = (host: FileExplorerHttpErrorHost, error: Error): boolean => {
    if (!hasApiStatusNotification(error)) {
        return false;
    }
    showHostedOperationFailureNotification({
        host,
        error,
        statusMessages: FILE_EXPLORER_HTTP_STATUS_MESSAGES,
        notificationMessage: i18n.t('fileExplorer.status.error')
    });
    return true;
};

export { notifyFileExplorerHttpError, resolveFileExplorerBrowserErrorMessage };
