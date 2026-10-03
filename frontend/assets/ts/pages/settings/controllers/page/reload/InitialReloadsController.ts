/* SoAI - Settings page initial section reload orchestration [frontend/assets/ts/pages/settings/controllers/page/reload/InitialReloadsController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAbortError, raceWithAbortSignal, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isSettingsNormalTabVisibleById } from '@pages/settings/controllers/page/settingsAccessController.ts';
import type { SettingsRuntimeContext } from '@pages/settings/controllers/page/contracts.ts';
import { updateSecurityTabNotifyBadge } from '@pages/settings/controllers/page/securityTabBadgeController.ts';
import type { SettingsPageState } from '@pages/settings/controllers/page/state.ts';

interface InitialSettingsReload {
    label: string;
    task: Promise<boolean | void>;
}

const createInitialManagerReloads = (page: SettingsRuntimeContext, state: SettingsPageState, signal: AbortSignal): InitialSettingsReload[] => {
    const themeManager = state.themeManager;
    const externalAccountsManager = state.externalAccountsManager;
    const preferencesManager = state.preferencesManager;
    if (!themeManager) {
        throw new Error('ThemeManager not initialized');
    }
    if (!externalAccountsManager) {
        throw new Error('ExternalAccountsManager not initialized');
    }
    if (!preferencesManager) {
        throw new Error('PreferencesManager not initialized');
    }
    const initialReloads: InitialSettingsReload[] = [
        { label: 'Settings theme reload', task: themeManager.reload() },
        { label: 'Settings external accounts reload', task: externalAccountsManager.reload() },
        { label: 'Settings OCR preference reload', task: preferencesManager.refreshOcrPreference() }
    ];
    if (isSettingsNormalTabVisibleById(page, state, 'messaging')) {
        if (!state.messagingManager) throw new Error('MessagingManager not initialized');
        initialReloads.push({ label: 'Settings messaging reload', task: state.messagingManager.reload() });
    }
    if (isSettingsNormalTabVisibleById(page, state, 'connect')) {
        if (!state.connectManager) throw new Error('ConnectManager not initialized');
        initialReloads.push({ label: 'Settings connect reload', task: state.connectManager.reload() });
    }

    if (page.owners.auth.isAdmin()) {
        const usersManager = state.usersManager;
        if (isSettingsNormalTabVisibleById(page, state, 'users')) {
            if (!usersManager) {
                throw new Error('UsersManager not initialized');
            }
            initialReloads.push({ label: 'Settings product users reload', task: usersManager.refreshProductUsers() });
        }
        if (isSettingsNormalTabVisibleById(page, state, 'security')) {
            const securityManager = state.securityManager;
            if (!securityManager) {
                throw new Error('SecurityManager not initialized');
            }
            initialReloads.push({
                label: 'Settings security audit reload',
                task: securityManager.reload({ showFailureNotification: false }).then((succeeded) => {
                    if (signal.aborted || state.securityManager !== securityManager) {
                        return false;
                    }
                    updateSecurityTabNotifyBadge(page, state);
                    return succeeded;
                })
            });
        }
        if (isSettingsNormalTabVisibleById(page, state, 'mcp')) {
            if (!state.mcpManager) {
                throw new Error('McpManager not initialized');
            }
            initialReloads.push({ label: 'Settings MCP reload', task: state.mcpManager.startActivityRefreshes() });
        }
        if (isSettingsNormalTabVisibleById(page, state, 'api-keys')) {
            if (!state.apiKeysManager) {
                throw new Error('ApiKeysManager not initialized');
            }
            initialReloads.push({ label: 'Settings API keys reload', task: state.apiKeysManager.startActivityRefreshes() });
        }
        if (isSettingsNormalTabVisibleById(page, state, 'backup')) {
            if (!state.backupManager) {
                throw new Error('BackupManager not initialized');
            }
            initialReloads.push({ label: 'Settings backup reload', task: state.backupManager.reload() });
        }
        if (isSettingsNormalTabVisibleById(page, state, 'licensing')) {
            if (!state.licensingManager) throw new Error('LicensingManager not initialized');
            initialReloads.push({ label: 'Settings licensing reload', task: state.licensingManager.reload() });
        }
        if (state.productSettingsEnabled) {
            for (const [tabId, manager] of state.productManagers) {
                if (isSettingsNormalTabVisibleById(page, state, tabId)) {
                    initialReloads.push({ label: `Settings ${tabId} reload`, task: manager.reload() });
                }
            }
        }
    }
    return initialReloads;
};

const InitialReloadsController = async (page: SettingsRuntimeContext, state: SettingsPageState, signal: AbortSignal): Promise<void> => {
    throwIfAborted(signal);
    const reloads = createInitialManagerReloads(page, state, signal);
    const outcomes = await raceWithAbortSignal(Promise.allSettled(reloads.map((reload) => reload.task)), signal);
    throwIfAborted(signal);
    outcomes.forEach((outcome, index) => {
        if (outcome.status === 'fulfilled' || isAbortError(outcome.reason)) {
            return;
        }
        const reload = reloads[index];
        page.owners.feedback.handle(ensureError(outcome.reason), reload?.label ?? 'Settings initial section reload');
    });
};

export { InitialReloadsController };
