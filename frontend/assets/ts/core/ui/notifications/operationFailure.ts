/* SoAI - Shared UI operation failure [frontend/assets/ts/core/ui/notifications/operationFailure.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasApiStatusNotification, resolveApiStatusErrorMessage, type ApiStatusMessageKeys } from '@core/api/httpStatusNotifications.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { notifyHandledOperationError } from '@core/operationErrorNotifier.ts';
interface OperationFailureNotificationOptions {
    error: Error;
    operation?: string | null | undefined;
    errorMessage?: string | null | undefined;
    fallbackMessage?: string | null | undefined;
    notificationMessage?: string | null | undefined;
    rawMessage?: boolean;
    statusMessages?: ApiStatusMessageKeys | null | undefined;
    onUnhandledError?: ((error: Error) => void) | undefined;
    showNotification: (message: string, level: 'error') => void;
}

interface OperationFailureNotificationHost {
    showNotification: (message: string, type: 'error') => void;
    handleError?: ((error: Error, context: string, options?: { notify?: boolean }) => void) | undefined;
}

interface OperationFailureNotificationNotifyingHost {
    notify: (message: string, type?: 'success' | 'error' | 'info' | 'warning') => void;
    handleError?: ((error: Error, context: string, options?: { notify?: boolean }) => void) | undefined;
}

interface HostedOperationFailureNotificationOptions {
    error: Error;
    host: OperationFailureNotificationHost;
    operation?: string | null | undefined;
    errorMessage?: string | null | undefined;
    fallbackMessage?: string | null | undefined;
    notificationMessage?: string | null | undefined;
    rawMessage?: boolean;
    statusMessages?: ApiStatusMessageKeys | null | undefined;
    context?: string | null | undefined;
    notify?: boolean | undefined;
}

interface DedupingOperationFailureReporterOptions {
    host: OperationFailureNotificationHost;
    dedupeWindowMs?: number | undefined;
}

interface DedupingOperationFailureReporter {
    report(error: Error, options?: Omit<HostedOperationFailureNotificationOptions, 'error' | 'host'>): void;
}

const resolveOperationFailureErrorMessage = (errorMessage: string | null | undefined, fallbackMessage: string | null | undefined): string => {
    const supplied = toTrimmedString(errorMessage);
    if (supplied) {
        return supplied;
    }
    const fallback = toTrimmedString(fallbackMessage);
    return fallback || i18n.t('common.errors.operationFailed');
};

const resolveOperationFailureNotificationMessage = (options: OperationFailureNotificationOptions): string => {
    const errorMessage = resolveOperationFailureErrorMessage(options.errorMessage, options.fallbackMessage);
    const operation = toTrimmedString(options.operation);
    if (operation) {
        return i18n.t('common.errors.operationFailedWithMessage', { operation, error: errorMessage });
    }
    if (options.rawMessage === true) {
        return errorMessage;
    }
    return i18n.t('common.errors.errorWithMessage', { message: errorMessage });
};

const resolveOperationFailureStatusMessage = (options: OperationFailureNotificationOptions): string | null => {
    if (!hasApiStatusNotification(options.error) || !options.statusMessages) {
        return null;
    }
    return resolveApiStatusErrorMessage(options.error.status, options.statusMessages, () =>
        resolveOperationFailureNotificationMessage({
            ...options,
            statusMessages: null
        })
    );
};

const showOperationFailureNotification = (options: OperationFailureNotificationOptions): boolean => {
    if (notifyHandledOperationError(options.error)) {
        return true;
    }
    const statusMessage = resolveOperationFailureStatusMessage(options);
    if (statusMessage) {
        options.showNotification(statusMessage, 'error');
        return false;
    }
    options.onUnhandledError?.(options.error);
    const notificationMessage = toTrimmedString(options.notificationMessage);
    if (notificationMessage) {
        options.showNotification(notificationMessage, 'error');
        return false;
    }
    options.showNotification(resolveOperationFailureNotificationMessage(options), 'error');
    return false;
};

const createNotifyingOperationFailureHost = (host: OperationFailureNotificationNotifyingHost): OperationFailureNotificationHost => {
    return {
        showNotification: (message, type): void => host.notify(message, type),
        handleError: host.handleError
    };
};

const showHostedOperationFailureNotification = (options: HostedOperationFailureNotificationOptions): boolean => {
    const context = toTrimmedString(options.context);
    const baseOptions: OperationFailureNotificationOptions = {
        error: options.error,
        operation: options.operation,
        errorMessage: options.errorMessage,
        fallbackMessage: options.fallbackMessage,
        notificationMessage: options.notificationMessage,
        rawMessage: options.rawMessage === true,
        statusMessages: options.statusMessages,
        showNotification: (message): void => options.host.showNotification(message, 'error')
    };
    const handleError = options.host.handleError;
    if (context && handleError) {
        return showOperationFailureNotification({
            ...baseOptions,
            onUnhandledError: (runtimeError: Error): void => {
                handleError(runtimeError, context, { notify: options.notify === true });
            }
        });
    }
    return showOperationFailureNotification(baseOptions);
};

const createDedupingOperationFailureReporter = (options: DedupingOperationFailureReporterOptions): DedupingOperationFailureReporter => {
    const history = new Map<string, number>();
    const dedupeWindowMs = options.dedupeWindowMs ?? 1500;
    return {
        report: (error, reportOptions = {}): void => {
            const message = toTrimmedString(error.message);
            const key = `${error.name}:${message}`;
            const now = Date.now();
            history.forEach((lastAt, historyKey) => {
                if (now - lastAt >= dedupeWindowMs) {
                    history.delete(historyKey);
                }
            });
            const lastAt = history.get(key) ?? 0;
            if (now - lastAt < dedupeWindowMs) {
                return;
            }
            history.set(key, now);
            showHostedOperationFailureNotification({
                ...reportOptions,
                error,
                host: options.host
            });
        }
    };
};

export { createDedupingOperationFailureReporter, createNotifyingOperationFailureHost, showHostedOperationFailureNotification, showOperationFailureNotification };
export type { DedupingOperationFailureReporter, DedupingOperationFailureReporterOptions, HostedOperationFailureNotificationOptions, OperationFailureNotificationHost, OperationFailureNotificationNotifyingHost, OperationFailureNotificationOptions };
