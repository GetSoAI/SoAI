/* SoAI - Settings page backup action click dispatcher controller [frontend/assets/ts/pages/settings/controllers/backupmanager/backupActionClickDispatcherController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { optionalTrimmedDataAttribute } from '@core/dom/attributes.ts';
import { bindDataActionListener } from '@core/dom/dataActionBinding.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { BackupActionId } from '@pages/settings/controllers/backupmanager/constants.ts';
import { isBackupActionId } from '@pages/settings/controllers/backupmanager/guards.ts';

type BackupActionHandlers = Record<BackupActionId, (backupId: string | null, actionElement: HTMLElement) => Promise<void>>;

interface BackupActionClickDispatcherDependencies {
    root: HTMLElement;
    handlers: BackupActionHandlers;
    onDispatchError: (error: Error) => void;
}

const bindBackupActionClickDispatcher = ({ root, handlers, onDispatchError }: BackupActionClickDispatcherDependencies): (() => void) => {
    const controller = new AbortController();
    bindDataActionListener({
        root,
        eventType: 'click',
        signal: controller.signal,
        isAction: isBackupActionId,
        preventDefault: 'always',
        mouseButton: 'primary',
        ignoreDisabled: true,
        onAction: async ({ action, actionElement }): Promise<void> => {
            const backupId = optionalTrimmedDataAttribute(actionElement, 'backup-id');
            const handler = handlers[action];
            try {
                await handler(backupId, actionElement);
            } catch (error) {
                const runtimeError = ensureError(error);
                onDispatchError(runtimeError);
                throw runtimeError;
            }
        }
    });
    return () => controller.abort();
};

export { bindBackupActionClickDispatcher, type BackupActionHandlers };
