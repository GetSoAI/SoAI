/* SoAI - Shared localization public surface [frontend/assets/ts/core/localization/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { isClockFormatPreference, isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference } from '@core/localization/guards.ts';
export { DEFAULT_LOCALIZATION_PREFERENCES, LOCALIZATION_CHANGED_EVENT, getLocalizationSnapshot, getResolvedLocalizationLocale, normalizeLocalizationPreferences, resolveBrowserCountryCode, setLocalizationPreferencesSnapshot, setLocalizationSnapshot } from '@core/localization/runtime.ts';
export { formatLocalizedDate, formatLocalizedDateParts, formatLocalizedRelativeTime } from '@core/localization/dateTimeFormatting.ts';
export { formatInvariantCompactNumber, formatInvariantNumber, formatLocalizedNumber } from '@core/localization/numberFormatting.ts';
export { celsiusToFahrenheit, fahrenheitToCelsius, formatByteSize, formatNetworkSpeedMbps, formatPower, formatTemperature, formatWindSpeed, kilometersPerHourToMilesPerHour, milesPerHourToKilometersPerHour, wattsToBtuPerHour } from '@core/localization/unitFormatting.ts';
export type { ClockFormatPreference, DateFormatPreference, LocalizationChangedDetail, LocalizationPreferences, LocalizationSnapshot, MeasurementUnitsPreference, RegionalLocalePreference, ResolvedDateOrder, ResolvedMeasurementUnits } from '@core/localization/types.ts';
