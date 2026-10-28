/* SoAI - Plugins feature concurrent manager effects [frontend/assets/ts/features/plugins/modals/concurrentmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { createRestartNotificationButton } from '@core/restartNotificationAction.ts';
import { getRestartState, triggerRestartStateBootstrap } from '@core/restartStateService.ts';
import { dismissPersistentNotifications, showPersistentNotification } from '@core/ui/notifications/notifications.ts';
import type { ConcurrentManagerHost } from '@features/plugins/modals/concurrentmanager/types.ts';

const ensureConcurrentConfigLoaded = async (host: ConcurrentManagerHost): Promise<void> => {
    const maxConcurrent = host.state.getMaxConcurrentPlugins();
    if (typeof maxConcurrent === 'number' && Number.isFinite(maxConcurrent)) {
        return;
    }

    try {
        await host.operations.loadCoreConfig({ force: true });
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('ConcurrentController', i18n.t('plugins.notifications.concurrentPluginsLoadFailed'), runtimeError);
        host.view.showNotification(i18n.t('plugins.notifications.concurrentPluginsLoadFailed'), 'error');
    }
};

const showConcurrentPluginsRestartNotification = async (): Promise<void> => {
    const message = i18n.t('plugins.notifications.restartRequired');
    await triggerRestartStateBootstrap('concurrent-plugins-save');
    const restartState = getRestartState();
    const required = Boolean(restartState?.required);
    if (!required) {
        dismissPersistentNotifications(message);
        return;
    }

    showPersistentNotification({
        message,
        type: 'warning',
        icon: 'restart',
        buttons: [createRestartNotificationButton(i18n.t('plugins.notifications.restartButton'))]
    });
};

export { ensureConcurrentConfigLoaded, showConcurrentPluginsRestartNotification };
