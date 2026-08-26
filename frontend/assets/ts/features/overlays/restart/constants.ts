/* SoAI - Overlays feature restart constants [frontend/assets/ts/features/overlays/restart/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { minutesToMs } from '@core/time/durations.ts';
import type { OperationType, PersistentRestartOperationType, RestartContent } from '@features/overlays/restart/types.ts';

const DEFAULT_MAX_RETRIES = 300;
const REBOOT_MAX_RETRIES = 900;
const RESTART_CACHE_TTL_MS = minutesToMs(10);
const RESTART_OVERLAY_SERVICE_ID = 'features.overlays.restart';
const RESTART_STATUS_ICON_HIDDEN_CLASS = 'restart-overlay--status-icon-hidden';

const getRestartContent = (type: OperationType): RestartContent => {
    switch (type) {
        case 'restart-application':
            return {
                message: i18n.t('restartOverlay.messages.restarting'),
                description: i18n.t('restartOverlay.descriptions.restarting'),
                statusIcon: 'restart-application'
            };
        case 'system-reboot':
            return {
                message: i18n.t('restartOverlay.messages.rebooting'),
                description: i18n.t('restartOverlay.descriptions.rebooting'),
                statusIcon: 'restart'
            };
        case 'system-shutdown':
            return {
                message: i18n.t('restartOverlay.messages.shutdown'),
                description: i18n.t('restartOverlay.descriptions.shutdown'),
                statusIcon: 'system-power-cycle'
            };
        case 'system-sleep':
            return {
                message: i18n.t('restartOverlay.messages.sleep'),
                description: i18n.t('restartOverlay.descriptions.sleep'),
                statusIcon: 'system-power-cycle'
            };
        case 'update-soai':
            return {
                message: i18n.t('restartOverlay.messages.updating'),
                description: i18n.t('restartOverlay.descriptions.updating'),
                statusIcon: 'application-power-cycle'
            };
        case 'connection-lost':
            return {
                message: i18n.t('restartOverlay.messages.connectionLost'),
                description: i18n.t('restartOverlay.descriptions.connectionLost'),
                statusIcon: 'connection-offline'
            };
        case 'restore-backup':
            return {
                message: i18n.t('restartOverlay.messages.pleaseWait'),
                description: i18n.t('restartOverlay.descriptions.generic'),
                statusIcon: 'application-power-cycle'
            };
    }
};

const shouldPollForRestartOperation = (type: OperationType): boolean => type !== 'system-shutdown' && type !== 'system-sleep' && type !== 'connection-lost';

const shouldPersistRestartOperation = (type: OperationType): type is PersistentRestartOperationType => type !== 'connection-lost';

export { DEFAULT_MAX_RETRIES, REBOOT_MAX_RETRIES, RESTART_CACHE_TTL_MS, RESTART_OVERLAY_SERVICE_ID, RESTART_STATUS_ICON_HIDDEN_CLASS, getRestartContent, shouldPersistRestartOperation, shouldPollForRestartOperation };
