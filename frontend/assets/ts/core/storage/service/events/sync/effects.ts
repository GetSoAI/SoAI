/* SoAI - Shared storage sync effects [frontend/assets/ts/core/storage/service/events/sync/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getBranding } from '@core/branding/public.ts';
import { dispatchCustomEvent, getMatchMedia } from '@core/environment/public.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { isAnimationSpeed, isInterfaceScalePercent } from '@core/storage/guards.ts';
import { syncLocalizationPreferencesFromUi } from '@core/storage/localizationPreferences.ts';
import { applyPresentationPreferenceDomEffects } from '@core/storage/service/presentationpreferences/domEffects.ts';
import { normalizeAccentColorPreference } from '@core/theme/accentColor.ts';
import { normalizeSurfaceColorPreference } from '@core/theme/surfaceColor.ts';
import { isBoolean, isObject, isString } from '@core/typeGuards.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { ThemeApplyOptions } from '@core/storage/service/types.ts';
import type { ThemeType } from '@core/storage/types.ts';
import type { StorageSyncApplyLocalContext, StorageSyncBootstrapContext } from '@core/storage/service/events/sync/types.ts';
import { applyThemeDomState, dispatchThemeChanged, resolveThemePreference, resolveThemePreferenceFromDom } from '@core/storage/service/events/sync/themeState.ts';
import { normalizeSessionData } from '@core/storage/normalization.ts';
import { resolveStoredParameters } from '@core/chat/parameters/chatParameterDefaults.ts';

const createThemeApplier = ({ state, syncLocal, scheduleBroadcast }: { state: StorageSyncBootstrapContext['state']; syncLocal: StorageSyncBootstrapContext['syncLocal']; scheduleBroadcast: StorageSyncBootstrapContext['scheduleBroadcast'] }): ((preference: string, options?: ThemeApplyOptions) => string) => {
    return (preference: string, options: ThemeApplyOptions = {}): string => {
        const persist = options.persist !== false;
        const update = options.update === true;
        const desiredTheme = resolveThemePreference(preference, state.cache.ui.theme);

        if (update) {
            state.cache.ui.theme = desiredTheme;
        }

        const systemThemeIsDark = state.systemThemeListener ? state.systemThemeListener.matches : getMatchMedia()('(prefers-color-scheme: dark)').matches;
        const actualTheme: ThemeType = desiredTheme === 'auto' ? (systemThemeIsDark ? 'dark' : 'light') : desiredTheme === 'light' ? 'light' : 'dark';

        applyThemeDomState(actualTheme);
        getBranding().updateAllLogos();
        dispatchThemeChanged(desiredTheme, actualTheme);

        if (persist) {
            syncLocal('ui');
            scheduleBroadcast();
        }

        return actualTheme;
    };
};

const applyLocalStorageState = ({
    state,
    adapters,
    effects,
    ensureMainState,
    syncLocal,
    applyTheme
}: StorageSyncApplyLocalContext & {
    applyTheme: (preference: string, options?: ThemeApplyOptions) => string;
}): void => {
    state.cache.ui.theme = resolveThemePreferenceFromDom(state.cache.ui.theme);

    if (state.localStorageAvailable) {
        const keys = state.localKeys;
        const themeValue = adapters.readStorage('localStorage', keys.theme);
        if (themeValue === 'auto' || themeValue === 'light' || themeValue === 'dark') {
            state.cache.ui.theme = themeValue;
        }

        const accentColorValue = adapters.readStorage('localStorage', keys.accentColor);
        const normalizedAccentColor = normalizeAccentColorPreference(accentColorValue);
        if (normalizedAccentColor !== null) {
            state.cache.ui.accentColor = normalizedAccentColor;
        }

        const surfaceColorValue = adapters.readStorage('localStorage', keys.surfaceColor);
        const normalizedSurfaceColor = normalizeSurfaceColorPreference(surfaceColorValue);
        if (normalizedSurfaceColor !== null) {
            state.cache.ui.surfaceColor = normalizedSurfaceColor;
        }

        const languageValue = adapters.readStorage('localStorage', keys.language);
        if (isString(languageValue) && languageValue.trim()) {
            state.cache.ui.language = languageValue.trim();
        }

        const animationSpeedValue = adapters.readStorage('localStorage', keys.animationSpeed);
        if (isAnimationSpeed(animationSpeedValue)) {
            state.cache.ui.animationSpeed = animationSpeedValue;
        }

        const interfaceScaleValue = adapters.readStorage('localStorage', keys.interfaceScale);
        if (isInterfaceScalePercent(interfaceScaleValue)) {
            state.cache.ui.interfaceScale = interfaceScaleValue;
        }

        const cachedChat = adapters.readStorage('localStorage', keys.chat);
        if (isObject(cachedChat)) {
            const defaults = state.defaults.chat;
            const current = state.cache.chat;
            const preferencesValue = cachedChat['preferences'];
            if (isJsonObject(preferencesValue)) {
                current.preferences = { ...defaults.preferences, parameters: resolveStoredParameters(preferencesValue) };
                const hideRealModelValue = preferencesValue['hide_real_model'];
                if (isBoolean(hideRealModelValue)) {
                    current.preferences.hideRealModel = hideRealModelValue;
                }
                const lockEnabledValue = preferencesValue['user_system_prompt_lock_enabled'];
                if (isBoolean(lockEnabledValue)) {
                    current.preferences.userSystemPromptLockEnabled = lockEnabledValue;
                }
                const lockValue = preferencesValue['user_system_prompt_lock_value'];
                if (isString(lockValue) || lockValue === null) {
                    current.preferences.userSystemPromptLockValue = lockValue;
                }
            }
            const defaultEmbeddingModelValue = cachedChat['default_embedding_model'];
            if (isString(defaultEmbeddingModelValue) || defaultEmbeddingModelValue === null) {
                current.defaultEmbeddingModel = defaultEmbeddingModelValue;
            }
            const textZoomValue = cachedChat['text_zoom'];
            if (isString(textZoomValue) || typeof textZoomValue === 'number') {
                const parsedValue = Number(textZoomValue);
                if (Number.isFinite(parsedValue)) {
                    current.textZoom = adapters.normalizeZoom(parsedValue, 0.5, 1.5);
                }
            }
            const widescreenModeValue = cachedChat['widescreen_mode'];
            if (typeof widescreenModeValue === 'boolean') {
                current.widescreenMode = widescreenModeValue;
            }
            const sidebarOpenValue = cachedChat['sidebar_open'];
            if (typeof sidebarOpenValue === 'boolean') {
                current.sidebarOpen = sidebarOpenValue;
            }
            const showFavoritesAtTopValue = cachedChat['show_favorites_at_top'];
            if (typeof showFavoritesAtTopValue === 'boolean') {
                current.showFavoritesAtTop = showFavoritesAtTopValue;
            }
            const planBarVisibleValue = cachedChat['plan_bar_visible'];
            if (typeof planBarVisibleValue === 'boolean') {
                current.planBarVisible = planBarVisibleValue;
            }
            const assistantAvatarValue = cachedChat['assistant_avatar'];
            if (isString(assistantAvatarValue) || assistantAvatarValue === null) {
                current.assistantAvatar = assistantAvatarValue;
            }
            const userAvatarValue = cachedChat['user_avatar'];
            if (isString(userAvatarValue) || userAvatarValue === null) {
                current.userAvatar = userAvatarValue;
            }
        }

        const cachedLogs = adapters.readStorage('localStorage', keys.logs);
        if (isObject(cachedLogs)) {
            const lineLimitValue = cachedLogs['line_limit'];
            if (typeof lineLimitValue === 'number' && Number.isFinite(lineLimitValue)) {
                state.cache.logs.lineLimit = adapters.normalizeLimit(lineLimitValue);
            }
            const textZoomValue = cachedLogs['text_zoom'];
            if (typeof textZoomValue === 'number' && Number.isFinite(textZoomValue)) {
                state.cache.logs.textZoom = adapters.normalizeZoom(textZoomValue, 0.5, 2);
            }
        }
    }

    state.session = normalizeSessionData(adapters.readStorage('sessionStorage', state.localKeys.session) ?? null);
    const redirectAfterLogin = state.session['redirect_after_login'];
    state.redirectAfterLogin = isString(redirectAfterLogin) ? redirectAfterLogin : null;

    const ui = state.cache.ui;
    syncLocalizationPreferencesFromUi(ui, { dispatch: false });
    applyPresentationPreferenceDomEffects({
        preferences: ui,
        includeHeaderAutoHideClass: true,
        dispatchClockChanged: true,
        applyTheme,
        effects
    });
    ensureMainState();
    void syncLocal;
};

const bootstrapStorageSync = async ({ state, adapters, flushPending, applyTheme, connectShared, broadcast, applyLocal }: StorageSyncBootstrapContext): Promise<void> => {
    adapters.initializeStorageAvailability();
    state.systemThemeListener = getMatchMedia()('(prefers-color-scheme: dark)');
    if (!state.systemThemeListener) {
        throw new Error('matchMedia failed');
    }
    getMaintenanceCoordinator().subscribe((maintenance) => {
        state.maintenanceHold = maintenance.pausesTransport;
        if (!maintenance.pausesTransport && state.pendingGroups.size > 0) {
            terminateHandledPromise(flushPending());
        }
    });

    applyLocal();
    await connectShared();

    state.resources.addEventListener(state.systemThemeListener, 'change', () => {
        if (state.cache.ui.theme === 'auto') {
            applyTheme('auto', { persist: false });
        }
    });

    await broadcast();
    dispatchCustomEvent('soai:storage:ready', null);
};

export { applyLocalStorageState, bootstrapStorageSync, createThemeApplier };
