/* SoAI - Shared API HTTP status notifications [frontend/assets/ts/core/api/httpStatusNotifications.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';

interface ApiStatusMessageKeys {
    forbidden: () => string;
    missing: () => string;
    precondition: () => string;
}

interface ApiStatusNotificationHost {
    notify(message: string, type: 'error'): void;
}

const hasApiStatusNotification = <T>(error: T): error is T & APIError => {
    return error instanceof APIError && (error.status === 403 || error.status === 404 || error.status === 412);
};

const resolveApiStatusErrorMessage = (status: number, keys: ApiStatusMessageKeys, defaultMessage: () => string): string => {
    if (status === 403) {
        return keys.forbidden();
    }
    if (status === 404) {
        return keys.missing();
    }
    if (status === 412) {
        return keys.precondition();
    }
    return defaultMessage();
};

const notifyApiStatusError = <T>(host: ApiStatusNotificationHost, error: T, keys: ApiStatusMessageKeys): boolean => {
    if (!hasApiStatusNotification(error)) {
        return false;
    }
    host.notify(resolveApiStatusErrorMessage(error.status, keys, keys.precondition), 'error');
    return true;
};

export { hasApiStatusNotification, notifyApiStatusError, resolveApiStatusErrorMessage };
export type { ApiStatusMessageKeys, ApiStatusNotificationHost };
