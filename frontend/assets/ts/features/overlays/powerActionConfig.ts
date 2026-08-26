/* SoAI - Power action overlay configuration [frontend/assets/ts/features/overlays/powerActionConfig.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';

type PowerActionKey = 'shutdownSystem' | 'shutdownApplication' | 'suspendSystem' | 'hibernateSystem';

interface ActionConfigEntry {
    overlayClass: string;
    statusIcon: IconName;
    getTitle: () => string;
    getMonitoring: () => string;
    getOffline: () => string;
}

const ACTION_CONFIG: Record<PowerActionKey, ActionConfigEntry> = {
    shutdownSystem: {
        overlayClass: 'power-overlay--danger',
        statusIcon: 'power',
        getTitle: () => i18n.t('power.actions.shutdownSystem.overlayMessage'),
        getMonitoring: () => i18n.t('power.overlays.shutdown.monitoring'),
        getOffline: () => i18n.t('power.overlays.shutdown.offline')
    },
    shutdownApplication: {
        overlayClass: 'power-overlay--warning',
        statusIcon: 'shutdown-application',
        getTitle: () => i18n.t('power.actions.shutdownApplication.overlayMessage'),
        getMonitoring: () => i18n.t('power.overlays.applicationShutdown.monitoring'),
        getOffline: () => i18n.t('power.overlays.applicationShutdown.offline')
    },
    suspendSystem: {
        overlayClass: 'power-overlay--suspend',
        statusIcon: 'suspend',
        getTitle: () => i18n.t('power.actions.suspendSystem.overlayMessage'),
        getMonitoring: () => i18n.t('power.overlays.suspend.monitoring'),
        getOffline: () => i18n.t('power.overlays.suspend.offline')
    },
    hibernateSystem: {
        overlayClass: 'power-overlay--info',
        statusIcon: 'hibernate',
        getTitle: () => i18n.t('power.actions.hibernateSystem.overlayMessage'),
        getMonitoring: () => i18n.t('power.overlays.hibernate.monitoring'),
        getOffline: () => i18n.t('power.overlays.hibernate.offline')
    }
};

const POLL_INTERVAL_MS = 1000;
const REQUEST_TIMEOUT_MS = 5000;

const isPowerActionKey = (value: string): value is PowerActionKey => {
    return value === 'shutdownSystem' || value === 'shutdownApplication' || value === 'suspendSystem' || value === 'hibernateSystem';
};

export { ACTION_CONFIG, POLL_INTERVAL_MS, REQUEST_TIMEOUT_MS, isPowerActionKey, type ActionConfigEntry, type PowerActionKey };
