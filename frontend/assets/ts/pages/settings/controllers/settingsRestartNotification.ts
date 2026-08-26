/* SoAI - Settings page restart notification [frontend/assets/ts/pages/settings/controllers/settingsRestartNotification.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getRestartState, triggerRestartStateBootstrap } from '@core/restartStateService.ts';
import { dismissPersistentNotifications, showPersistentNotification } from '@core/ui/notifications/notifications.ts';
import type { OperationType } from '@features/overlays/public.ts';

interface SettingsRestartNotificationHost {
    restartApplication(): Promise<void>;
    showRestartOverlay(value: OperationType): void;
}

const showSettingsRestartNotification = async (host: SettingsRestartNotificationHost): Promise<void> => {
    await triggerRestartStateBootstrap('settings-save');
    const restartState = getRestartState();
    const required = Boolean(restartState?.required);
    const message = i18n.t('settings.notifications.restartRequired');
    if (!required) {
        dismissPersistentNotifications(message);
        return;
    }

    showPersistentNotification({
        message,
        type: 'warning',
        icon: 'restart',
        buttons: [
            {
                text: i18n.t('settings.notifications.restartButton'),
                variant: 'warning',
                icon: 'restart',
                action: async () => {
                    await host.restartApplication();
                    host.showRestartOverlay('restart-application');
                }
            }
        ]
    });
};

export { showSettingsRestartNotification };
export type { SettingsRestartNotificationHost };
