/* SoAI - File explorer page control layer HTTP error controller [frontend/assets/ts/pages/fileexplorer/controllers/fileExplorerHttpErrorController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNetworkError, isRequestTimeoutError } from '@core/apiError.ts';
import { isErrorHttpStatus } from '@core/errors/coerce.ts';
import { DirectoryListingFailure } from '@core/fileexplorerbrowser/directoryListingFailure.ts';
import { hasApiStatusNotification } from '@core/api/httpStatusNotifications.ts';
import { FILE_EXPLORER_HTTP_STATUS_MESSAGES } from '@core/api/statusMessageCatalog.ts';
import { resolveFileExplorerBrowserStatusMessage } from '@core/fileexplorerbrowser/errorMessages.ts';
import { i18n } from '@core/i18n/index.ts';
import { showHostedOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';

interface FileExplorerHttpErrorHost {
    showNotification(message: string, type: 'error' | 'warning'): void;
}

const resolveListingOperationalMessage = (error: Error): string | null => {
    if (isRequestTimeoutError(error) || isErrorHttpStatus(error, 408) || isErrorHttpStatus(error, 504)) return i18n.t('fileExplorer.errors.listingTimeout');
    if (isErrorHttpStatus(error, 429)) return i18n.t('fileExplorer.errors.listingBusy');
    if (isNetworkError(error) || isErrorHttpStatus(error, 502) || isErrorHttpStatus(error, 503)) return i18n.t('fileExplorer.errors.listingUnavailable');
    return null;
};

const resolveFileExplorerBrowserErrorMessage = (error: Error): string => {
    if (error instanceof DirectoryListingFailure) {
        if (error.reason === 'changed') return i18n.t('fileExplorer.errors.listingChanged');
        if (error.reason === 'timeout') return i18n.t('fileExplorer.errors.listingTimeout');
        return i18n.t('fileExplorer.errors.listingIncoherent');
    }
    return resolveFileExplorerBrowserStatusMessage(error, {
        ...FILE_EXPLORER_HTTP_STATUS_MESSAGES,
        fallback: (): string => resolveListingOperationalMessage(error) ?? i18n.t('fileExplorer.status.error')
    });
};

const notifyFileExplorerBrowserError = (host: FileExplorerHttpErrorHost, error: Error): boolean => {
    if (error instanceof DirectoryListingFailure) {
        host.showNotification(resolveFileExplorerBrowserErrorMessage(error), error.reason === 'incoherent' ? 'error' : 'warning');
        return true;
    }
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

const notifyFileExplorerListingFailure = (host: FileExplorerHttpErrorHost, error: Error): boolean => {
    if (resolveListingOperationalMessage(error) !== null) {
        host.showNotification(resolveFileExplorerBrowserErrorMessage(error), 'warning');
        return true;
    }
    return notifyFileExplorerBrowserError(host, error);
};

export { notifyFileExplorerBrowserError, notifyFileExplorerListingFailure, resolveFileExplorerBrowserErrorMessage };
