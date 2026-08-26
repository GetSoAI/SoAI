/* SoAI - Shared storage preferences service [frontend/assets/ts/core/storage/service/preferences/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { createPreferenceHandlers } from '@core/storage/service/preferences/actions.ts';
import { syncLocalizationPreferences } from '@core/storage/service/localizationpreferences/actions.ts';
import type { PreferenceDelegates, StorageApiClientContract, StorageRuntime, StoragePreferenceMethods } from '@core/storage/service/preferences/types.ts';
import { applyPresentationPreferenceState } from '@core/storage/service/presentationpreferences/apply.ts';
import type { ChatPreferencesManager, ThemeType, UiPreferences } from '@core/storage/types.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { APIError } from '@core/apiError.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isBoolean, isObject, isString } from '@core/typeGuards.ts';

const CLOCK_PREFERENCE_KEYS = new Set(['header_clock_enabled', 'clock_seconds_enabled']);

const createStoragePreferenceMethods = (core: StorageRuntime, apiClient: StorageApiClientContract, delegates: PreferenceDelegates): StoragePreferenceMethods => {
    const state = core.state;

    const refresh = async (options: { authTransitionOwned?: boolean } = {}): Promise<void> => {
        const getterFunction = apiClient?.webui?.preferences?.get;
        if (!getterFunction) {
            state.isAuthenticated = false;
            return;
        }
        let result: JsonObject;
        try {
            result = await core.refreshChatPreferences(options);
        } catch (error) {
            const status = error instanceof APIError ? error.status : 0;
            if ([401, 403, 404].includes(status)) {
                state.isAuthenticated = false;
                return;
            }
            throw error;
        }
        state.isAuthenticated = true;
        core.mergeRemote(result);
        core.scheduleBroadcast();
    };

    const setAuthenticated = async (authenticated: boolean, options: { authTransitionOwned?: boolean } = {}): Promise<void> => {
        if (!authenticated) {
            state.isAuthenticated = false;
            state.pendingGroups.clear();
            state.persistedChecksums = {};
            state.inflightChecksums = {};
            state.queuedChecksums = {};
            const theme = state.cache.ui.theme;
            const accentColor = state.cache.ui.accentColor;
            const surfaceColor = state.cache.ui.surfaceColor;
            const interfaceScale = state.cache.ui.interfaceScale;
            state.cache = core.createDefaults();
            state.cache.ui.theme = theme;
            state.cache.ui.accentColor = normalizeAccentColorPreference(accentColor) ?? null;
            state.cache.ui.surfaceColor = normalizeSurfaceColorPreference(surfaceColor) ?? null;
            state.cache.ui.interfaceScale = interfaceScale;
            const redirectAfterLogin = state.session['redirect_after_login'];
            state.session = isString(redirectAfterLogin) ? { redirectAfterLogin: redirectAfterLogin } : {};
            core.writeStorage('sessionStorage', state.localKeys.session, toJsonCompatibleValue(state.session));
            syncLocalizationPreferences(core);
            applyPresentationPreferenceState(core);
            core.scheduleBroadcast();
            return;
        }
        const previouslyAuthenticated = state.isAuthenticated;
        state.isAuthenticated = true;
        try {
            await refresh(options);
        } catch (error) {
            state.isAuthenticated = previouslyAuthenticated;
            throw error;
        }
        if (!state.isAuthenticated) return;
        await core.flushPending();
        if (!state.isAuthenticated) return;
        core.scheduleBroadcast();
    };

    const getPreferences = (): UiPreferences => core.clone(state.cache.ui);

    const getTheme = (): ThemeType => state.cache.ui.theme || 'auto';

    const getPromptEnhancerModel = (): string | null => {
        const value = state.cache.ui.promptEnhancerModel;
        return typeof value === 'string' && value.trim() ? value : null;
    };

    const setTheme = (preference: string): string => core.applyTheme(preference, { update: true });

    const toggleTheme = (): string => {
        const current = getTheme();
        if (current === 'dark') {
            return setTheme('light');
        }
        if (current === 'light') {
            return setTheme('auto');
        }
        return setTheme('dark');
    };

    const saveDashboardLayout = (layout: JsonObject | null | undefined): void => {
        const normalizedLayout = layout ? toJsonCompatibleValue(layout) : null;
        state.cache.ui.dashboardLayout = isJsonObject(normalizedLayout) ? normalizedLayout : null;
        terminateHandledPromise(core.queuePersist('ui'));
    };

    const getDashboardLayout = (): JsonObject | null => (isJsonObject(state.cache.ui.dashboardLayout) ? core.clone(state.cache.ui.dashboardLayout) : null);

    const preferenceHandlers = createPreferenceHandlers({
        core,
        delegates,
        setTheme,
        saveDashboardLayout
    });

    const setPreference = (keyCandidate: string, value: JsonObject[keyof JsonObject] | null | undefined): UiPreferences => {
        if (!isString(keyCandidate) || !keyCandidate.trim()) {
            return getPreferences();
        }
        const key = keyCandidate.trim();
        const handler = preferenceHandlers[key];
        const normalizedValue = value === undefined ? undefined : toJsonCompatibleValue(value);
        if (handler) {
            handler(normalizedValue);
            return getPreferences();
        }
        errorHandler.warn('StorageManager', `Unsupported UI preference key '${key}'`, value);
        return getPreferences();
    };

    const setPreferences = (patch: JsonObject | null | undefined): UiPreferences => {
        if (isObject(patch)) {
            const headerClockEnabled = patch['header_clock_enabled'];
            const clockSecondsEnabled = patch['clock_seconds_enabled'];
            if (headerClockEnabled !== undefined || clockSecondsEnabled !== undefined) {
                if (headerClockEnabled !== undefined && !isBoolean(headerClockEnabled)) {
                    errorHandler.warn('StorageManager', 'Invalid header_clock_enabled preference value', headerClockEnabled);
                }
                if (clockSecondsEnabled !== undefined && !isBoolean(clockSecondsEnabled)) {
                    errorHandler.warn('StorageManager', 'Invalid clock_seconds_enabled preference value', clockSecondsEnabled);
                }
                const normalizedHeaderClockEnabled = isBoolean(headerClockEnabled) ? headerClockEnabled : state.cache.ui.headerClockEnabled !== false;
                const normalizedClockSecondsEnabled = isBoolean(clockSecondsEnabled) ? clockSecondsEnabled : state.cache.ui.clockSecondsEnabled === true;
                delegates.setClockPreferences(normalizedHeaderClockEnabled, normalizedClockSecondsEnabled);
            }
            for (const [key, value] of Object.entries(patch)) {
                if (CLOCK_PREFERENCE_KEYS.has(key)) {
                    continue;
                }
                setPreference(key, value);
            }
        }
        return getPreferences();
    };

    const getChatPreferences = (): ChatPreferencesManager => core.clone(state.cache.chat.preferences);

    const setPromptEnhancerModel = (value: string | null): UiPreferences => {
        state.cache.ui.promptEnhancerModel = typeof value === 'string' && value.trim() ? value.trim() : null;
        terminateHandledPromise(core.queuePersist('ui'));
        return getPreferences();
    };

    return {
        refresh,
        setAuthenticated,
        getPreferences,
        setPreferences,
        setPreference,
        getTheme,
        setTheme,
        toggleTheme,
        saveDashboardLayout,
        getDashboardLayout,
        getChatPreferences,
        getPromptEnhancerModel,
        setPromptEnhancerModel
    };
};

export { createStoragePreferenceMethods };
export type { PreferenceDelegates };
