/* SoAI - Shared storage service [frontend/assets/ts/core/storage/StorageService.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { normalizeStringArray } from '@core/storage/normalization.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { createStorageRuntime } from '@core/storage/service/runtime.ts';
import { resetUiPreferences, type ResetOptions } from '@core/storage/service/preferences/preferenceReset.ts';
import type { PreferenceDelegates } from '@core/storage/service/preferences/types.ts';
import { createStoragePreferenceMethods } from '@core/storage/service/preferences/service.ts';
import { createLocalizationPreferenceMethods } from '@core/storage/service/localizationpreferences/actions.ts';
import { createPresentationPreferenceMethods } from '@core/storage/service/presentationpreferences/service.ts';
import { createStorageStateActions } from '@core/storage/service/actions.ts';
import { createAiSetupStateMethods } from '@core/storage/service/aiSetupActions.ts';
import { createStoragePageControlMethods } from '@core/storage/service/pageControls.ts';
import { createStorageStateReaders } from '@core/storage/service/state.ts';
import { serializeChatPreferences } from '@core/storage/persistence/chatPreferenceSerialization.ts';
import { serializeHardwareCache, serializePageControlStates } from '@core/storage/persistence/operationalPreferenceSerialization.ts';
import { parseSettingsBackup, serializeSettingsBackup, type ExportedSettings } from '@core/storage/persistence/settingsBackupSerialization.ts';
import { applyUiPatch } from '@core/storage/persistence/mergeremotepreferences/mappers.ts';
import type { StorageApiClientContract, StorageRuntimeDependencies } from '@core/storage/service/types.ts';
import type { SessionData } from '@core/storage/types.ts';
import { isNumber, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { preferenceRequestIdentityIsCurrent, readPreferenceRequestIdentity } from '@core/storage/chatpreferences/preferenceRequestIdentity.ts';

type StorageInputValue = JsonValue | null | undefined;
const createStorageService = (dependencies: StorageRuntimeDependencies) => {
    const runtime = createStorageRuntime(dependencies);
    const storageState = {
        ...createStorageStateReaders(runtime),
        ...createStorageStateActions(runtime),
        ...createStoragePageControlMethods(runtime),
        ...createAiSetupStateMethods(runtime)
    };
    const presentationPreferences = createPresentationPreferenceMethods(runtime);
    const localizationPreferences = createLocalizationPreferenceMethods(runtime);
    localizationPreferences.syncLocalizationPreferences({ dispatch: false });
    const preferenceDelegates: PreferenceDelegates = {
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
        setDefaultWallpaper: presentationPreferences.setDefaultWallpaper,
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
    };
    const preferences = createStoragePreferenceMethods(runtime, dependencies.apiClient, preferenceDelegates);
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
        subscribeUiPreferenceChanges: runtime.subscribeUiPreferenceChanges,
        optionalRecords: { readOptionalRecord: runtime.readOptionalRecord, writeOptionalRecord: runtime.writeOptionalRecord, removeOptionalRecord: runtime.removeOptionalRecord },
        getAuthenticatedIdentity: () => {
            const identity = readPreferenceRequestIdentity(runtime.state);
            return identity && preferenceRequestIdentityIsCurrent(runtime.state, identity) ? identity : null;
        },
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
        resetUiPreferences: (options: ResetOptions = {}) => resetUiPreferences(runtime, { ...preferenceDelegates, setTheme: preferences.setTheme, setPromptEnhancerModel: preferences.setPromptEnhancerModel, clearAllModalStates: presentationPreferences.clearAllModalStates }, options),
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
