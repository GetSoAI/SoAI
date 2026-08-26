/* SoAI - Settings page backup action disabled state sync controller [frontend/assets/ts/pages/settings/controllers/backupmanager/backupActionDisabledStateSyncController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BackupOperationState } from '@core/settings/contracts.ts';
import { setControlDisabledState } from '@core/ui/controls/disabledState.ts';
import { UI_IDS } from '@features/settings/public.ts';
import { optionalBackupButton, optionalHTMLElement, requireBackupItemFromActionButton, requireBackupValidFlag, resolveButtons } from '@pages/settings/controllers/backupmanager/dom.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface BackupActionDisabledStateHost extends PageDomOwnerHost {
    getBackupOperation: () => BackupOperationState | null;
}

class BackupActionDisabledStateSync {
    readonly #host: BackupActionDisabledStateHost;

    constructor({ host }: { host: BackupActionDisabledStateHost }) {
        this.#host = host;
    }

    disableAllActions(): void {
        const root = optionalHTMLElement(this.#host, 'backup-content');
        if (!root) {
            return;
        }
        const createButton = optionalBackupButton(this.#host, UI_IDS.BACKUP_CREATE, root);
        if (createButton) {
            setControlDisabledState(createButton, true);
        }
        for (const button of resolveButtons('.backup-restore-btn, .backup-verify-btn, .backup-delete-btn, .backup-export-btn', root)) {
            setControlDisabledState(button, true);
        }
    }

    syncActionDisabledStates(): void {
        const root = optionalHTMLElement(this.#host, 'backup-content');
        if (!root) {
            return;
        }
        const operation = this.#host.getBackupOperation();
        const isOperating = operation !== null;

        const createButton = optionalBackupButton(this.#host, UI_IDS.BACKUP_CREATE, root);
        if (createButton) {
            setControlDisabledState(createButton, isOperating);
        }

        for (const button of resolveButtons('.backup-restore-btn, .backup-verify-btn', root)) {
            const item = requireBackupItemFromActionButton(button);
            const isValid = requireBackupValidFlag(item);
            setControlDisabledState(button, isOperating || !isValid);
        }

        for (const button of resolveButtons('.backup-delete-btn', root)) {
            setControlDisabledState(button, isOperating);
        }

        for (const button of resolveButtons('.backup-export-btn', root)) {
            setControlDisabledState(button, isOperating);
        }
    }
}

export { BackupActionDisabledStateSync };
