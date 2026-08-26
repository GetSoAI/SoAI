/* SoAI - Shared UI native android bridge [frontend/assets/ts/core/ui/notifications/nativeAndroidBridge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { NotificationType } from '@core/ui/notifications/types.ts';

interface SoAIAndroidNotificationsBridge {
    showNotification: (payloadJson: string) => void;
}

declare global {
    interface Window {
        SoAIAndroidNotifications?: SoAIAndroidNotificationsBridge;
        SoAIAndroidNotificationsToken?: string;
    }
}

const showAndroidNativeNotification = (message: string, type: NotificationType): void => {
    const bridge = window.SoAIAndroidNotifications;
    if (!bridge) {
        return;
    }
    const token = window.SoAIAndroidNotificationsToken;
    if (!token) {
        return;
    }
    try {
        bridge.showNotification(JSON.stringify({ message, token, type }));
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn('Notifications', 'Android notification bridge failed', runtimeError);
    }
};

export { showAndroidNativeNotification };
