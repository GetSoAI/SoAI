/* SoAI - Settings page control layer manager hosts adapters [frontend/assets/ts/pages/settings/controllers/page/managerhosts/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dispatchCustomEvent } from '@core/environment/public.ts';
import { decodeWallpaperInfoResponse } from '@core/api/contracts/wallpaperContracts.ts';
import type { WallpaperMetadata } from '@core/settings/contracts.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { runIdentityMutationWithStatusRecovery } from '@core/mutations/identityMutationPolling.ts';
import { createStorageDefaults } from '@core/storage/defaults.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import type { SettingsManagerCallbacks, SettingsRuntimeContext, SettingsPageState } from '@pages/settings/controllers/page/contracts.ts';
import { buildBaseHostBindings } from '@pages/settings/controllers/page/hostBindings.ts';
import { hasSettingsAction } from '@pages/settings/controllers/page/settingsAccessController.ts';
import { SETTINGS_SYSTEM_FACTORY_RESET_ACTION, SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION, SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION, SETTINGS_SYSTEM_RESET_METRICS_ACTION } from '@pages/settings/controllers/systemmanager/constants.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import type { SystemManagerActionId, SystemManagerHost } from '@pages/settings/controllers/systemmanager/contracts.ts';
import type { ThemeManagerHost } from '@pages/settings/controllers/thememanager/contracts.ts';
import type { PreferencesManagerHost } from '@pages/settings/controllers/preferences/types.ts';
import type { UsersManagerHost } from '@pages/settings/controllers/usersmanager/types.ts';

const createUiPreferenceBindings = (
    state: SettingsPageState
): {
    getUiPrefValue: (key: UiPreferenceKey) => JsonValue | null | undefined;
    setUiPrefValue: (key: UiPreferenceKey, value: JsonValue | null | undefined) => void;
} => {
    return {
        getUiPrefValue: (key: UiPreferenceKey): JsonValue | null | undefined => {
            if (!state.uiPrefsManager) {
                throw new Error('uiPrefsManager not initialized');
            }
            return state.uiPrefsManager.getValue(key);
        },
        setUiPrefValue: (key: UiPreferenceKey, value: JsonValue | null | undefined): void => {
            if (!state.uiPrefsManager) {
                throw new Error('uiPrefsManager not initialized');
            }
            if (!isJsonValue(value)) {
                throw new Error('UI preference value must be JSON-compatible');
            }
            state.uiPrefsManager.updateValue(key, value);
            state.dirtyStateManager?.syncUiPreferenceField(key);
        }
    };
};

const createPreferencesManagerHost = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): PreferencesManagerHost => ({
    ...buildBaseHostBindings(page, callbacks),
    languageService: page.owners.languageService,
    storage: page.owners.storage,
    ...createUiPreferenceBindings(state),
    filterSettings: callbacks.filterSettings
});

const createThemeManagerHost = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): ThemeManagerHost => ({
    ...buildBaseHostBindings(page, callbacks),
    canManageWallpaper: (): boolean => page.owners.auth.isAdmin() && hasSettingsAction(state, 'WEBUI_APPEARANCE_ADMIN'),
    uploadWallpaper: (file: File) => page.owners.api.webui.wallpaper.upload(file),
    downloadWallpaper: (url: string) => page.owners.api.webui.wallpaper.download(url),
    deleteWallpaper: () => page.owners.api.webui.wallpaper.delete(),
    getWallpaperStatus: async () => decodeWallpaperInfoResponse(await requestWebSocketSnapshotRecord('webui.wallpaper.status')),
    storage: page.owners.storage,
    ...createUiPreferenceBindings(state),
    getCurrentWallpaperUrl: (): string | null => state.currentWallpaperUrl,
    setCurrentWallpaperUrl: (url: string | null): void => {
        state.currentWallpaperUrl = url;
    },
    getCurrentWallpaperMetadata: (): WallpaperMetadata | null => state.currentWallpaperMetadata,
    setCurrentWallpaperMetadata: (metadata: WallpaperMetadata | null): void => {
        state.currentWallpaperMetadata = metadata;
    },
    getCurrentSolidBackground: (): string | null => state.currentSolidBackground,
    setCurrentSolidBackground: (value: string | null): void => {
        state.currentSolidBackground = value;
    },
    applyWallpaperOverlay: callbacks.applyWallpaperOverlay,
    scheduleWallpaperRefresh: callbacks.scheduleWallpaperRefresh
});

const createUsersManagerHost = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): UsersManagerHost => ({
    api: {
        listUsers: async (): Promise<WebuiUser[]> => (page.owners.auth.isAdmin() && hasSettingsAction(state, 'USER_ADMIN') ? await page.owners.api.webui.users.list() : [await page.owners.api.webui.users.current()]),
        createUser: (username: string, password: string, isAdmin: boolean) => page.owners.api.webui.users.create(username, password, isAdmin),
        updateUser: (userId: number, isAdmin: boolean) => page.owners.api.webui.users.update(userId, isAdmin),
        changeOwnPassword: async (operationId: string, current: string, newPassword: string) => {
            const actor = page.owners.auth.getCurrentUser();
            if (actor === null) throw new Error('Authenticated user is required for password change.');
            return await page.owners.auth.runOwnIdentityMutation({
                operationId,
                operationType: 'password_change',
                targetUserId: actor.id,
                requestedUsername: null,
                execute: (signal) => page.owners.api.webui.auth.changePassword(operationId, current, newPassword, { signal, authTransitionOwned: true }),
                recover: (signal) => page.owners.api.webui.auth.recoverSessionRotation(operationId, { signal, authTransitionOwned: true }),
                status: (finalizeAbsence, signal) => page.owners.api.webui.users.mutationStatus(operationId, finalizeAbsence ? { operationType: 'password_change', targetUserId: actor.id } : undefined, { signal, authTransitionOwned: true }),
                currentUser: (signal) => page.owners.api.webui.users.current({ signal, authTransitionOwned: true })
            });
        },
        changeUserPassword: async (userId: number, operationId: string, current: string, newPassword: string, signal: AbortSignal) => {
            return await runIdentityMutationWithStatusRecovery({
                operationId,
                signal,
                execute: (signal) => page.owners.api.webui.users.changePassword(userId, operationId, current, newPassword, { signal }),
                status: (finalizeAbsence, signal) => page.owners.api.webui.users.mutationStatus(operationId, finalizeAbsence ? { operationType: 'password_change', targetUserId: userId } : undefined, { signal }),
                resolveCommittedUser: async (signal) => {
                    const user = (await page.owners.api.webui.users.list({ signal })).find((entry) => entry.id === userId);
                    if (!user) throw new Error('Committed password target is unavailable.');
                    return user;
                }
            });
        },
        renameOwnUsername: async (operationId: string, newUsername: string, currentPassword: string) => {
            const actor = page.owners.auth.getCurrentUser();
            if (actor === null) throw new Error('Authenticated user is required for self rename.');
            return await page.owners.auth.runOwnIdentityMutation({
                operationId,
                operationType: 'username_rename',
                targetUserId: actor.id,
                requestedUsername: newUsername,
                execute: (signal) => page.owners.api.webui.users.renameCurrent(operationId, newUsername, currentPassword, { signal, authTransitionOwned: true }),
                recover: (signal) => page.owners.api.webui.auth.recoverSessionRotation(operationId, { signal, authTransitionOwned: true }),
                status: (finalizeAbsence, signal) => page.owners.api.webui.users.mutationStatus(operationId, finalizeAbsence ? { operationType: 'username_rename', targetUserId: actor.id, requestedUsername: newUsername } : undefined, { signal, authTransitionOwned: true }),
                currentUser: (signal) => page.owners.api.webui.users.current({ signal, authTransitionOwned: true })
            });
        },
        renameUser: async (userId: number, operationId: string, newUsername: string, currentPassword: string, signal: AbortSignal) => {
            return await runIdentityMutationWithStatusRecovery({
                operationId,
                signal,
                execute: (signal) => page.owners.api.webui.users.rename(userId, operationId, newUsername, currentPassword, { signal }),
                status: (finalizeAbsence, signal) => page.owners.api.webui.users.mutationStatus(operationId, finalizeAbsence ? { operationType: 'username_rename', targetUserId: userId, requestedUsername: newUsername } : undefined, { signal }),
                resolveCommittedUser: async (signal) => {
                    const user = (await page.owners.api.webui.users.list({ signal })).find((entry) => entry.id === userId);
                    if (!user) throw new Error('Committed rename target is unavailable.');
                    return user;
                }
            });
        },
        listWorkspaceBrowserRoots: (options) => page.owners.api.webui.users.workspaceBrowser.roots(options),
        locateWorkspaceBrowserPath: (path, options) => page.owners.api.webui.users.workspaceBrowser.locate(path, options),
        listWorkspaceBrowser: (options) => page.owners.api.webui.users.workspaceBrowser.list(options),
        searchWorkspaceBrowser: (options) => page.owners.api.webui.users.workspaceBrowser.search(options),
        updateUserWorkspacePath: (userId: number, workspacePath: string | null) => page.owners.api.webui.users.updateWorkspacePath(userId, workspacePath),
        deleteUser: (userId: number) => page.owners.api.webui.users.delete(userId),
        logout: async (): Promise<void> => {
            await page.owners.auth.logout();
        },
        invalidateSession: async (): Promise<void> => {
            await page.owners.auth.invalidateSession();
        },
        listSessions: (options) => page.owners.api.webui.sessions.list(options),
        revokeSession: (jti: string) => page.owners.api.webui.sessions.revoke(jti),
        revokeAllSessions: () => page.owners.api.webui.sessions.revokeAll()
    },
    view: {
        pageDom: page.owners.pageDom,
        pageResources: page.owners.pageResources,
        sanitizeHtml: (value: JsonValue | null | undefined): string => page.owners.pageContext.sanitizer.html(value)
    },
    execution: {
        feedback: page.owners.feedback,
        runWithBoundary: <T>(name: string, task: () => Promise<T> | T): Promise<T> => page.owners.pageLifecycle.run(name, task),
        runPageTask: <T>(name: string, task: () => Promise<T>, options?: Record<string, JsonValue | null | undefined>): Promise<T | null> => page.owners.streaming.runTask(name, task, options),
        withButtonDisabled: callbacks.withButtonDisabled,
        confirmAndExecute: callbacks.confirmAndExecute
    },
    notifications: { feedback: page.owners.feedback },
    state: {
        getUsers: (): WebuiUser[] => state.users,
        setUsers: (users: WebuiUser[]): void => {
            state.users = users;
        },
        getUsersAvailability: () => state.usersAvailability,
        setUsersAvailability: (availability): void => {
            state.usersAvailability = availability;
        },
        getCurrentUserId: (): string | null => state.currentUserId,
        canAdministerUsers: (): boolean => page.owners.auth.isAdmin() && hasSettingsAction(state, 'USER_ADMIN')
    },
    filterSettings: callbacks.filterSettings
});

const createSystemManagerHost = (page: SettingsRuntimeContext, state: SettingsPageState, callbacks: SettingsManagerCallbacks): SystemManagerHost => ({
    api: {
        resetUiPreferencesRemote: () => page.owners.api.webui.preferences.resetUiPreferences(),
        resetUiPreferencesLocal: (options: { preserveWizardState: boolean }): void => {
            page.owners.storage.resetUiPreferences(options);
        },
        resetAppearancePreferences: async (): Promise<void> => {
            const defaults = createStorageDefaults().ui;
            await page.owners.api.webui.wallpaper.delete();
            page.owners.storage.setAccentColor(defaults.accentColor);
            page.owners.storage.setSurfaceColor(defaults.surfaceColor);
            page.owners.storage.setReduceMotions(defaults.reduceMotions);
            page.owners.storage.setGlassEnabled(defaults.glassEnabled);
            page.owners.storage.setPageAnimation(defaults.pageAnimation);
            page.owners.storage.setModalAnimation(defaults.modalAnimation);
            page.owners.storage.setNotificationAnimation(defaults.notificationAnimation);
            page.owners.storage.setAnimationSpeed(defaults.animationSpeed);
            page.owners.storage.setWallpaperOverlay(defaults.wallpaperOverlay);
            page.owners.storage.setSolidBackground(defaults.solidBackground);
            state.currentWallpaperUrl = null;
            state.currentWallpaperMetadata = null;
            state.currentSolidBackground = defaults.solidBackground;
        },
        resetAclPolicy: () => page.owners.api.webui.acl.resetPolicy(),
        refreshAclPolicyAfterReset: async (): Promise<void> => {
            await state.aclManager?.reload();
            callbacks.notifySaveChanged();
            dispatchCustomEvent('soai:search:request-refresh', {});
        },
        resetMetrics: () => page.owners.api.system.resetMetrics(),
        resetHardwareHistory: () => page.owners.api.system.resetHardwareHistory(),
        resetMovablePageLayouts: (): void => {
            page.owners.storage.saveDashboardLayout(null);
            page.owners.storage.remove('metrics_layout');
            page.owners.storage.remove('hardware_layout');
        },
        resetChatPresets: () => page.owners.api.webui.chat.presets.reset(),
        resetRecentSearches: (): void => page.owners.storage.clearRecentSearches(),
        clearPromptHistory: () => page.owners.api.webui.chat.promptHistory.clear(),
        deleteAllConversations: () => page.owners.api.webui.chat.deleteAll(),
        resetToolApprovalPermissions: () => page.owners.api.webui.preferences.resetToolApprovalPermissions(),
        resetPasswordVault: () => page.owners.api.webui.passwordVault.reset(),
        resetConfiguration: () => page.owners.api.webui.admin.resetConfiguration(),
        factoryReset: () => page.owners.api.webui.admin.factoryReset(),
        getWallpaperOverlay: (): number => page.owners.storage.getWallpaperOverlay(),
        getSolidBackground: (): string | null => page.owners.storage.getSolidBackground()
    },
    view: {
        pageDom: page.owners.pageDom,
        pageResources: page.owners.pageResources,
        setUIValue: (target: string | Element, value: string | null | undefined, options?: { attribute?: string }): void => page.owners.pageElements.setValue(target, value, options)
    },
    execution: {
        feedback: page.owners.feedback,
        runWithBoundary: <T>(name: string, task: () => Promise<T> | T): Promise<T> => page.owners.pageLifecycle.run(name, task),
        withButtonDisabled: callbacks.withButtonDisabled,
        confirmAndExecute: callbacks.confirmAndExecute
    },
    notifications: { feedback: page.owners.feedback },
    workflow: {
        canRunSystemAction: (action: SystemManagerActionId): boolean => {
            if (action === SETTINGS_SYSTEM_RESET_CONFIGURATION_ACTION) return hasSettingsAction(state, 'CONFIG_PATCH');
            if (action === SETTINGS_SYSTEM_FACTORY_RESET_ACTION) {
                return hasSettingsAction(state, 'FACTORY_RESET');
            }
            if (action === SETTINGS_SYSTEM_RESET_METRICS_ACTION || action === SETTINGS_SYSTEM_RESET_HARDWARE_HISTORY_ACTION) {
                return hasSettingsAction(state, 'METRICS_RESET');
            }
            return true;
        },
        setTimer: (functionValue: () => void, delay: number): number => {
            const timerId = page.owners.pageResources.setTimer(functionValue, delay);
            if (timerId === null) {
                throw new Error('Failed to allocate timer');
            }
            return timerId;
        },
        clearTimer: (timerId: number | null | undefined): void => page.owners.pageResources.clearTimer(timerId),
        applyWallpaperOverlay: callbacks.applyWallpaperOverlay,
        refreshWallpaperPreview: callbacks.refreshWallpaperPreview,
        refreshSettingsAfterPreferencesReset: async (): Promise<void> => await callbacks.refreshSettingsAfterPreferencesReset(),
        navigate: (route: string, options?: Record<string, JsonValue | null | undefined>): void => {
            page.owners.router.navigate(route, options);
        },
        filterSettings: callbacks.filterSettings,
        showRestartOverlay: (value: string): void => state.restartOverlay.show(value)
    }
});

export { createPreferencesManagerHost, createSystemManagerHost, createThemeManagerHost, createUsersManagerHost };
