/* SoAI - Settings page backup operation messages controller [frontend/assets/ts/pages/settings/controllers/backupmanager/backupOperationMessagesController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { BackupOperationState } from '@core/settings/contracts.ts';

const resolveBackupProgressLabel = (taskType: BackupOperationState['type']): string => {
    switch (taskType) {
        case 'create':
            return i18n.t('settings.backup.progress.create');
        case 'restore':
            return i18n.t('settings.backup.progress.restore');
        case 'verify':
            return i18n.t('settings.backup.progress.verify');
        case 'delete':
            return i18n.t('settings.backup.progress.delete');
        default: {
            const exhaustive: never = taskType;
            throw new Error(`Unhandled backup task type: ${exhaustive}`);
        }
    }
};

const resolveBackupSuccessNotification = (taskType: BackupOperationState['type']): string => {
    switch (taskType) {
        case 'create':
            return i18n.t('settings.backup.notifications.createSuccess');
        case 'restore':
            return i18n.t('settings.backup.notifications.restoreSuccess');
        case 'verify':
            return i18n.t('settings.backup.notifications.verifySuccess');
        case 'delete':
            return i18n.t('settings.backup.notifications.deleteSuccess');
        default: {
            const exhaustive: never = taskType;
            throw new Error(`Unhandled backup task type: ${exhaustive}`);
        }
    }
};

const resolveBackupFailureNotification = (taskType: BackupOperationState['type']): string => {
    switch (taskType) {
        case 'create':
            return i18n.t('settings.backup.notifications.createFailed');
        case 'restore':
            return i18n.t('settings.backup.notifications.restoreFailed');
        case 'verify':
            return i18n.t('settings.backup.notifications.verifyFailed');
        case 'delete':
            return i18n.t('settings.backup.notifications.deleteFailed');
        default: {
            const exhaustive: never = taskType;
            throw new Error(`Unhandled backup task type: ${exhaustive}`);
        }
    }
};

export { resolveBackupFailureNotification, resolveBackupProgressLabel, resolveBackupSuccessNotification };
