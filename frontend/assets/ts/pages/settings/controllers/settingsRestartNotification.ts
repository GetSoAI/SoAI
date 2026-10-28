/* SoAI - Settings page restart notification [frontend/assets/ts/pages/settings/controllers/settingsRestartNotification.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { createRestartNotificationButton } from '@core/restartNotificationAction.ts';
import type { RestartState } from '@core/restartStateGateway.ts';
import { getRestartState, triggerRestartStateBootstrap } from '@core/restartStateService.ts';
import { dismissPersistentNotifications, showPersistentNotification } from '@core/ui/notifications/notifications.ts';

const showSettingsRestartNotification = async (): Promise<void> => {
    await triggerRestartStateBootstrap('settings-save');
    projectSettingsRestartNotification(getRestartState());
};

const projectSettingsRestartNotification = (restartState: RestartState): void => {
    const message = i18n.t('settings.notifications.restartRequired');
    if (!restartState.required) {
        dismissPersistentNotifications(message);
        return;
    }
    showPersistentNotification({
        message,
        type: 'warning',
        icon: 'restart',
        buttons: [createRestartNotificationButton(i18n.t('settings.notifications.restartButton'))]
    });
};

export { projectSettingsRestartNotification, showSettingsRestartNotification };
