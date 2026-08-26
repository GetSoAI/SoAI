/* SoAI - Shared page context notifications service [frontend/assets/ts/core/pagecontext/notifications/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isString } from '@core/typeGuards.ts';
import type { NotificationApi, NotificationHandler } from '@core/pagecontext/contracts.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';

const createNotificationApi = (notifier: NotificationHandler, pageId: string): NotificationApi => {
    if (!isFunction(notifier)) {
        throw new Error('PageContext requires a notification handler');
    }
    const invoke = (message: string, type: NotificationType = 'info', duration: number = 3000): void => {
        if (!isString(message)) {
            throw new Error(`PageContext notifications require a message for ${pageId}`);
        }
        const trimmed = message.trim();
        if (!trimmed) {
            throw new Error(`PageContext notifications require a message for ${pageId}`);
        }
        notifier(trimmed, type, duration);
    };
    return Object.freeze({
        show: invoke,
        success: (message: string, duration: number = 3000) => invoke(message, 'success', duration),
        warning: (message: string, duration: number = 4000) => invoke(message, 'warning', duration),
        error: (message: string, duration: number = 6000) => invoke(message, 'error', duration),
        info: (message: string, duration: number = 3000) => invoke(message, 'info', duration)
    });
};

export { createNotificationApi };
