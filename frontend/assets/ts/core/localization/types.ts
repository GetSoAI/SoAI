/* SoAI - Shared localization contracts [frontend/assets/ts/core/localization/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type RegionalLocalePreference = 'auto' | 'browser' | 'en-US' | 'en-GB' | 'it-IT';
type DateFormatPreference = 'auto' | 'us' | 'eu' | 'iso';
type MeasurementUnitsPreference = 'auto' | 'metric' | 'imperial';
type ClockFormatPreference = '24h' | '12h';
type ResolvedMeasurementUnits = 'metric' | 'imperial';
type ResolvedDateOrder = 'locale' | 'us' | 'eu' | 'iso';

interface LocalizationPreferences {
    language: string;
    clockFormat: ClockFormatPreference;
    regionalLocale: RegionalLocalePreference;
    dateFormat: DateFormatPreference;
    measurementUnits: MeasurementUnitsPreference;
}

interface LocalizationSnapshot {
    preferences: LocalizationPreferences;
    locale: string;
    dateOrder: ResolvedDateOrder;
    measurementUnits: ResolvedMeasurementUnits;
    hour12: boolean;
    version: number;
}

interface LocalizationChangedDetail {
    snapshot: LocalizationSnapshot;
    changedKeys: string[];
}

export type { ClockFormatPreference, DateFormatPreference, LocalizationChangedDetail, LocalizationPreferences, LocalizationSnapshot, MeasurementUnitsPreference, RegionalLocalePreference, ResolvedDateOrder, ResolvedMeasurementUnits };
