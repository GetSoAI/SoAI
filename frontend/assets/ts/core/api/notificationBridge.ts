/* SoAI - Shared API notification bridge [frontend/assets/ts/core/api/notificationBridge.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { APIErrorMetadataValue } from '@core/apiError.ts';

type ApiNotificationType = 'success' | 'error' | 'warning' | 'danger' | 'info';

interface ApiNotificationBridge {
    showNotification: (message: string, type: ApiNotificationType, durationMs: number) => HTMLElement;
    notifyHandledOperationError: (error: APIErrorMetadataValue) => boolean;
}

let activeBridge: ApiNotificationBridge | null = null;

const setApiNotificationBridge = (bridge: ApiNotificationBridge): void => {
    if (activeBridge) {
        if (activeBridge === bridge) {
            return;
        }
        throw new Error('API notification bridge is already configured');
    }
    activeBridge = bridge;
};

const resetApiNotificationBridge = (): void => {
    activeBridge = null;
};

const requireApiNotificationBridge = (): ApiNotificationBridge => {
    if (!activeBridge) {
        throw new Error('API notification bridge is not configured');
    }
    return activeBridge;
};

const getApiNotificationBridge = (): ApiNotificationBridge | null => activeBridge;

export { getApiNotificationBridge, requireApiNotificationBridge, resetApiNotificationBridge, setApiNotificationBridge };
export type { ApiNotificationBridge, ApiNotificationType };
