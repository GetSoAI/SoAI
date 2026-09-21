/* SoAI - Settings page preferences contracts [frontend/assets/ts/pages/settings/controllers/preferences/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConfigurationManager } from '@core/configurationManager.ts';
import type { OcrLanguage } from '@core/api/contracts/ocrLanguageContracts.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { DateFormatPreference, MeasurementUnitsPreference, RegionalLocalePreference } from '@core/localization/public.ts';
import type { LanguageEntryWithFlag } from '@core/languageservice/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { UiPreferenceKey } from '@core/settings/settingsFieldKeys.ts';
import type { InterfaceScalePercent } from '@core/layout/interfaceScale.ts';

interface PreferencesStorage {
    getClockFormat: () => '12h' | '24h';
    setClockFormat: (format: '12h' | '24h') => void;
    getRegionalLocale: () => RegionalLocalePreference;
    setRegionalLocale: (locale: RegionalLocalePreference) => void;
    getDateFormat: () => DateFormatPreference;
    setDateFormat: (format: DateFormatPreference) => void;
    getMeasurementUnits: () => MeasurementUnitsPreference;
    setMeasurementUnits: (units: MeasurementUnitsPreference) => void;
    getNotificationDuration: () => number;
    setNotificationDuration: (value: number) => void;
    getInterfaceScale: () => InterfaceScalePercent;
    setInterfaceScale: (percent: InterfaceScalePercent) => void;
    getHeaderClockEnabled: () => boolean;
    getClockSecondsEnabled: () => boolean;
    setClockPreferences: (headerClockEnabled: boolean, clockSecondsEnabled: boolean) => void;
    getSoundEffects: () => boolean;
    setSoundEffects: (enabled: boolean) => void;
    getLiveStatusOverlayEnabled: () => boolean;
    setLiveStatusOverlayEnabled: (enabled: boolean) => void;
    getPromptEnhancerModel: () => string | null;
    setPromptEnhancerModel: (value: string | null) => void;
}

interface PreferencesLanguageService {
    getLanguage: () => string;
    setLanguage: (lang: string) => Promise<void>;
    getAvailableLanguages: () => ReadonlyArray<LanguageEntryWithFlag>;
}

interface PreferencesManagerHost extends PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    createConfigurationManager: () => ConfigurationManager;
    getCurrentUserId: () => number | null;
    isDestroyed: () => boolean;
    loadOcrLanguages: (signal: AbortSignal) => Promise<readonly OcrLanguage[]>;
    loadPreferences: (signal: AbortSignal) => Promise<JsonObject>;
    saveOcrPreference: (code: string, intendedUserId: number, signal: AbortSignal) => Promise<JsonObject>;
    syncManualDirtyField: (key: string, modified: boolean, valid: boolean) => void;
    notifySaveChanged: () => void;
    languageService: PreferencesLanguageService;
    storage: PreferencesStorage;
    getUiPrefValue: (key: UiPreferenceKey) => JsonValue | null | undefined;
    setUiPrefValue: (key: UiPreferenceKey, value: JsonValue | null | undefined) => void;
    filterSettings: () => void;
}

interface PreferencesManagerDependencies {
    host: PreferencesManagerHost;
}

interface PreferenceToggleStates {
    enabled: string;
    disabled: string;
}

interface PreferenceToggleExternalEvent {
    name: string;
    getValue: (event: CustomEvent) => boolean;
}

interface PreferenceToggleContract {
    id: string;
    getValue: () => boolean;
    setValue: (value: boolean) => void;
    notifyKey: string;
    notifyStates: PreferenceToggleStates | null;
    externalEvent: PreferenceToggleExternalEvent | null;
}

interface PreferenceViewModel {
    languageOptions: Array<{ value: string; label: string }>;
    selectedLanguage: string;
    selectedClockFormat: '12h' | '24h';
    notificationDuration: number;
    toggles: Array<{ id: string; label: string; help: string; checked: boolean }>;
}

export type { PreferenceToggleContract, PreferenceToggleExternalEvent, PreferenceToggleStates, PreferenceViewModel, PreferencesLanguageService, PreferencesManagerDependencies, PreferencesManagerHost, PreferencesStorage };
