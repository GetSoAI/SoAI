/* SoAI - Dashboard page clock time widget [frontend/assets/ts/pages/dashboard/controllers/dashboardClockTimeWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { daysToMs, hoursToMs } from '@core/time/durations.ts';

type DashboardClockDisplayMode = 'analog' | 'digital';

const CLOCK_TICK_COUNT = 12;
const CLOCK_MAJOR_TICK_EVERY = 3;
const CLOCK_DEGREES_PER_SECOND = 6;
const CLOCK_DEGREES_PER_MINUTE = 6;
const CLOCK_DEGREES_PER_HOUR = 30;
const CLOCK_DATE_OPTIONS: Intl.DateTimeFormatOptions = { weekday: 'long', day: 'numeric', month: 'short' };
const CLOCK_TIME_WITH_SECONDS_OPTIONS: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
const CLOCK_TIME_WITHOUT_SECONDS_OPTIONS: Intl.DateTimeFormatOptions = { hour: '2-digit', minute: '2-digit' };
const CLOCK_WEEK_DAYS = 7;
const CLOCK_WEEKDAY_OPTIONS: Intl.DateTimeFormatOptions = { weekday: 'narrow' };
const DAY_MS = daysToMs(1);
const SWATCH_BIEL_MEAN_TIME_OFFSET_MS = hoursToMs(1);
const SWATCH_BEAT_DURATION_MS = 86_400;

const resolveClockTimeOptions = (clockSecondsEnabled: boolean): Intl.DateTimeFormatOptions => (clockSecondsEnabled ? CLOCK_TIME_WITH_SECONDS_OPTIONS : CLOCK_TIME_WITHOUT_SECONDS_OPTIONS);

const nextClockDisplayMode = (mode: DashboardClockDisplayMode): DashboardClockDisplayMode => (mode === 'analog' ? 'digital' : 'analog');

const buildDashboardClockClassName = (mode: DashboardClockDisplayMode, clockSecondsEnabled: boolean): string => {
    const secondsClassName = clockSecondsEnabled ? '' : ' dashboard-clock--seconds-disabled';
    return `dashboard-clock dashboard-clock--${mode}${secondsClassName}`;
};

const formatTimeZoneOffset = (date: Date): string => {
    const totalMinutes = -date.getTimezoneOffset();
    const sign = totalMinutes >= 0 ? '+' : '-';
    const absoluteMinutes = Math.abs(totalMinutes);
    const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, '0');
    const minutes = String(absoluteMinutes % 60).padStart(2, '0');
    return `UTC${sign}${hours}:${minutes}`;
};

const formatDayOfYearCounter = (date: Date): string => {
    const year = date.getFullYear();
    const todayUtc = Date.UTC(year, date.getMonth(), date.getDate());
    const yearStartUtc = Date.UTC(year, 0, 1);
    const nextYearStartUtc = Date.UTC(year + 1, 0, 1);
    const dayOfYear = Math.floor((todayUtc - yearStartUtc) / DAY_MS) + 1;
    const daysInYear = Math.floor((nextYearStartUtc - yearStartUtc) / DAY_MS);
    return `${i18n.formatNumber(dayOfYear)}/${i18n.formatNumber(daysInYear)}`;
};

const formatSwatchInternetTime = (date: Date): string => {
    const bielMeanTimeMs = date.getTime() + SWATCH_BIEL_MEAN_TIME_OFFSET_MS;
    const msSinceBielMidnight = ((bielMeanTimeMs % DAY_MS) + DAY_MS) % DAY_MS;
    const beat = Math.floor(msSinceBielMidnight / SWATCH_BEAT_DURATION_MS);
    return `@${String(beat).padStart(3, '0')}`;
};

const computeJulianDayNumber = (year: number, month: number, day: number): number => {
    const monthOffset = Math.floor((14 - month) / 12);
    const adjustedYear = year + 4800 - monthOffset;
    const adjustedMonth = month + 12 * monthOffset - 3;
    return day + Math.floor((153 * adjustedMonth + 2) / 5) + 365 * adjustedYear + Math.floor(adjustedYear / 4) - Math.floor(adjustedYear / 100) + Math.floor(adjustedYear / 400) - 32045;
};

const JULIAN_DATE_TO_MODIFIED_JULIAN_DATE_OFFSET = 2_400_000.5;

const formatModifiedJulianDate = (date: Date): string => {
    const julianDayNumber = computeJulianDayNumber(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
    const fractionOfDay = (date.getUTCHours() - 12) / 24 + date.getUTCMinutes() / 1_440 + (date.getUTCSeconds() + date.getUTCMilliseconds() / 1_000) / 86_400;
    const modifiedJulianDate = julianDayNumber + fractionOfDay - JULIAN_DATE_TO_MODIFIED_JULIAN_DATE_OFFSET;
    return modifiedJulianDate.toFixed(2);
};

export { CLOCK_DATE_OPTIONS, CLOCK_DEGREES_PER_HOUR, CLOCK_DEGREES_PER_MINUTE, CLOCK_DEGREES_PER_SECOND, CLOCK_MAJOR_TICK_EVERY, CLOCK_TICK_COUNT, CLOCK_WEEK_DAYS, CLOCK_WEEKDAY_OPTIONS, buildDashboardClockClassName, formatDayOfYearCounter, formatModifiedJulianDate, formatSwatchInternetTime, formatTimeZoneOffset, nextClockDisplayMode, resolveClockTimeOptions };
export type { DashboardClockDisplayMode };
