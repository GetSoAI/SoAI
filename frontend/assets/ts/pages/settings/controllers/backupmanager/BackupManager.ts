/* SoAI - Settings backup manager ownership [frontend/assets/ts/pages/settings/controllers/backupmanager/BackupManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { requireTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { SettingsSectionLifecycle, transformBackupEntry, UI_IDS } from '@features/settings/public.ts';
import { BACKUP_ACTION_CREATE, BACKUP_ACTION_DELETE, BACKUP_ACTION_EXPORT, BACKUP_ACTION_RESTORE, BACKUP_ACTION_VERIFY } from '@pages/settings/controllers/backupmanager/constants.ts';
import { bindBackupActionClickDispatcher, type BackupActionHandlers } from '@pages/settings/controllers/backupmanager/backupActionClickDispatcherController.ts';
import type { BackupManagerDependencies, BackupManagerHost } from '@pages/settings/controllers/backupmanager/contracts.ts';
import { BackupActionDisabledStateSync } from '@pages/settings/controllers/backupmanager/backupActionDisabledStateSyncController.ts';
import { BackupActionController } from '@pages/settings/controllers/backupmanager/BackupActionController.ts';
import { optionalHTMLElement, requireButton, requireHTMLElement } from '@pages/settings/controllers/backupmanager/dom.ts';
import { BackupProgressWidget } from '@pages/settings/controllers/backupmanager/backupProgressWidget.ts';
import { BackupProgressController } from '@pages/settings/controllers/backupmanager/BackupProgressController.ts';
import { renderBackupListContent, renderBackupSection } from '@pages/settings/controllers/backupmanager/view.ts';

class BackupManager {
    readonly #host: BackupManagerHost;
    readonly #actionController: BackupActionController;
    readonly #progressController: BackupProgressController;
    readonly #actionDisabledStateSync: BackupActionDisabledStateSync;
    readonly #progressWidget: BackupProgressWidget;
    readonly #lifecycle: SettingsSectionLifecycle = new SettingsSectionLifecycle();

    constructor({ host }: BackupManagerDependencies) {
        if (!host) {
            throw new Error('BackupManager requires a host');
        }
        this.#host = host;
        this.#actionDisabledStateSync = new BackupActionDisabledStateSync({
            host: {
                pageDom: host.dom.pageDom,
                getBackupOperation: () => host.state.getBackupOperation()
            }
        });
        this.#progressWidget = new BackupProgressWidget({
            host: {
                pageDom: host.dom.pageDom
            },
            isMounted: () => this.#lifecycle.isMounted
        });
        this.#progressController = new BackupProgressController({
            host: {
                getBackupOperation: () => host.state.getBackupOperation(),
                setBackupOperation: (operation) => host.state.setBackupOperation(operation),
                trackAcceptedTask: (taskId, options) => host.tasks.trackAcceptedTask(taskId, options),
                feedback: host.notifications.feedback,
                restartApplication: () => host.api.restartApplication(),
                showRestartOverlay: (value) => host.api.showRestartOverlay(value)
            },
            renderProgress: () => this.#renderProgress(),
            requestReload: this.reload
        });
        this.#actionController = new BackupActionController({
            host: {
                createBackup: () => host.api.createBackup(),
                restoreBackup: (backupId) => host.api.restoreBackup(backupId),
                verifyBackup: (backupId) => host.api.verifyBackup(backupId),
                deleteBackup: (backupId) => host.api.deleteBackup(backupId),
                exportBackup: (backupId) => host.api.exportBackup(backupId),
                runWithBoundary: (name, task) => host.execution.runWithBoundary(name, task),
                confirmAndExecute: host.execution.confirmAndExecute,
                feedback: host.notifications.feedback
            },
            disableBackupActions: () => this.#actionDisabledStateSync.disableAllActions(),
            syncBackupActions: () => this.#actionDisabledStateSync.syncActionDisabledStates(),
            trackOperation: (operation) => this.#progressController.track(operation),
            clearOperation: () => this.#progressController.clear(),
            requestReload: this.reload
        });
    }

    render(): TrustedHtml {
        return toTrustedUiHtml(
            renderBackupSection({
                isAdmin: this.#host.api.isAdmin(),
                backups: this.#host.state.getBackups(),
                listLoadStatus: this.#host.state.getBackupListLoadStatus(),
                isOperating: this.#host.state.getBackupOperation() !== null,
                sanitizeHtml: this.#host.api.sanitizeHtml,
                sanitizeAttribute: this.#host.api.sanitizeAttribute
            })
        );
    }

    setupEventListeners(): void {
        this.dispose();
        if (!this.#host.api.isAdmin()) {
            return;
        }
        this.#lifecycle.mount();

        const root = requireHTMLElement(this.#host.dom, 'backup-content');
        const createButton = requireButton(this.#host.dom, UI_IDS.BACKUP_CREATE, root);
        if (requireTrimmedDataAttribute(createButton, 'action', 'Backup create button') !== BACKUP_ACTION_CREATE) {
            throw new Error('Backup create button is missing required data-action');
        }
        requireHTMLElement(this.#host.dom, UI_IDS.BACKUP_LIST, root);
        requireHTMLElement(this.#host.dom, UI_IDS.BACKUP_PROGRESS, root);

        const handlers: BackupActionHandlers = {
            [BACKUP_ACTION_CREATE]: async () => {
                await this.#actionController.createBackup();
            },
            [BACKUP_ACTION_RESTORE]: async (backupId: string | null, actionElement: HTMLElement) => {
                await this.#actionController.restoreBackup(this.#requireBackupId(backupId), actionElement);
            },
            [BACKUP_ACTION_VERIFY]: async (backupId: string | null, actionElement: HTMLElement) => {
                await this.#actionController.verifyBackup(this.#requireBackupId(backupId), actionElement);
            },
            [BACKUP_ACTION_DELETE]: async (backupId: string | null, actionElement: HTMLElement) => {
                await this.#actionController.deleteBackup(this.#requireBackupId(backupId), actionElement);
            },
            [BACKUP_ACTION_EXPORT]: async (backupId: string | null, actionElement: HTMLElement) => {
                await this.#actionController.exportBackup(this.#requireBackupId(backupId), actionElement);
            }
        };

        this.#lifecycle.addCleanup(
            bindBackupActionClickDispatcher({
                root,
                handlers,
                onDispatchError: (error: Error) => {
                    this.#host.notifications.feedback.handle(error, 'Backup action');
                }
            })
        );

        this.#actionDisabledStateSync.syncActionDisabledStates();
        const activeOperation = this.#host.state.getBackupOperation();
        if (activeOperation) {
            this.#progressController.track(activeOperation);
        } else {
            this.#renderProgress();
        }
    }

    readonly reload = async (): Promise<void> => {
        const reloadRun = this.#lifecycle.beginReload('backup-reload');
        if (reloadRun === null) {
            return;
        }

        try {
            this.#host.state.setBackupListLoadStatus('loading');
            this.#updateBackupList();
            const response = await this.#host.execution.runWithBoundary('settings:loadBackups', async () => this.#host.api.listBackups());
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }

            this.#host.state.setBackups(response.backups.map(transformBackupEntry));
            this.#host.state.setBackupListLoadStatus('loaded');
            this.#updateBackupList();
        } catch (error) {
            if (!this.#lifecycle.isReloadCurrent(reloadRun)) {
                return;
            }
            this.#host.state.setBackupListLoadStatus('failed');
            this.#updateBackupList();
            this.#host.notifications.feedback.handle(ensureError(error), 'Backup reload');
            this.#host.notifications.feedback.show(i18n.t('settings.backup.errors.reloadFailed'), 'error');
        } finally {
            if (this.#lifecycle.isReloadCurrent(reloadRun)) {
                this.#actionDisabledStateSync.syncActionDisabledStates();
                if (this.#host.search.hasSearchQuery()) {
                    this.#host.search.filterSettings();
                }
            }
        }
    };

    dispose(): void {
        try {
            this.#lifecycle.dispose('backup-dispose');
        } finally {
            this.#progressWidget.reset();
        }
    }

    #renderProgress(): void {
        this.#progressWidget.scheduleRender(this.#host.state.getBackupOperation());
    }

    #updateBackupList(): void {
        const root = optionalHTMLElement(this.#host.dom, 'backup-content');
        if (!root) {
            return;
        }
        const list = optionalHTMLElement(this.#host.dom, UI_IDS.BACKUP_LIST, root);
        if (!list) {
            return;
        }
        const isOperating = this.#host.state.getBackupOperation() !== null;
        const markup = renderBackupListContent(this.#host.state.getBackups(), this.#host.api.sanitizeHtml, this.#host.api.sanitizeAttribute, isOperating, this.#host.state.getBackupListLoadStatus());
        const trustedMarkup = toTrustedUiHtml(markup);
        this.#host.dom.pageDom.updateHtml(list, trustedMarkup, { escape: false });
    }

    #requireBackupId(backupId: string | null): string {
        const normalizedBackupId = toTrimmedStringOrNull(backupId);
        if (!normalizedBackupId) {
            throw new Error('Backup action is missing data-backup-id');
        }
        return normalizedBackupId;
    }
}

export { BackupManager };
