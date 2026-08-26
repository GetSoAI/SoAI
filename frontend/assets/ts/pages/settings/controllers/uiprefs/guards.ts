/* SoAI - Settings UI preference value guards [frontend/assets/ts/pages/settings/controllers/uiprefs/guards.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isAnimationSpeed, type AnimationSpeed } from '@core/animations/speed.ts';
import { isDateFormatPreference, isMeasurementUnitsPreference, isRegionalLocalePreference, type DateFormatPreference, type MeasurementUnitsPreference, type RegionalLocalePreference } from '@core/localization/public.ts';
import { readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readRequiredBooleanValue, readRequiredEnumValue, readRequiredNonEmptyStringValue, readRequiredStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isInterfaceScalePercent, type InterfaceScalePercent } from '@core/layout/interfaceScale.ts';
import { isAnimationType, isChartColorModeType, isThemeType } from '@core/storage/guards.ts';
import type { AnimationType, ChartColorModeType, ThemeType } from '@core/storage/types.ts';

const requireUiPrefsLanguage = (value: JsonValue | null | undefined): string => readRequiredNonEmptyStringValue(value, 'uiPrefs.language');

type ClockFormatValue = '12h' | '24h';

const CLOCK_FORMAT_VALUES: readonly ClockFormatValue[] = ['12h', '24h'];

const requireUiPrefsClockFormat = (value: JsonValue | null | undefined): ClockFormatValue => readRequiredEnumValue(value, 'uiPrefs.clockFormat', CLOCK_FORMAT_VALUES);

const requireUiPrefsRegionalLocale = (value: JsonValue | null | undefined): RegionalLocalePreference => {
    if (!isRegionalLocalePreference(value)) {
        throw new TypeError('uiPrefs.regionalLocale must be a valid regional locale preference');
    }
    return value;
};

const requireUiPrefsDateFormat = (value: JsonValue | null | undefined): DateFormatPreference => {
    if (!isDateFormatPreference(value)) {
        throw new TypeError('uiPrefs.dateFormat must be a valid date format preference');
    }
    return value;
};

const requireUiPrefsMeasurementUnits = (value: JsonValue | null | undefined): MeasurementUnitsPreference => {
    if (!isMeasurementUnitsPreference(value)) {
        throw new TypeError('uiPrefs.measurementUnits must be a valid measurement units preference');
    }
    return value;
};

const requireUiPrefsNotificationDuration = (value: JsonValue | null | undefined): number => readRequiredFiniteNumberValue(value, 'uiPrefs.notificationDuration');

const requireUiPrefsWallpaperOverlay = (value: JsonValue | null | undefined): number => readRequiredFiniteNumberValue(value, 'uiPrefs.wallpaperOverlay');

const requireUiPrefsInterfaceScale = (value: JsonValue | null | undefined): InterfaceScalePercent => {
    if (!isInterfaceScalePercent(value)) {
        throw new TypeError('uiPrefs.interfaceScale must be one of the supported percentage steps');
    }
    return value;
};

const requireUiPrefsSolidBackground = (value: JsonValue | null | undefined): string | null => {
    if (value === null) {
        return null;
    }
    return readRequiredStringValue(value, 'uiPrefs.solidBackground');
};

const requireUiPrefsBoolean = (value: JsonValue | null | undefined, label: string): boolean => readRequiredBooleanValue(value, label);

const requireUiPrefsNullableString = (value: JsonValue | null | undefined, label: string): string | null => {
    if (value === null || value === undefined) {
        return null;
    }
    return readRequiredStringValue(value, label);
};

const requireUiPrefsNonEmptyString = (value: JsonValue | null | undefined, label: string): string => readRequiredNonEmptyStringValue(value, label);

const requireUiPrefsAnimationSpeed = (value: JsonValue | null | undefined): AnimationSpeed => {
    if (!isAnimationSpeed(value)) {
        throw new TypeError('uiPrefs.animationSpeed must be a valid animation speed');
    }
    return value;
};

const requireUiPrefsTheme = (value: JsonValue | null | undefined): ThemeType => {
    if (!isThemeType(value)) throw new TypeError('uiPrefs.theme must be a valid theme');
    return value;
};

const requireUiPrefsAnimation = (value: JsonValue | null | undefined, label: string): AnimationType => {
    if (!isAnimationType(value)) throw new TypeError(`${label} must be a valid animation type`);
    return value;
};

const requireUiPrefsChartColorMode = (value: JsonValue | null | undefined): ChartColorModeType => {
    if (!isChartColorModeType(value)) throw new TypeError('uiPrefs.chartColorMode must be a valid chart color mode');
    return value;
};

export { requireUiPrefsAnimation, requireUiPrefsAnimationSpeed, requireUiPrefsBoolean, requireUiPrefsChartColorMode, requireUiPrefsClockFormat, requireUiPrefsDateFormat, requireUiPrefsInterfaceScale, requireUiPrefsLanguage, requireUiPrefsMeasurementUnits, requireUiPrefsNonEmptyString, requireUiPrefsNotificationDuration, requireUiPrefsNullableString, requireUiPrefsRegionalLocale, requireUiPrefsSolidBackground, requireUiPrefsTheme, requireUiPrefsWallpaperOverlay };
