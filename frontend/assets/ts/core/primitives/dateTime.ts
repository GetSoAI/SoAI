/* SoAI - Shared primitives date time [frontend/assets/ts/core/primitives/dateTime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatLocalizedDate, formatLocalizedRelativeTime } from '@core/localization/public.ts';
import { resolveLocalCalendarBucket } from '@core/time/localCalendar.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';

const buildDateTimeOptions = (includeSeconds: boolean = true): Intl.DateTimeFormatOptions => {
    const options: Intl.DateTimeFormatOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    if (includeSeconds) options.second = '2-digit';
    return options;
};

const DATE_TIME_MINUTE_OPTIONS: Readonly<Intl.DateTimeFormatOptions> = Object.freeze({
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
});

const DATE_TIME_SECOND_OPTIONS: Readonly<Intl.DateTimeFormatOptions> = Object.freeze({
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
});

const TIME_SECOND_OPTIONS: Readonly<Intl.DateTimeFormatOptions> = Object.freeze({
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
});

export const formatDateTimeWithOptions = (date: Date | string | number, options: Intl.DateTimeFormatOptions): string => {
    const resolved = date instanceof Date ? date : new Date(date);
    return formatLocalizedDate(resolved, options);
};

export const formatDateTime = (date: Date | string | number, includeSeconds: boolean = true): string => {
    return formatDateTimeWithOptions(date, buildDateTimeOptions(includeSeconds));
};

export const formatRuntimeDateTimeOrEmpty = (value: string | number | Date | null | undefined, includeSeconds: boolean = true): string => {
    if (isString(value) || isFiniteNumber(value) || value instanceof Date) {
        return formatDateTime(value, includeSeconds);
    }
    return '';
};

export const formatNullableEpochMsWithFallback = (timestampMs: number | null | undefined, fallback: string, options: Intl.DateTimeFormatOptions = {}): string => {
    if (timestampMs === null || timestampMs === undefined) {
        return fallback;
    }
    if (!isFiniteNumber(timestampMs)) {
        throw new Error('Timestamp must be numeric');
    }
    return formatDateTimeWithOptions(timestampMs, options);
};

export const formatPositiveEpochMsWithFallback = (timestampMs: number | null | undefined, fallback: string, options: Intl.DateTimeFormatOptions = {}): string => {
    if (!isFiniteNumber(timestampMs) || timestampMs <= 0) {
        return fallback;
    }
    return formatDateTimeWithOptions(timestampMs, options);
};

export const formatNullableEpochMsMinuteWithFallback = (timestampMs: number | null | undefined, fallback: string): string => {
    return formatNullableEpochMsWithFallback(timestampMs, fallback, { ...DATE_TIME_MINUTE_OPTIONS });
};

export const formatPositiveEpochMsMinuteWithFallback = (timestampMs: number | null | undefined, fallback: string): string => {
    return formatPositiveEpochMsWithFallback(timestampMs, fallback, { ...DATE_TIME_MINUTE_OPTIONS });
};

export const formatPositiveEpochMsSecondWithFallback = (timestampMs: number | null | undefined, fallback: string): string => {
    return formatPositiveEpochMsWithFallback(timestampMs, fallback, { ...DATE_TIME_SECOND_OPTIONS });
};

export const formatNullableEpochMsSecondWithFallback = (timestampMs: number | null | undefined, fallback: string): string => {
    return formatNullableEpochMsWithFallback(timestampMs, fallback, { ...DATE_TIME_SECOND_OPTIONS });
};

export const formatNullableEpochMsSecondOrNull = (timestampMs: number | null | undefined): string | null => {
    if (!isFiniteNumber(timestampMs)) {
        return null;
    }
    const date = new Date(timestampMs);
    return Number.isNaN(date.getTime()) ? null : formatDateTimeSecond(date);
};

export const formatDateTimeMinute = (date: Date | string | number): string => {
    return formatDateTimeWithOptions(date, { ...DATE_TIME_MINUTE_OPTIONS });
};

export const formatDateTimeSecond = (date: Date | string | number): string => {
    return formatDateTimeWithOptions(date, { ...DATE_TIME_SECOND_OPTIONS });
};

export const formatCalendarLabelWithFullDate = (date: Date | string | number, nowMs: number, includeSeconds: boolean = true): string => {
    const resolved = date instanceof Date ? date : new Date(date);
    if (!isFiniteNumber(resolved.getTime())) {
        throw new Error('Calendar date label requires a valid timestamp');
    }
    const fullDate = includeSeconds ? formatDateTimeSecond(resolved) : formatDateTimeMinute(resolved);
    const bucket = resolveLocalCalendarBucket(resolved, new Date(nowMs));
    if (bucket.type === 'today') {
        return `${i18n.t('common.today')}, ${fullDate}`;
    }
    if (bucket.type === 'yesterday') {
        return `${i18n.t('common.yesterday')}, ${fullDate}`;
    }
    return fullDate;
};

export const formatTimeSecond = (date: Date | string | number): string => {
    return formatDateTimeWithOptions(date, { ...TIME_SECOND_OPTIONS });
};

export const formatEpochMsTimeSecondOrEmpty = (timestampMs: number | null | undefined): string => {
    if (!isFiniteNumber(timestampMs)) {
        return '';
    }
    const date = new Date(timestampMs);
    return Number.isNaN(date.getTime()) ? '' : formatTimeSecond(date);
};

export const formatRelativeTime = (date: Date | string | number, nowMs: number): string => {
    const ts = new Date(date).getTime();
    if (!isFiniteNumber(ts)) throw new Error('Relative time requires a valid timestamp');
    const diff = Math.floor((nowMs - ts) / 1000);
    if (Math.abs(diff) < 60) return i18n.t('common.time.relative.justNow');
    try {
        if (Math.abs(diff) < 3600) return formatLocalizedRelativeTime(-Math.round(diff / 60), 'minute');
        if (Math.abs(diff) < 86400) return formatLocalizedRelativeTime(-Math.round(diff / 3600), 'hour');
        if (Math.abs(diff) < 604800) return formatLocalizedRelativeTime(-Math.round(diff / 86400), 'day');
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('DateTime', 'Formatting relative time failed', runtimeError);
    }
    return formatDateTime(date, false);
};
