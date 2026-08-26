/* SoAI - Charts feature time formatting [frontend/assets/ts/features/charts/component/data/timeFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { formatLocalizedDate } from '@core/localization/public.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { ChartTimestampFormatInput, ChartTimestampFormatter, TimestampFormatConfig } from '@features/charts/chartTypes.ts';
import { isFin, MINUTE_MS, SECOND_MS, YEAR_MS } from '@features/charts/component/chartComponentStatics.ts';
import type { VisibleRange } from '@features/charts/component/chartComponentTypes.ts';
import { logWarn } from '@features/charts/component/logger.ts';

const isTimestampFormatter = (value: ChartTimestampFormatInput): value is ChartTimestampFormatter => typeof value === 'function';

interface TimeFormattingHost {
    timestampFormatConfig: TimestampFormatConfig;
    visibleRange: VisibleRange;
    timestamps: Float64Array;
    dataLength: number;
}

const normalizeTimestampFormat = (option: ChartTimestampFormatInput): TimestampFormatConfig => {
    const response: TimestampFormatConfig = { mode: 'auto', formatter: null, timeZone: null };
    if (isTimestampFormatter(option)) {
        response.mode = 'custom';
        response.formatter = option;
    } else if (isString(option)) {
        const currentTime = option.trim().toLowerCase();
        if (currentTime === 'utc' || currentTime === 'iso') response.timeZone = 'UTC';
        if (currentTime === 'iso') response.mode = 'iso';
        else if (currentTime && !['auto', 'local', 'utc'].includes(currentTime)) response.timeZone = option.trim();
    } else if (isObject(option)) {
        const optionObject = option;
        const formatValue = optionObject['format'];
        const formatterValue = optionObject['formatter'];
        const objectFormatter = isTimestampFormatter(formatValue) ? formatValue : isTimestampFormatter(formatterValue) ? formatterValue : null;
        if (objectFormatter) {
            response.mode = 'custom';
            response.formatter = objectFormatter;
        }
        const timeZoneValue = optionObject['timeZone'];
        if (isString(timeZoneValue) && timeZoneValue.trim()) response.timeZone = timeZoneValue.trim();
        const match = String(optionObject['mode']).trim().toLowerCase();
        if (match === 'iso') response.mode = 'iso';
        else if (match === 'custom' && objectFormatter) response.mode = 'custom';
        else if (match === 'auto') response.mode = 'auto';
    }
    return response;
};

const finalizeDateTimeOptions = (chart: TimeFormattingHost, base: Intl.DateTimeFormatOptions = {}): Intl.DateTimeFormatOptions => {
    const objectValue: Intl.DateTimeFormatOptions = { ...base };
    if (chart.timestampFormatConfig?.timeZone) objectValue.timeZone = chart.timestampFormatConfig.timeZone;
    return objectValue;
};

const formatDateTime = (chart: TimeFormattingHost, ts: number, base: Intl.DateTimeFormatOptions = {}): string => {
    if (!isFin(ts)) return '';
    const options = finalizeDateTimeOptions(chart, base);
    try {
        return formatLocalizedDate(new Date(ts), options);
    } catch (error) {
        const exception = ensureError(error);
        logWarn('Date formatter execution failed', { message: exception.message, options: options });
    }
    const dataValue = new Date(ts);
    return isFin(dataValue.getTime()) ? dataValue.toISOString() : `${ts}`;
};

const resolveAxisFormat = (ms: number): { options: Intl.DateTimeFormatOptions } => {
    const stringValue = ms > 0 ? ms : 0;
    const objectValue: Intl.DateTimeFormatOptions = {};
    if (stringValue >= YEAR_MS) {
        objectValue.year = 'numeric';
        objectValue.month = 'short';
    } else if (stringValue >= 2 * 7 * 24 * 60 * 60 * 1000) {
        objectValue.month = 'short';
        objectValue.day = 'numeric';
    } else if (stringValue >= 2 * 24 * 60 * 60 * 1000) {
        objectValue.month = 'short';
        objectValue.day = 'numeric';
        objectValue.hour = '2-digit';
        objectValue.minute = '2-digit';
    } else if (stringValue >= 60 * 60 * 1000) {
        objectValue.hour = '2-digit';
        objectValue.minute = '2-digit';
    } else if (stringValue >= MINUTE_MS) {
        objectValue.hour = '2-digit';
        objectValue.minute = '2-digit';
        objectValue.second = '2-digit';
    } else if (stringValue > 0) {
        objectValue.minute = '2-digit';
        objectValue.second = '2-digit';
        objectValue.fractionalSecondDigits = stringValue <= SECOND_MS ? 3 : 2;
    } else {
        objectValue.hour = '2-digit';
        objectValue.minute = '2-digit';
        objectValue.second = '2-digit';
    }
    return { options: objectValue };
};

const getVisibleTimeWindow = (chart: TimeFormattingHost): { startTs: number; endTs: number; span: number } | null => {
    if (!chart.timestamps || chart.dataLength === 0) return null;
    const { start, displayCount, offsetFraction } = chart.visibleRange;
    const startIndex = clampNumber(start, 0, chart.dataLength - 1);
    const baseStart = chart.timestamps[startIndex] ?? Number.NaN;
    if (!isFin(baseStart)) return null;
    const baseStartNumber: number = baseStart;
    const nextIndex = Math.min(chart.dataLength - 1, startIndex + 1);
    const nextTimestamp = chart.timestamps[nextIndex] ?? Number.NaN;
    const startTs = offsetFraction > 0 && nextIndex !== startIndex && isFin(nextTimestamp) ? baseStartNumber + (nextTimestamp - baseStartNumber) * offsetFraction : baseStartNumber;

    const endIndex = Math.min(chart.dataLength - 1, start + Math.max(1, displayCount) - 1);
    const endTimestamp = chart.timestamps[endIndex] ?? Number.NaN;
    if (!isFin(endTimestamp)) return null;
    return { startTs, endTs: endTimestamp, span: Math.max(1, endTimestamp - startTs || 0) };
};

const getVisibleTimeSpan = (chart: TimeFormattingHost): number => {
    const width = getVisibleTimeWindow(chart);
    if (width?.span) return width.span;
    if (!chart.timestamps || chart.dataLength === 0) return 0;
    const { start: stringValue, end: error } = chart.visibleRange;
    const first = clampNumber(stringValue, 0, chart.dataLength - 1);
    const last = clampNumber((error || 0) - 1, first, chart.dataLength - 1);
    if (last <= first) return 0;
    const st = chart.timestamps[first] ?? Number.NaN;
    const et = chart.timestamps[last] ?? Number.NaN;
    return isFin(st) && isFin(et) ? Math.max(0, et - st) : 0;
};

interface TimestampHost extends TimeFormattingHost {
    formatDateTime: (ts: number, base?: Intl.DateTimeFormatOptions) => string;
    resolveAxisFormat: (ms: number) => { options: Intl.DateTimeFormatOptions };
}

const formatTimestamp = (chart: TimestampHost, timestamp: number, mode: ChartTimestampFormatter | string | null | undefined = 'auto'): string => {
    if (!isFin(timestamp)) return '';
    const fmt = mode;

    if (isFunction(fmt)) {
        try {
            const formatted = fmt(timestamp, { context: 'mode', chart });
            if (typeof formatted !== 'string') {
                throw new Error('Custom timestamp formatter must return a string');
            }
            return formatted;
        } catch (error) {
            const message = ensureError(error).message;
            logWarn('Custom timestamp formatter threw', { message });
        }
    }

    const fmtString = isString(fmt) ? fmt : 'auto';
    const { mode: configMode, formatter } = chart.timestampFormatConfig;
    if (configMode === 'custom' && isFunction(formatter) && fmtString === 'auto') {
        try {
            const formatted = formatter(timestamp, { context: 'default', chart });
            if (typeof formatted !== 'string') {
                throw new Error('timestampFormat formatter must return a string');
            }
            return formatted;
        } catch (error) {
            const message = ensureError(error).message;
            logWarn('timestampFormat custom formatter failed', { message });
        }
    }

    if (configMode === 'iso' || fmtString === 'iso') return new Date(timestamp).toISOString();
    if (fmtString === 'full')
        return chart.formatDateTime(timestamp, {
            year: 'numeric',
            month: 'short',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    const ms = getVisibleTimeSpan(chart);
    const { options } = chart.resolveAxisFormat(ms);
    if (ms <= MINUTE_MS && !options.second) options.second = '2-digit';
    return chart.formatDateTime(timestamp, options);
};

const formatAxisTimestamp = (chart: TimestampHost, ts: number, ms: number = getVisibleTimeSpan(chart)): string => {
    if (!isFin(ts)) return '';
    const { mode, formatter } = chart.timestampFormatConfig;
    if (mode === 'custom' && isFunction(formatter))
        try {
            return formatter(ts, { context: 'axis', spanMs: ms, chart }) ?? '';
        } catch (error) {
            const message = ensureError(error).message;
            logWarn('Custom axis timestamp formatter failed', { message });
        }
    return mode === 'iso' ? new Date(ts).toISOString() : chart.formatDateTime(ts, chart.resolveAxisFormat(ms).options);
};

interface DetailedHost extends TimestampHost {
    visibleRange: VisibleRange;
}

const formatDetailedTimestamp = (chart: DetailedHost, timestamp: number, options: JsonObject | null | undefined = null): string => {
    if (!isFin(timestamp)) return '';
    const includeSecondsRaw = isObject(options) ? options['includeSeconds'] : undefined;
    const includeMillisecondsRaw = isObject(options) ? options['includeMilliseconds'] : undefined;
    const includeSeconds = typeof includeSecondsRaw === 'boolean' ? includeSecondsRaw : false;
    const includeMilliseconds = typeof includeMillisecondsRaw === 'boolean' ? includeMillisecondsRaw : false;

    const { mode, formatter } = chart.timestampFormatConfig;
    if (mode === 'custom' && isFunction(formatter)) {
        try {
            const formatted = formatter(timestamp, {
                context: 'detail',
                includeSeconds,
                includeMilliseconds,
                chart
            });
            if (typeof formatted !== 'string') {
                throw new Error('Custom detailed timestamp formatter must return a string');
            }
            return formatted;
        } catch (error) {
            const message = ensureError(error).message;
            logWarn('Custom detailed timestamp formatter failed', { message });
        }
    }
    if (mode === 'iso') return new Date(timestamp).toISOString();
    const ms = getVisibleTimeSpan(chart);
    const ss = includeSeconds || ms <= MINUTE_MS;
    const objectValue: Record<string, string | boolean | number | undefined> = {
        hour: '2-digit',
        minute: '2-digit'
    };
    if (ss) {
        objectValue['second'] = '2-digit';
        if (includeMilliseconds || ms <= 5 * SECOND_MS) objectValue['fractionalSecondDigits'] = ms <= SECOND_MS ? 3 : 2;
    }
    const dataValue: Record<string, string | undefined> = { month: 'short', day: '2-digit' };
    if (ms >= YEAR_MS) dataValue['year'] = 'numeric';
    else {
        const { start, end } = chart.visibleRange;
        if (end - 1 > start) {
            const redChannel = chart.timestamps[clampNumber(start, 0, chart.dataLength - 1)] ?? Number.NaN;
            if (isFin(redChannel) && new Date(redChannel).getFullYear() !== new Date(timestamp).getFullYear()) dataValue['year'] = 'numeric';
        }
    }
    return `${chart.formatDateTime(timestamp, objectValue)} • ${chart.formatDateTime(timestamp, dataValue)}`;
};

export { finalizeDateTimeOptions, formatAxisTimestamp, formatDateTime, formatDetailedTimestamp, formatTimestamp, getVisibleTimeSpan, getVisibleTimeWindow, normalizeTimestampFormat, resolveAxisFormat };
