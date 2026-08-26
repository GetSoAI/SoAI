/* SoAI - Notifications feature notification center contracts [frontend/assets/ts/features/notifications/NotificationCenterContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { NotificationCenterStreamManager } from '@features/notifications/NotificationCenterDataController.ts';

interface NotificationCenterHeaderApi {
    closeDropdowns: (options?: { except?: string | string[] | undefined }) => void;
}

interface NotificationCenterDependencies {
    dom: { getDocument: () => Document };
    header: NotificationCenterHeaderApi;
    apiClient: ApiClient;
    stream: NotificationCenterStreamManager;
}

const validateNotificationCenterDependencies = (dependencies: NotificationCenterDependencies): void => {
    if (!dependencies) {
        throw new Error('NotificationCenter requires deps');
    }
    if (!dependencies.dom || !isFunction(dependencies.dom.getDocument)) {
        throw new Error('NotificationCenter requires dom.getDocument');
    }
    if (!dependencies.header || !isFunction(dependencies.header.closeDropdowns)) {
        throw new Error('NotificationCenter requires a layout header controller');
    }
    if (!dependencies.apiClient || !isFunction(dependencies.apiClient.get) || !isFunction(dependencies.apiClient.post) || !isFunction(dependencies.apiClient.delete)) {
        throw new Error('NotificationCenter requires apiClient');
    }
    if (!dependencies.stream) {
        throw new Error('NotificationCenter requires stream owners');
    }
};

export { validateNotificationCenterDependencies };
export type { NotificationCenterDependencies, NotificationCenterHeaderApi };
