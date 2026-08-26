/* SoAI - Chat feature weather widget formatters [frontend/assets/ts/features/chat/message/messageview/weatherWidgetFormatters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { fahrenheitToCelsius, formatLocalizedDate, formatLocalizedNumber, formatTemperature, formatWindSpeed, getLocalizationSnapshot, milesPerHourToKilometersPerHour } from '@core/localization/public.ts';
import { toIsoDate } from '@core/time/localCalendar.ts';
import type { ToolResultWeatherPayload, WeatherDailyPayload, WeatherHourlyPayload } from '@features/chat/message/messageview/toolResultWeatherPayload.ts';

type UnitSystem = ToolResultWeatherPayload['unitSystem'];

type CompassKey = 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w' | 'nw';

const COMPASS_KEYS: readonly CompassKey[] = ['n', 'ne', 'e', 'se', 's', 'sw', 'w', 'nw'];

const translateCompassKey = (key: CompassKey): string => {
    if (key === 'n') return i18n.t('chat.weather.compass.n');
    if (key === 'ne') return i18n.t('chat.weather.compass.ne');
    if (key === 'e') return i18n.t('chat.weather.compass.e');
    if (key === 'se') return i18n.t('chat.weather.compass.se');
    if (key === 's') return i18n.t('chat.weather.compass.s');
    if (key === 'sw') return i18n.t('chat.weather.compass.sw');
    if (key === 'w') return i18n.t('chat.weather.compass.w');
    return i18n.t('chat.weather.compass.nw');
};

const formatWeatherTemperature = (value: number, unitSystem: UnitSystem): string => {
    const celsius = unitSystem === 'imperial' ? fahrenheitToCelsius(value) : value;
    return formatTemperature(celsius, 0);
};

const formatWind = (value: number, unitSystem: UnitSystem): string => {
    const kilometersPerHour = unitSystem === 'imperial' ? milesPerHourToKilometersPerHour(value) : value;
    return formatWindSpeed(kilometersPerHour, 0);
};

const formatWholePercent = (value: number): string => formatLocalizedNumber(Math.round(value) / 100, { style: 'percent', maximumFractionDigits: 0 });

const formatWeatherForecastDayCount = (dayCount: number): string => i18n.t('common.time.units.day.short', { count: formatLocalizedNumber(dayCount, { maximumFractionDigits: 0 }) });

const formatWeatherMeasurementUnitsLabel = (): string => {
    const units = getLocalizationSnapshot().measurementUnits;
    return units === 'imperial' ? i18n.t('chat.weather.units.imperial') : i18n.t('chat.weather.units.metric');
};

const formatCompass = (degrees: number): string => {
    if (!Number.isFinite(degrees)) {
        return '';
    }
    const normalized = ((degrees % 360) + 360) % 360;
    const index = Math.round(normalized / 45) % 8;
    const key = COMPASS_KEYS[index];
    if (key === undefined) {
        return '';
    }
    return translateCompassKey(key);
};

const formatWindWithDirection = (speed: number, direction: number, unitSystem: UnitSystem): string => {
    const compass = formatCompass(direction);
    const speedText = formatWind(speed, unitSystem);
    return compass === '' ? speedText : `${compass} ${speedText}`;
};

const formatDayLabel = (dateValue: string): string => {
    const timestamp = new Date(`${dateValue}T12:00:00`).getTime();
    if (!Number.isFinite(timestamp)) {
        return dateValue;
    }
    return formatLocalizedDate(new Date(timestamp), { weekday: 'short' });
};

const formatHourLabel = (timeValue: string): string => {
    const timestamp = new Date(timeValue).getTime();
    if (!Number.isFinite(timestamp)) {
        return timeValue;
    }
    return formatLocalizedDate(new Date(timestamp), { hour: 'numeric' });
};

const formatDayNumber = (dateValue: string): string => {
    const timestamp = new Date(`${dateValue}T12:00:00`).getTime();
    if (!Number.isFinite(timestamp)) {
        return '';
    }
    return formatLocalizedDate(new Date(timestamp), { day: 'numeric', month: 'short' });
};

const formatDailyRange = (entries: readonly WeatherDailyPayload[]): string => {
    if (entries.length === 0) {
        return '';
    }
    const first = entries[0];
    const last = entries[entries.length - 1];
    if (first === undefined || last === undefined) {
        return '';
    }
    const start = new Date(`${first.date}T12:00:00`);
    const end = new Date(`${last.date}T12:00:00`);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
        return '';
    }
    const startLabel = formatLocalizedDate(start, { month: 'short', day: 'numeric', weekday: 'short' });
    const endLabel = formatLocalizedDate(end, { month: 'short', day: 'numeric', weekday: 'short' });
    return entries.length === 1 ? startLabel : `${startLabel} - ${endLabel}`;
};

const formatHourlyRange = (entries: readonly WeatherHourlyPayload[]): string => {
    if (entries.length === 0) {
        return '';
    }
    const first = entries[0];
    const last = entries[entries.length - 1];
    if (first === undefined || last === undefined) {
        return '';
    }
    const start = new Date(first.time);
    const end = new Date(last.time);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
        return '';
    }
    const startLabel = formatLocalizedDate(start, { weekday: 'short', hour: 'numeric' });
    const endLabel = formatLocalizedDate(end, { weekday: 'short', hour: 'numeric' });
    return entries.length === 1 ? startLabel : `${startLabel} - ${endLabel}`;
};

const normalizeConditionAttribute = (conditionType: string): string => conditionType.trim().toLowerCase();

const resolveLocalIsoDate = (): string => toIsoDate(new Date());

const MIN_VISIBLE_PRECIP_PERCENT = 5;

export { COMPASS_KEYS, MIN_VISIBLE_PRECIP_PERCENT, formatCompass, formatDailyRange, formatDayLabel, formatDayNumber, formatHourLabel, formatHourlyRange, formatWeatherForecastDayCount, formatWeatherMeasurementUnitsLabel, formatWeatherTemperature, formatWholePercent, formatWind, formatWindWithDirection, normalizeConditionAttribute, resolveLocalIsoDate };
export type { UnitSystem };
