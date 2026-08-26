/* SoAI - Settings page initial section reload orchestration [frontend/assets/ts/pages/settings/controllers/page/reload/InitialReloadsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isSettingsNormalTabVisibleById } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

const createInitialManagerReloads = (page: SettingsRuntimeContext, state: SettingsPageState): Promise<boolean | void>[] => {
    const themeManager = state.themeManager;
    const externalAccountsManager = state.externalAccountsManager;
    if (!themeManager) {
        throw new Error('ThemeManager not initialized');
    }
    if (!externalAccountsManager) {
        throw new Error('ExternalAccountsManager not initialized');
    }
    const initialReloads: Promise<boolean | void>[] = [themeManager.reload(), externalAccountsManager.reload()];
    if (isSettingsNormalTabVisibleById(page, state, 'messaging')) {
        if (!state.messagingManager) throw new Error('MessagingManager not initialized');
        initialReloads.push(state.messagingManager.reload());
    }

    if (page.owners.auth.isAdmin()) {
        const usersManager = state.usersManager;
        if (isSettingsNormalTabVisibleById(page, state, 'users')) {
            if (!usersManager) {
                throw new Error('UsersManager not initialized');
            }
            initialReloads.push(usersManager.refreshProductUsers());
        }
        if (isSettingsNormalTabVisibleById(page, state, 'mcp')) {
            if (!state.mcpManager) {
                throw new Error('McpManager not initialized');
            }
            initialReloads.push(state.mcpManager.reload());
        }
        if (isSettingsNormalTabVisibleById(page, state, 'api-keys')) {
            if (!state.apiKeysManager) {
                throw new Error('ApiKeysManager not initialized');
            }
            initialReloads.push(state.apiKeysManager.reload());
        }
        if (isSettingsNormalTabVisibleById(page, state, 'backup')) {
            if (!state.backupManager) {
                throw new Error('BackupManager not initialized');
            }
            initialReloads.push(state.backupManager.reload());
        }
        if (isSettingsNormalTabVisibleById(page, state, 'licensing')) {
            if (!state.licensingManager) throw new Error('LicensingManager not initialized');
            initialReloads.push(state.licensingManager.reload());
        }
        if (state.productSettingsEnabled) {
            for (const [tabId, manager] of state.productManagers) {
                if (isSettingsNormalTabVisibleById(page, state, tabId)) {
                    initialReloads.push(manager.reload());
                }
            }
        }
    }
    return initialReloads;
};

const InitialReloadsController = (page: SettingsRuntimeContext, state: SettingsPageState, signal: AbortSignal | null): void => {
    throwIfAborted(signal);
    const reloads = createInitialManagerReloads(page, state);
    void (signal ? raceWithAbortSignal(Promise.all(reloads), signal) : Promise.all(reloads))
        .then((): void => undefined)
        .catch((error): void => {
            if (signal?.aborted) {
                return;
            }
            page.owners.feedback.handle(ensureError(error), 'Settings initial section reload');
        });
};

export { InitialReloadsController };
