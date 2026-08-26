/* SoAI - Shared time local calendar [frontend/assets/ts/core/time/localCalendar.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { daysToMs } from '@core/time/durations.ts';
import { parseLocalDateTimeParts } from '@core/time/localDateTime.ts';

const DAY_MS = daysToMs(1);

const pad2 = (value: number): string => String(value).padStart(2, '0');

const createLocalDate = (year: number, monthIndex: number, day: number, hour: number, minute: number): Date => {
    const date = new Date(0);
    date.setFullYear(year, monthIndex, day);
    date.setHours(hour, minute, 0, 0);
    return date;
};

const toStartLocal = (date: Date): string => {
    const year = date.getFullYear();
    const month = pad2(date.getMonth() + 1);
    const day = pad2(date.getDate());
    const hour = pad2(date.getHours());
    const minute = pad2(date.getMinutes());
    return `${year}-${month}-${day}T${hour}:${minute}`;
};

const parseStartLocalToDate = (value: string): Date | null => {
    const parts = parseLocalDateTimeParts(value);
    if (!parts) {
        return null;
    }
    const date = createLocalDate(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
    if (date.getFullYear() !== parts.year || date.getMonth() !== parts.month - 1 || date.getDate() !== parts.day || date.getHours() !== parts.hour || date.getMinutes() !== parts.minute) {
        return null;
    }
    return Number.isFinite(date.getTime()) ? date : null;
};

const toIsoDate = (date: Date): string => {
    const year = date.getFullYear();
    const month = pad2(date.getMonth() + 1);
    const day = pad2(date.getDate());
    return `${year}-${month}-${day}`;
};

const parseIsoDateToUtcMs = (iso: string): number | null => {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim());
    if (!match) {
        return null;
    }
    const year = Number(match[1] || '');
    const month = Number(match[2] || '');
    const day = Number(match[3] || '');
    if (!Number.isFinite(year) || !Number.isFinite(month) || !Number.isFinite(day)) {
        return null;
    }
    if (month < 1 || month > 12) {
        return null;
    }
    if (day < 1 || day > 31) {
        return null;
    }
    const date = createLocalDate(year, month - 1, day, 0, 0);
    if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
        return null;
    }
    return date.getTime();
};

const requireIsoDateToUtcMs = (iso: string, label: string): number => {
    const utcMs = parseIsoDateToUtcMs(iso);
    if (utcMs === null) {
        throw new Error(`${label} must be an ISO date (YYYY-MM-DD)`);
    }
    return utcMs;
};

const startOfDay = (date: Date): Date => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0);

const isSameDay = (firstValue: Date, secondValue: Date): boolean => firstValue.getFullYear() === secondValue.getFullYear() && firstValue.getMonth() === secondValue.getMonth() && firstValue.getDate() === secondValue.getDate();

type LocalCalendarBucketType = 'today' | 'yesterday' | 'recent' | 'older';

interface LocalCalendarBucket {
    type: LocalCalendarBucketType;
    calendarDaysAgo: number;
    timeMinute: string;
    timeSecond: string;
}

const formatLocalTimeMinute = (date: Date): string => `${pad2(date.getHours())}:${pad2(date.getMinutes())}`;

const formatLocalTimeSecond = (date: Date): string => `${formatLocalTimeMinute(date)}:${pad2(date.getSeconds())}`;

const resolveLocalCalendarBucket = (date: Date, now: Date, options: { futureAsToday?: boolean | undefined } = {}): LocalCalendarBucket => {
    if (!Number.isFinite(date.getTime()) || !Number.isFinite(now.getTime())) {
        throw new Error('Local calendar bucket requires valid dates');
    }
    const todayStart = startOfDay(now).getTime();
    const yesterdayStart = todayStart - DAY_MS;
    const dateStart = startOfDay(date).getTime();
    const calendarDaysAgo = Math.floor((todayStart - dateStart) / DAY_MS);
    const isToday = options.futureAsToday === true ? date.getTime() >= todayStart : dateStart === todayStart;
    const type: LocalCalendarBucketType = isToday ? 'today' : dateStart === yesterdayStart ? 'yesterday' : calendarDaysAgo < 7 ? 'recent' : 'older';
    return {
        type,
        calendarDaysAgo,
        timeMinute: formatLocalTimeMinute(date),
        timeSecond: formatLocalTimeSecond(date)
    };
};

const resolveWeekStartsOnSunday = (locale: string): boolean => {
    const normalized = locale.trim().toLowerCase();
    return normalized === 'en-us' || normalized.startsWith('en-us-');
};

const startOfWeek = (date: Date, weekStartsOnSunday: boolean): Date => {
    const dayIndex = date.getDay();
    const delta = weekStartsOnSunday ? -dayIndex : -((dayIndex + 6) % 7);
    const nextDate = startOfDay(date);
    nextDate.setDate(nextDate.getDate() + delta);
    return nextDate;
};

const addDays = (date: Date, days: number): Date => {
    const nextDate = new Date(date.getTime());
    nextDate.setDate(nextDate.getDate() + days);
    return nextDate;
};

const buildMonthGrid = (focus: Date, weekStartsOnSunday: boolean): Date[] => {
    const firstOfMonth = new Date(focus.getFullYear(), focus.getMonth(), 1, 0, 0, 0, 0);
    const gridStart = startOfWeek(firstOfMonth, weekStartsOnSunday);
    return Array.from({ length: 42 }).map((_unusedValue, index) => addDays(gridStart, index));
};

const buildWeekDays = (focus: Date, weekStartsOnSunday: boolean): Date[] => {
    const weekStart = startOfWeek(focus, weekStartsOnSunday);
    return Array.from({ length: 7 }).map((_unusedValue, index) => addDays(weekStart, index));
};

const getIsoWeekNumber = (date: Date): number => {
    const utc = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate(), 0, 0, 0, 0));
    const day = utc.getUTCDay() || 7;
    utc.setUTCDate(utc.getUTCDate() + 4 - day);
    const yearStart = new Date(Date.UTC(utc.getUTCFullYear(), 0, 1, 0, 0, 0, 0));
    const diffDays = Math.floor((utc.getTime() - yearStart.getTime()) / DAY_MS) + 1;
    return Math.ceil(diffDays / 7);
};

const getLocalWeekNumber = (date: Date, weekStartsOnSunday: boolean): number => {
    const anchor = startOfDay(date);
    const yearStart = startOfDay(new Date(anchor.getFullYear(), 0, 1));
    const yearWeekStart = startOfWeek(yearStart, weekStartsOnSunday);
    const anchorWeekStart = startOfWeek(anchor, weekStartsOnSunday);
    const diff = anchorWeekStart.getTime() - yearWeekStart.getTime();
    const diffWeeks = Math.floor(diff / daysToMs(7));
    return diffWeeks + 1;
};

const getWeekNumberForWindow = (weekStart: Date, weekStartsOnSunday: boolean, numbering: 'iso' | 'local'): number => {
    const anchor = numbering === 'iso' && weekStartsOnSunday ? addDays(weekStart, 1) : weekStart;
    return numbering === 'iso' ? getIsoWeekNumber(anchor) : getLocalWeekNumber(anchor, weekStartsOnSunday);
};

type FilenameTimestampPrecision = 'milliseconds' | 'seconds';

const formatIsoTimestampForFilename = (date: Date = new Date(), precision: FilenameTimestampPrecision = 'milliseconds'): string => {
    const iso = precision === 'seconds' ? date.toISOString().slice(0, 19) : date.toISOString();
    return iso.replace(/[:.]/g, '-');
};

export { addDays, buildMonthGrid, buildWeekDays, formatIsoTimestampForFilename, getIsoWeekNumber, getLocalWeekNumber, getWeekNumberForWindow, isSameDay, pad2, parseIsoDateToUtcMs, parseStartLocalToDate, requireIsoDateToUtcMs, resolveLocalCalendarBucket, resolveWeekStartsOnSunday, startOfDay, startOfWeek, toIsoDate, toStartLocal };
export type { FilenameTimestampPrecision, LocalCalendarBucket, LocalCalendarBucketType };
