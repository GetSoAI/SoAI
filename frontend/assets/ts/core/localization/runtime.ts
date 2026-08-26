/* SoAI - Shared localization runtime [frontend/assets/ts/core/localization/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { dispatchCustomEvent } from '@core/environment/public.ts';
import { isClockFormatPreference, isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/guards.ts';
import type { DateFormatPreference, LocalizationChangedDetail, LocalizationPreferences, LocalizationSnapshot, MeasurementUnitsPreference, RegionalLocalePreference, ResolvedDateOrder, ResolvedMeasurementUnits } from '@core/localization/types.ts';
import { isString } from '@core/typeGuards.ts';

const LOCALIZATION_CHANGED_EVENT = 'soai:localization:changed';

const DEFAULT_LOCALIZATION_PREFERENCES: LocalizationPreferences = Object.freeze({
    language: 'en',
    clockFormat: '24h',
    regionalLocale: 'auto',
    dateFormat: 'auto',
    measurementUnits: 'auto'
});

let snapshotVersion = 1;

const normalizeLanguage = (value: JsonValue | undefined): string => {
    if (!isString(value)) {
        return DEFAULT_LOCALIZATION_PREFERENCES.language;
    }
    const trimmed = value.trim();
    return trimmed ? trimmed : DEFAULT_LOCALIZATION_PREFERENCES.language;
};

const canonicalizeLocale = (value: string): string => {
    try {
        const canonical = Intl.getCanonicalLocales(value.trim());
        return canonical[0] || DEFAULT_LOCALIZATION_PREFERENCES.language;
    } catch {
        return DEFAULT_LOCALIZATION_PREFERENCES.language;
    }
};

const resolveBrowserLocale = (): string => {
    if (typeof navigator !== 'object') {
        return DEFAULT_LOCALIZATION_PREFERENCES.language;
    }
    const candidate = navigator.language || navigator.languages?.[0] || DEFAULT_LOCALIZATION_PREFERENCES.language;
    return canonicalizeLocale(candidate);
};

const resolveBrowserCountryCode = (): string | null => {
    const locale = resolveBrowserLocale();
    const region = locale.split('-').find((component) => /^[A-Z]{2}$/.test(component));
    return region ?? null;
};

const normalizeRegionalLocale = (value: JsonValue | undefined): RegionalLocalePreference => (isRegionalLocalePreference(value) ? value : DEFAULT_LOCALIZATION_PREFERENCES.regionalLocale);

const normalizeDateFormat = (value: JsonValue | undefined): DateFormatPreference => (isDateFormatPreference(value) ? value : DEFAULT_LOCALIZATION_PREFERENCES.dateFormat);

const normalizeMeasurementUnits = (value: JsonValue | undefined): MeasurementUnitsPreference => (isMeasurementUnitsPreference(value) ? value : DEFAULT_LOCALIZATION_PREFERENCES.measurementUnits);

const normalizeLocalizationPreferences = (value: Partial<LocalizationPreferences>): LocalizationPreferences => ({
    language: normalizeLanguage(value.language),
    clockFormat: isClockFormatPreference(value.clockFormat) ? value.clockFormat : DEFAULT_LOCALIZATION_PREFERENCES.clockFormat,
    regionalLocale: normalizeRegionalLocale(value.regionalLocale),
    dateFormat: normalizeDateFormat(value.dateFormat),
    measurementUnits: normalizeMeasurementUnits(value.measurementUnits)
});

const resolveLocale = (preferences: LocalizationPreferences): string => {
    if (preferences.regionalLocale === 'browser') {
        return resolveBrowserLocale();
    }
    if (preferences.regionalLocale !== 'auto') {
        return preferences.regionalLocale;
    }
    return canonicalizeLocale(preferences.language);
};

const resolveDateOrder = (preference: DateFormatPreference): ResolvedDateOrder => {
    if (preference === 'us' || preference === 'eu' || preference === 'iso') {
        return preference;
    }
    return 'locale';
};

const resolveMeasurementUnits = (preference: MeasurementUnitsPreference, locale: string): ResolvedMeasurementUnits => {
    if (preference === 'metric' || preference === 'imperial') {
        return preference;
    }
    return locale.toUpperCase().endsWith('-US') ? 'imperial' : 'metric';
};

const createLocalizationSnapshot = (preferencesCandidate: LocalizationPreferences, version: number): LocalizationSnapshot => {
    const preferences = normalizeLocalizationPreferences(preferencesCandidate);
    const locale = resolveLocale(preferences);
    return {
        preferences,
        locale,
        dateOrder: resolveDateOrder(preferences.dateFormat),
        measurementUnits: resolveMeasurementUnits(preferences.measurementUnits, locale),
        hour12: preferences.clockFormat === '12h',
        version
    };
};

let currentSnapshot = createLocalizationSnapshot(DEFAULT_LOCALIZATION_PREFERENCES, snapshotVersion);

const collectChangedKeys = (previous: LocalizationSnapshot, next: LocalizationSnapshot): string[] => {
    const changedKeys: string[] = [];
    if (previous.preferences.language !== next.preferences.language) changedKeys.push('language');
    if (previous.preferences.clockFormat !== next.preferences.clockFormat) changedKeys.push('clock_format');
    if (previous.preferences.regionalLocale !== next.preferences.regionalLocale) changedKeys.push('regional_locale');
    if (previous.preferences.dateFormat !== next.preferences.dateFormat) changedKeys.push('date_format');
    if (previous.preferences.measurementUnits !== next.preferences.measurementUnits) changedKeys.push('measurement_units');
    if (previous.locale !== next.locale) changedKeys.push('locale');
    if (previous.dateOrder !== next.dateOrder) changedKeys.push('date_order');
    if (previous.measurementUnits !== next.measurementUnits) changedKeys.push('resolved_measurement_units');
    return changedKeys;
};

const getLocalizationSnapshot = (): LocalizationSnapshot => currentSnapshot;

const getResolvedLocalizationLocale = (): string => currentSnapshot.locale;

const setLocalizationSnapshot = (snapshot: LocalizationSnapshot, options: { dispatch?: boolean } = {}): LocalizationSnapshot => {
    const previous = currentSnapshot;
    const changedKeys = collectChangedKeys(previous, snapshot);
    if (changedKeys.length === 0) {
        return previous;
    }
    currentSnapshot = snapshot;
    snapshotVersion = snapshot.version;
    if (options.dispatch !== false) {
        const detail: LocalizationChangedDetail = { snapshot, changedKeys };
        dispatchCustomEvent(LOCALIZATION_CHANGED_EVENT, detail);
    }
    return snapshot;
};

const setLocalizationPreferencesSnapshot = (preferences: LocalizationPreferences, options: { dispatch?: boolean } = {}): LocalizationSnapshot => {
    const previous = currentSnapshot;
    const next = createLocalizationSnapshot(preferences, previous.version + 1);
    const changedKeys = collectChangedKeys(previous, next);
    if (changedKeys.length === 0) {
        return previous;
    }
    currentSnapshot = next;
    snapshotVersion = next.version;
    if (options.dispatch !== false) {
        const detail: LocalizationChangedDetail = { snapshot: next, changedKeys };
        dispatchCustomEvent(LOCALIZATION_CHANGED_EVENT, detail);
    }
    return next;
};

export { DEFAULT_LOCALIZATION_PREFERENCES, LOCALIZATION_CHANGED_EVENT, getLocalizationSnapshot, getResolvedLocalizationLocale, normalizeLocalizationPreferences, resolveBrowserCountryCode, setLocalizationPreferencesSnapshot, setLocalizationSnapshot };
