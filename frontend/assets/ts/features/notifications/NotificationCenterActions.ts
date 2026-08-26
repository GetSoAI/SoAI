/* SoAI - Notifications feature notification center actions [frontend/assets/ts/features/notifications/NotificationCenterActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { handleApiResult } from '@core/api/apiResultHandler.ts';
import { notificationOpenPath, notificationPath, notificationsMarkReadPath, notificationsPath } from '@core/api/endpoints/uiPaths.ts';
import type { ApiClient } from '@core/api/service.ts';
import { i18n } from '@core/i18n/index.ts';
import { trimStringList } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const LOG_ID = 'NotificationCenter';

const serializeNotificationReadRequest = (notificationIds: string[]): JsonObject => ({
    'notification_ids': notificationIds
});

class NotificationCenterActions {
    readonly #apiClient: ApiClient;

    constructor(apiClient: ApiClient) {
        this.#apiClient = apiClient;
    }

    async markNotificationsRead(notificationIds: string[]): Promise<void> {
        const normalizedIds = trimStringList(notificationIds);
        if (normalizedIds.length === 0) {
            return;
        }
        await handleApiResult(this.#apiClient.post(notificationsMarkReadPath(), serializeNotificationReadRequest(normalizedIds)), {
            boundaryName: LOG_ID,
            notifyOnError: false,
            logErrors: true,
            rethrow: true
        });
    }

    async clearAll(): Promise<boolean> {
        const confirmed = await requireDialogsService().showConfirmation({
            title: i18n.t('header.notificationCenter.actions.clearAll'),
            message: i18n.t('header.notificationCenter.confirmations.clearAllMessage'),
            confirmText: i18n.t('header.notificationCenter.actions.clearAll'),
            cancelText: i18n.t('common.cancel')
        });
        if (!confirmed) {
            return false;
        }
        const result = await handleApiResult(this.#apiClient.delete(notificationsPath()), {
            boundaryName: LOG_ID,
            notifyOnError: true,
            logErrors: true,
            rethrow: false,
            notifyErrorMessage: i18n.t('common.errors.unknownError')
        });
        return result !== null;
    }

    async openNotification(notificationId: string): Promise<boolean> {
        const normalizedId = isString(notificationId) ? notificationId.trim() : '';
        if (!normalizedId) {
            throw new Error('NotificationCenter open requires a notification id');
        }
        const result = await handleApiResult(this.#apiClient.post(notificationOpenPath(normalizedId), {}), {
            boundaryName: LOG_ID,
            notifyOnError: false,
            logErrors: true,
            rethrow: false
        });
        return result !== null;
    }

    async deleteOne(notificationId: string): Promise<boolean> {
        const normalizedId = isString(notificationId) ? notificationId.trim() : '';
        if (!normalizedId) {
            throw new Error('NotificationCenter delete requires a notification id');
        }
        const result = await handleApiResult(this.#apiClient.delete(notificationPath(normalizedId)), {
            boundaryName: LOG_ID,
            notifyOnError: true,
            logErrors: true,
            rethrow: false,
            notifyErrorMessage: i18n.t('common.errors.unknownError')
        });
        return result !== null;
    }
}

export { NotificationCenterActions };
