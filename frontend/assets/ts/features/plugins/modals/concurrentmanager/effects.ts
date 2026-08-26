/* SoAI - Plugins feature concurrent manager effects [frontend/assets/ts/features/plugins/modals/concurrentmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getRestartState, triggerRestartStateBootstrap } from '@core/restartStateService.ts';
import { isFunction } from '@core/typeGuards.ts';
import { dismissPersistentNotifications, showPersistentNotification } from '@core/ui/notifications/notifications.ts';
import { isOverlayWithShow } from '@features/plugins/modals/concurrentmanager/guards.ts';
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

const showConcurrentPluginsRestartNotification = async (host: ConcurrentManagerHost): Promise<void> => {
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
        buttons: [
            {
                text: i18n.t('plugins.notifications.restartButton'),
                variant: 'warning',
                icon: 'restart',
                action: async () => {
                    const powerApi = host.operations.api.system?.power;
                    if (!powerApi || !isFunction(powerApi.restartApplication)) {
                        host.view.showNotification(i18n.t('plugins.notifications.restartFailed'), 'error');
                        return false;
                    }

                    let didRestart = false;
                    try {
                        await powerApi.restartApplication();
                        const overlay = host.operations.getRestartOverlay();
                        if (!isOverlayWithShow(overlay)) {
                            throw new Error('Restart overlay must expose show(type: string)');
                        }
                        overlay.show('restart-application');
                        didRestart = true;
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        errorHandler.error('ConcurrentController', i18n.t('plugins.notifications.restartFailed'), runtimeError);
                    }

                    if (!didRestart) {
                        return false;
                    }
                    return true;
                }
            }
        ]
    });
};

export { ensureConcurrentConfigLoaded, showConcurrentPluginsRestartNotification };
