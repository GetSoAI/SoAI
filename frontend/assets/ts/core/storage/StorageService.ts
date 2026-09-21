/* SoAI - Shared storage service [frontend/assets/ts/core/storage/StorageService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { normalizeStringArray } from '@core/storage/normalization.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { createStorageRuntime } from '@core/storage/service/runtime.ts';
import { createStoragePreferenceMethods } from '@core/storage/service/preferences/service.ts';
import { createLocalizationPreferenceMethods } from '@core/storage/service/localizationpreferences/actions.ts';
import { createPresentationPreferenceMethods } from '@core/storage/service/presentationpreferences/service.ts';
import { createStorageStateActions } from '@core/storage/service/actions.ts';
import { createStoragePageControlMethods } from '@core/storage/service/pageControls.ts';
import { createStorageStateReaders } from '@core/storage/service/state.ts';
import { serializeChatPreferences } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { serializeHardwareCache, serializePageControlStates } from '@core/storage/persistence/operationalPreferenceSerialization.ts';
import { parseSettingsBackup, serializeSettingsBackup, type ExportedSettings } from '@core/storage/persistence/settingsBackupSerialization.ts';
import { applyUiPatch } from '@core/storage/persistence/mergeremotepreferences/mappers.ts';
import type { StorageApiClientContract, StorageRuntimeDependencies } from '@core/storage/service/types.ts';
import type { SessionData, UiPreferences } from '@core/storage/types.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

interface ResetOptions {
    preserveWizardState?: boolean | undefined;
}

type StorageInputValue = JsonValue | null | undefined;
const createStorageService = (dependencies: StorageRuntimeDependencies) => {
    const runtime = createStorageRuntime(dependencies);
    const storageState = {
        ...createStorageStateReaders(runtime),
        ...createStorageStateActions(runtime),
        ...createStoragePageControlMethods(runtime)
    };
    const presentationPreferences = createPresentationPreferenceMethods(runtime);
    const localizationPreferences = createLocalizationPreferenceMethods(runtime);
    localizationPreferences.syncLocalizationPreferences({ dispatch: false });
    const preferences = createStoragePreferenceMethods(runtime, dependencies.apiClient, {
        setLanguage: storageState.setLanguage,
        setClockFormat: storageState.setClockFormat,
        setRegionalLocale: localizationPreferences.setRegionalLocale,
        setDateFormat: localizationPreferences.setDateFormat,
        setMeasurementUnits: localizationPreferences.setMeasurementUnits,
        setNotificationDuration: presentationPreferences.setNotificationDuration,
        setCodeRecognitionEnabled: presentationPreferences.setCodeRecognitionEnabled,
        setClockPreferences: presentationPreferences.setClockPreferences,
        setReduceMotions: presentationPreferences.setReduceMotions,
        setAccentColor: presentationPreferences.setAccentColor,
        setSurfaceColor: presentationPreferences.setSurfaceColor,
        setSoundEffects: presentationPreferences.setSoundEffects,
        setLiveStatusOverlayEnabled: presentationPreferences.setLiveStatusOverlayEnabled,
        setWallpaperOverlay: presentationPreferences.setWallpaperOverlay,
        setSolidBackground: presentationPreferences.setSolidBackground,
        setGlassEnabled: presentationPreferences.setGlassEnabled,
        setHiddenSidebarPages: storageState.setHiddenSidebarPages,
        setShowMainStatusIndicator: storageState.setShowMainStatusIndicator,
        setHiddenDashboardElements: storageState.setHiddenDashboardElements,
        setDashboardLocked: storageState.setDashboardLocked,
        setDashboardImageCard: storageState.setDashboardImageCard,
        setDashboardImageCardFit: storageState.setDashboardImageCardFit,
        setDashboardMemo: storageState.setDashboardMemo,
        setDefaultPage: storageState.setDefaultPage,
        setChartColorMode: presentationPreferences.setChartColorMode,
        setChartStaticColor: presentationPreferences.setChartStaticColor,
        setHeaderAutoHide: presentationPreferences.setHeaderAutoHide,
        setShowScrollToTopButton: presentationPreferences.setShowScrollToTopButton,
        setPageAnimation: presentationPreferences.setPageAnimation,
        setModalAnimation: presentationPreferences.setModalAnimation,
        setNotificationAnimation: presentationPreferences.setNotificationAnimation,
        setAnimationSpeed: presentationPreferences.setAnimationSpeed,
        setInterfaceScale: presentationPreferences.setInterfaceScale,
        setPromptEnhancerModel: storageState.setPromptEnhancerModel
    });
    const normalizeStorageInput = (value: StorageInputValue): JsonValue | null => {
        if (value === undefined) {
            return null;
        }
        return isJsonValue(value) ? value : toJsonCompatibleValue(value);
    };
    const keyBindings: Record<string, { get: (fallback?: JsonValue | null) => JsonValue | null; set: (value: StorageInputValue) => void }> = {
        'soai_chat_preferences': { get: () => serializeChatPreferences(preferences.getChatPreferences()), set: (value) => storageState.setChatPreferences(normalizeStorageInput(value)) },
        'soai_chat_text_zoom': {
            get: (fallback) => storageState.getChatTextZoom(isNumber(fallback) ? fallback : runtime.state.defaults.chat.textZoom),
            set: (value) => {
                if (isNumber(value) && Number.isFinite(value)) {
                    storageState.setChatTextZoom(value);
                }
            }
        },
        'soai_log_line_limit': {
            get: () => storageState.getLogLineLimit(),
            set: (value) => {
                if (isNumber(value) && Number.isFinite(value)) {
                    storageState.setLogLineLimit(value);
                }
            }
        },
        'soai_logs_text_zoom': {
            get: (fallback) => storageState.getLogsTextZoom(isNumber(fallback) ? fallback : runtime.state.defaults.logs.textZoom),
            set: (value) => {
                if (isNumber(value) && Number.isFinite(value)) {
                    storageState.setLogsTextZoom(value);
                }
            }
        },
        'soai_terminal_preferences': { get: () => ({ 'text_zoom': presentationPreferences.getTerminalPreferences().textZoom }), set: (value) => presentationPreferences.setTerminalPreferences(normalizeStorageInput(value)) },
        'soai_terminal_text_zoom': {
            get: (fallback) => presentationPreferences.getTerminalTextZoom(isNumber(fallback) ? fallback : runtime.state.defaults.terminal.textZoom),
            set: (value) => {
                if (isNumber(value) && Number.isFinite(value)) {
                    presentationPreferences.setTerminalTextZoom(value);
                }
            }
        },
        'soai_recent_searches': {
            get: () => storageState.getRecentSearches(),
            set: (value) => {
                runtime.state.cache.search.recent = normalizeStringArray(value ?? null, 50);
                terminateHandledPromise(runtime.queuePersist('search'));
            }
        },
        'soai_hardware_prefs': { get: () => serializeHardwareCache(storageState.getHardwarePreferences()), set: (value) => storageState.setHardwarePreferences(normalizeStorageInput(value)) },
        'soai_page_controls': { get: () => serializePageControlStates(storageState.getPageControlStates()), set: (value) => storageState.setPageControlStates(normalizeStorageInput(value)) }
    };
    const normalizeKey = (key: string): string => (key.startsWith('soai_') ? key : `soai_${key}`);
    const get = (keyCandidate: string, defaultValue: JsonValue | null = null): JsonValue | null => {
        if (!isString(keyCandidate) || !keyCandidate.trim()) {
            return defaultValue;
        }
        const normalized = normalizeKey(keyCandidate.trim());
        const binding = keyBindings[normalized];
        if (binding) {
            return binding.get(defaultValue);
        }
        return runtime.state.cache.misc[normalized] !== undefined ? runtime.clone(runtime.state.cache.misc[normalized]) : defaultValue;
    };
    const set = (keyCandidate: string, value: StorageInputValue): void => {
        if (!isString(keyCandidate) || !keyCandidate.trim()) {
            return;
        }
        const normalized = normalizeKey(keyCandidate.trim());
        const binding = keyBindings[normalized];
        if (binding) {
            binding.set(value);
            return;
        }
        if (value === undefined) {
            delete runtime.state.cache.misc[normalized];
        } else {
            runtime.state.cache.misc[normalized] = normalizeStorageInput(value);
        }
        terminateHandledPromise(runtime.queuePersist('misc'));
        runtime.syncLocal('misc');
        if (normalized === 'soai_connection_base_url') {
            runtime.scheduleBroadcast();
        }
    };
    const remove = (key: string): void => {
        set(key, undefined);
    };
    const resetUiPreferences = (options: ResetOptions = {}): UiPreferences => {
        const preserveWizardState = options.preserveWizardState !== false;
        const defaults = runtime.createDefaults();
        const preservedWizard = preserveWizardState ? runtime.state.cache.wizard : defaults.wizard;
        const preservedMisc = runtime.state.cache.misc;
        preferences.setTheme(defaults.ui.theme);
        storageState.setLanguage(defaults.ui.language);
        storageState.setClockFormat(defaults.ui.clockFormat);
        localizationPreferences.setRegionalLocale(defaults.ui.regionalLocale);
        localizationPreferences.setDateFormat(defaults.ui.dateFormat);
        localizationPreferences.setMeasurementUnits(defaults.ui.measurementUnits);
        presentationPreferences.setNotificationDuration(defaults.ui.notificationDuration);
        presentationPreferences.setCodeRecognitionEnabled(defaults.ui.codeRecognitionEnabled);
        presentationPreferences.setClockPreferences(defaults.ui.headerClockEnabled, defaults.ui.clockSecondsEnabled);
        preferences.setPromptEnhancerModel(defaults.ui.promptEnhancerModel);
        presentationPreferences.setReduceMotions(defaults.ui.reduceMotions);
        presentationPreferences.setAccentColor(defaults.ui.accentColor);
        presentationPreferences.setSurfaceColor(defaults.ui.surfaceColor);
        presentationPreferences.setSoundEffects(defaults.ui.soundEffects);
        presentationPreferences.setLiveStatusOverlayEnabled(defaults.ui.liveStatusOverlayEnabled);
        presentationPreferences.setGlassEnabled(defaults.ui.glassEnabled);
        presentationPreferences.setWallpaperOverlay(defaults.ui.wallpaperOverlay);
        presentationPreferences.setSolidBackground(defaults.ui.solidBackground);
        presentationPreferences.setChartColorMode(defaults.ui.chartColorMode);
        presentationPreferences.setChartStaticColor(defaults.ui.chartStaticColor);
        storageState.setHiddenSidebarPages(defaults.ui.hiddenSidebarPages);
        storageState.setHiddenDashboardElements(defaults.ui.hiddenDashboardElements);
        storageState.setDashboardLocked(defaults.ui.dashboardLocked);
        storageState.setDashboardImageCard(defaults.ui.dashboardImageCard);
        storageState.setDashboardImageCardFit(defaults.ui.dashboardImageCardFit);
        storageState.setDashboardMemo(defaults.ui.dashboardMemo);
        storageState.setDefaultPage(defaults.ui.defaultPage);
        presentationPreferences.setHeaderAutoHide(defaults.ui.headerAutoHide);
        presentationPreferences.setShowScrollToTopButton(defaults.ui.showScrollToTopButton);
        storageState.setShowMainStatusIndicator(defaults.ui.showMainStatusIndicator);
        presentationPreferences.setPageAnimation(defaults.ui.pageAnimation);
        presentationPreferences.setModalAnimation(defaults.ui.modalAnimation);
        presentationPreferences.setNotificationAnimation(defaults.ui.notificationAnimation);
        presentationPreferences.setAnimationSpeed(defaults.ui.animationSpeed);
        presentationPreferences.setInterfaceScale(defaults.ui.interfaceScale);
        presentationPreferences.clearAllModalStates();
        runtime.state.cache.ui.mainStatePreferenceVersion = defaults.ui.mainStatePreferenceVersion;
        runtime.state.cache.chat.preferences = runtime.clone(defaults.chat.preferences);
        runtime.state.cache.chat.defaultEmbeddingModel = defaults.chat.defaultEmbeddingModel ?? null;
        runtime.state.cache.chat.textZoom = defaults.chat.textZoom;
        runtime.state.cache.logs = runtime.clone(defaults.logs);
        runtime.state.cache.terminal = runtime.clone(defaults.terminal);
        runtime.state.cache.search = runtime.clone(defaults.search);
        runtime.state.cache.hardware = runtime.clone(defaults.hardware);
        runtime.state.cache.filters = runtime.clone(defaults.filters);
        runtime.state.cache.wizard = runtime.clone(preservedWizard);
        runtime.state.cache.settings = runtime.clone(defaults.settings);
        runtime.state.cache.misc = runtime.clone(preservedMisc);
        const resetGroups: readonly string[] = ['chat', 'logs', 'terminal', 'search', 'hardware', 'filters', 'wizard', 'settings', 'misc'];
        for (const group of resetGroups) {
            terminateHandledPromise(runtime.queuePersist(group));
        }
        runtime.scheduleBroadcast();
        return preferences.getPreferences();
    };
    const exportSettings = (): ExportedSettings => {
        return serializeSettingsBackup({
            ui: preferences.getPreferences(),
            chatPreferences: preferences.getChatPreferences(),
            logs: storageState.getLogsPreferences(),
            recentSearches: storageState.getRecentSearches(),
            hardware: storageState.getHardwarePreferences(),
            pageControls: storageState.getPageControlStates(),
            exportedAt: new Date().toISOString()
        });
    };
    const importSettings = (settings: JsonValue | null | undefined): void => {
        const parsed = parseSettingsBackup(settings);
        if (parsed.ui) {
            const importedUiPreferences = runtime.clone(runtime.state.cache.ui);
            applyUiPatch(parsed.ui, importedUiPreferences);
            preferences.setPreferences(parsed.ui);
            presentationPreferences.setCodeRecognitionEnabled(importedUiPreferences.codeRecognitionEnabled);
            presentationPreferences.setInterfaceScale(importedUiPreferences.interfaceScale);
        }
        if (parsed.chatPreferences) {
            storageState.setChatPreferences(parsed.chatPreferences);
        }
        if (parsed.hardware) {
            storageState.setHardwarePreferences(parsed.hardware);
        }
        if (parsed.pageControls) {
            storageState.setPageControlStates(parsed.pageControls);
        }
        if (parsed.recentSearches) {
            set('soai_recent_searches', parsed.recentSearches);
        }
        if (parsed.logs) {
            storageState.setLogsPreferences(parsed.logs);
        }
    };
    const service = {
        ready: runtime.ready,
        get session(): SessionData {
            return runtime.state.session;
        },
        refresh: preferences.refresh,
        refreshAuthoritativeChatPreferences: runtime.refreshChatPreferences,
        persistAuthoritativeChatPatch: runtime.persistChatPreferencePatch,
        prepareAuthoritativeChatPatch: runtime.prepareChatPreferencePatch,
        prepareAuthoritativeChatProjection: runtime.prepareExternalChatPreferenceProjection,
        prepareChatPreferenceInvalidation: runtime.prepareChatPreferenceInvalidation,
        getPendingConversationDefaults: runtime.pendingConversationDefaults,
        setAuthenticated: preferences.setAuthenticated,
        getPreferences: preferences.getPreferences,
        setPreferences: preferences.setPreferences,
        setPreference: preferences.setPreference,
        resetUiPreferences,
        getTheme: preferences.getTheme,
        setTheme: preferences.setTheme,
        toggleTheme: preferences.toggleTheme,
        saveDashboardLayout: preferences.saveDashboardLayout,
        getDashboardLayout: preferences.getDashboardLayout,
        getChatPreferences: preferences.getChatPreferences,
        getPromptEnhancerModel: preferences.getPromptEnhancerModel,
        get,
        set,
        remove,
        flushPending: runtime.flushPending,
        exportSettings,
        importSettings,
        ...storageState,
        ...localizationPreferences,
        ...presentationPreferences
    };
    return service;
};
export { createStorageService };
export type { ExportedSettings, ResetOptions, StorageApiClientContract, StorageRuntimeDependencies };
export type StorageService = ReturnType<typeof createStorageService>;
