/* SoAI - Settings backup action execution [frontend/assets/ts/pages/settings/controllers/backupmanager/BackupActionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { downloadAuthenticatedResponse } from '@core/api/authenticatedDownload.ts';
import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ExecutionHost } from '@core/ui/controllerHosts.ts';
import { DeferredButtonLoading } from '@core/ui/loadingbuttons/deferredLoadingButton.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import type { BackupOperationState } from '@core/settings/contracts.ts';
import { resolveBackupFailureNotification, resolveBackupProgressLabel } from '@pages/settings/controllers/backupmanager/backupOperationMessagesController.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { BackupTaskAcceptedResponse } from '@core/api/contracts/adminContracts.ts';

interface BackupActionExecutor extends PageFeedbackOwnerHost {
    createBackup: () => Promise<BackupTaskAcceptedResponse>;
    restoreBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    verifyBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    deleteBackup: (backupId: string) => Promise<BackupTaskAcceptedResponse>;
    exportBackup: (backupId: string) => Promise<Response>;
    runWithBoundary: <T>(name: string, task: () => Promise<T> | T) => Promise<T>;
    confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
}

interface BackupActionDependencies {
    host: BackupActionExecutor;
    disableBackupActions: () => void;
    syncBackupActions: () => void;
    trackOperation: (operation: BackupOperationState) => void;
    clearOperation: () => void;
    requestReload: () => Promise<void>;
}

const isBackupOperationConflict = (error: Error): boolean => error instanceof APIError && error.status === 409;

class BackupActionController {
    readonly #host: BackupActionExecutor;
    readonly #disableBackupActions: () => void;
    readonly #syncBackupActions: () => void;
    readonly #trackOperation: (operation: BackupOperationState) => void;
    readonly #clearOperation: () => void;
    readonly #requestReload: () => Promise<void>;
    readonly #buttonLoading: DeferredButtonLoading = new DeferredButtonLoading();
    #isExecuting = false;

    constructor({ host, disableBackupActions, syncBackupActions, trackOperation, clearOperation, requestReload }: BackupActionDependencies) {
        this.#host = host;
        this.#disableBackupActions = disableBackupActions;
        this.#syncBackupActions = syncBackupActions;
        this.#trackOperation = trackOperation;
        this.#clearOperation = clearOperation;
        this.#requestReload = requestReload;
    }

    createBackup(): Promise<void> {
        return this.#executeBackupTask('create', () => this.#host.createBackup(), undefined, null, {
            title: i18n.t('settings.backup.confirmCreate.title'),
            message: i18n.t('settings.backup.confirmCreate.message'),
            confirmText: i18n.t('settings.backup.actions.create'),
            cancelText: i18n.t('common.cancel'),
            variant: 'accent'
        });
    }

    restoreBackup(backupId: string, actionElement: HTMLElement): Promise<void> {
        return this.#executeBackupTask('restore', () => this.#host.restoreBackup(backupId), backupId, actionElement, {
            title: i18n.t('settings.backup.confirmRestore.title'),
            message: i18n.t('settings.backup.confirmRestore.message'),
            confirmText: i18n.t('settings.backup.actions.restore'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        });
    }

    verifyBackup(backupId: string, actionElement: HTMLElement): Promise<void> {
        return this.#executeBackupTask('verify', () => this.#host.verifyBackup(backupId), backupId, actionElement);
    }

    deleteBackup(backupId: string, actionElement: HTMLElement): Promise<void> {
        return this.#executeBackupTask('delete', () => this.#host.deleteBackup(backupId), backupId, actionElement, {
            title: i18n.t('settings.backup.confirmDelete.title'),
            message: i18n.t('settings.backup.confirmDelete.message'),
            confirmText: i18n.t('settings.backup.actions.delete'),
            cancelText: i18n.t('common.cancel'),
            variant: 'danger'
        });
    }

    async exportBackup(backupId: string, actionElement: HTMLElement): Promise<void> {
        if (this.#isExecuting) {
            return;
        }
        this.#isExecuting = true;
        this.#disableBackupActions();
        this.#buttonLoading.begin(actionElement);
        this.#host.feedback.show(i18n.t('common.notifications.downloadStarted'), 'download');
        try {
            await this.#host.runWithBoundary('settings:exportBackup', async () => {
                const response = await this.#host.exportBackup(backupId);
                await downloadAuthenticatedResponse(response, { filename: `${backupId}.tar.gz` });
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                operation: i18n.t('common.download'),
                ...(isBackupOperationConflict(runtimeError) ? { notificationMessage: i18n.t('settings.backup.errors.downloadConflict') } : {}),
                showNotification: (message): void => this.#host.feedback.show(message, 'error')
            });
            errorHandler.handleError(runtimeError, { context: 'settings:exportBackup' });
        } finally {
            this.#isExecuting = false;
            this.#buttonLoading.settle();
            this.#syncBackupActions();
        }
    }

    async #executeBackupTask(
        taskType: BackupOperationState['type'],
        apiCall: () => Promise<BackupTaskAcceptedResponse>,
        backupId: string | undefined,
        actionElement: HTMLElement | null,
        confirmOptions?: {
            title: string;
            message: string;
            confirmText?: string;
            cancelText?: string;
            variant?: string;
        } | null
    ): Promise<void> {
        if (this.#isExecuting) {
            return;
        }
        this.#isExecuting = true;
        this.#disableBackupActions();
        try {
            await this.#host.confirmAndExecute(
                `settings:${taskType}Backup`,
                confirmOptions ?? null,
                async () => {
                    this.#buttonLoading.begin(actionElement);
                    const response = await apiCall();

                    const taskId = response.taskId;

                    const operation: BackupOperationState = {
                        taskId,
                        type: taskType,
                        progress: 0,
                        message: resolveBackupProgressLabel(taskType),
                        ...(backupId ? { backupId } : {})
                    };
                    this.#trackOperation(operation);
                    return null;
                },
                null,
                null,
                null
            );
        } catch (error) {
            this.#clearOperation();
            const runtimeError = ensureError(error);
            showOperationFailureNotification({
                error: runtimeError,
                notificationMessage: resolveBackupFailureNotification(taskType),
                showNotification: (message): void => this.#host.feedback.show(message, 'error')
            });
            this.#requestReloadSafely();
            errorHandler.handleError(runtimeError, { context: `settings:${taskType}Backup` });
        } finally {
            this.#isExecuting = false;
            this.#buttonLoading.settle();
            this.#syncBackupActions();
        }
    }

    #requestReloadSafely(): void {
        void this.#requestReload().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('Settings', 'Backup manager reload failed', runtimeError);
        });
    }
}

export { BackupActionController };
