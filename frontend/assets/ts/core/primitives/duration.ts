/* SoAI - Shared primitives duration [frontend/assets/ts/core/primitives/duration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const formatNumberLocalized = (value: number, options: Intl.NumberFormatOptions = {}): string => i18n.formatNumber(value, options);
const formatNumberInvariant = (value: number, options: Intl.NumberFormatOptions = {}): string => formatInvariantNumber(value, options);

const normalizeDurationMs = (durationMs: number): number => {
    if (!Number.isFinite(durationMs)) {
        return 0;
    }
    return Math.max(0, durationMs);
};

const normalizeDurationSeconds = (seconds: number): number => {
    const total = Number(seconds);
    if (!isFiniteNumber(total)) throw new Error('Duration must be numeric');
    return Math.max(0, Math.floor(total));
};

const formatDurationSeconds = (durationMs: number): string => {
    const seconds = normalizeDurationMs(durationMs) / 1000;
    if (seconds < 10) {
        return formatNumberInvariant(seconds, { maximumFractionDigits: 2 });
    }
    if (seconds < 1000) {
        return formatNumberInvariant(seconds, { maximumFractionDigits: 1 });
    }
    return formatNumberInvariant(seconds, { maximumFractionDigits: 0 });
};

const trimDurationDecimalZeros = (value: string): string => {
    const trimmed = value.replace(/([.,]\d*?)0+$/, '$1').replace(/[.,]$/, '');
    return trimmed;
};

const formatMillisecondsAsSecondsUnit = (durationMs: number, decimals: number): string => {
    const seconds = normalizeDurationMs(durationMs) / 1000;
    return i18n.t('common.time.units.second.short', { count: formatNumberInvariant(seconds, { maximumFractionDigits: Math.max(0, decimals) }) });
};

const formatCompactMillisecondsAsSecondsUnit = (durationMs: number): string => {
    const seconds = normalizeDurationMs(durationMs) / 1000;
    const decimals = seconds < 10 ? 2 : seconds < 100 ? 1 : 0;
    return i18n.t('common.time.units.second.short', { count: trimDurationDecimalZeros(formatNumberInvariant(seconds, { maximumFractionDigits: decimals })) });
};

const formatHumanDurationFromMs = (durationMs: number): string => {
    const totalSeconds = Math.floor(normalizeDurationMs(durationMs) / 1000);
    const seconds = totalSeconds % 60;
    const totalMinutes = Math.floor(totalSeconds / 60);
    const minutes = totalMinutes % 60;
    const totalHours = Math.floor(totalMinutes / 60);
    const hours = totalHours % 24;
    const days = Math.floor(totalHours / 24);
    if (days > 0) {
        const parts = [`${days}d`];
        if (hours > 0) parts.push(`${hours}h`);
        if (minutes > 0) parts.push(`${minutes}m`);
        return parts.join(' ');
    }
    if (totalHours > 0) {
        const parts = [`${totalHours}h`];
        if (minutes > 0) parts.push(`${minutes}m`);
        if (seconds > 0) parts.push(`${seconds}s`);
        return parts.join(' ');
    }
    const parts = [`${totalMinutes}m`];
    if (seconds > 0) parts.push(`${seconds}s`);
    return parts.join(' ');
};

const formatCompactDurationFromMs = (durationMs: number): string => {
    const safeMs = normalizeDurationMs(durationMs);
    if (safeMs < 60_000) {
        return `${formatDurationSeconds(safeMs)}s`;
    }
    return formatHumanDurationFromMs(safeMs);
};

const truncateDurationSeconds = (durationSeconds: number, decimals: number): number => {
    const factor = 10 ** decimals;
    return Math.floor(durationSeconds * factor) / factor;
};

const formatStableElapsedDurationFromMs = (durationMs: number): string => {
    const safeMs = normalizeDurationMs(durationMs);
    if (safeMs < 10_000) {
        return `${formatNumberInvariant(truncateDurationSeconds(safeMs / 1000, 2), { minimumFractionDigits: 2, maximumFractionDigits: 2 })}s`;
    }
    if (safeMs < 60_000) {
        return `${formatNumberInvariant(truncateDurationSeconds(safeMs / 1000, 1), { minimumFractionDigits: 1, maximumFractionDigits: 1 })}s`;
    }
    const totalSeconds = Math.floor(safeMs / 1000);
    const seconds = totalSeconds % 60;
    const totalMinutes = Math.floor(totalSeconds / 60);
    const minutes = totalMinutes % 60;
    const totalHours = Math.floor(totalMinutes / 60);
    const hours = totalHours % 24;
    const days = Math.floor(totalHours / 24);
    if (days > 0) {
        return `${days}d ${hours}h ${minutes}m`;
    }
    if (totalHours > 0) {
        return `${totalHours}h ${minutes}m ${seconds}s`;
    }
    return `${totalMinutes}m ${seconds}s`;
};

const resolveWidestStableElapsedSiblingMs = (durationMs: number): number => {
    if (durationMs < 60_000) {
        return durationMs;
    }
    if (durationMs < 86_400_000) {
        return Math.floor(durationMs / 60_000) * 60_000 + 59_000;
    }
    return Math.floor(durationMs / 3_600_000) * 3_600_000 + 59 * 60_000;
};

const resolveStableElapsedDurationReserveCharacters = (durationMs: number): number => {
    const safeMs = normalizeDurationMs(durationMs);
    return formatStableElapsedDurationFromMs(resolveWidestStableElapsedSiblingMs(safeMs)).length;
};

const formatWholeDurationFromMs = (durationMs: number): string => {
    const durationSeconds = Math.floor(normalizeDurationMs(durationMs) / 1000);
    if (durationSeconds < 60) {
        return `${String(durationSeconds)}s`;
    }
    const durationMinutes = Math.floor(durationSeconds / 60);
    const secondsRemainder = durationSeconds % 60;
    if (durationMinutes < 60) {
        return `${String(durationMinutes)}m ${String(secondsRemainder)}s`;
    }
    const durationHours = Math.floor(durationMinutes / 60);
    const minutesRemainder = durationMinutes % 60;
    return `${String(durationHours)}h ${String(minutesRemainder)}m ${String(secondsRemainder)}s`;
};

const formatDuration = (seconds: number, style: 'short' | 'uptime' = 'short'): string => {
    const total = normalizeDurationSeconds(seconds);
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const remainingSeconds = Math.floor(total % 60);
    const formatShortUnit = (unit: 'day' | 'hour' | 'minute' | 'second', count: number): string => {
        const formattedCount = formatNumberLocalized(count);
        if (unit === 'day') return i18n.t('common.time.units.day.short', { count: formattedCount });
        if (unit === 'hour') return i18n.t('common.time.units.hour.short', { count: formattedCount });
        if (unit === 'minute') return i18n.t('common.time.units.minute.short', { count: formattedCount });
        return i18n.t('common.time.units.second.short', { count: formattedCount });
    };
    const formatLongUnit = (unit: 'day' | 'hour' | 'minute', count: number): string => {
        const formattedCount = formatNumberLocalized(count);
        if (unit === 'day') return i18n.plural('common.time.units.day.long', count, { count: formattedCount });
        if (unit === 'hour') return i18n.plural('common.time.units.hour.long', count, { count: formattedCount });
        return i18n.plural('common.time.units.minute.long', count, { count: formattedCount });
    };
    if (style === 'uptime') {
        if (days > 0) return `${formatShortUnit('day', days)}, ${formatShortUnit('hour', hours)} ${formatShortUnit('minute', minutes)}`;
        return hours > 0 ? `${formatShortUnit('hour', hours)} ${formatShortUnit('minute', minutes)}` : formatLongUnit('minute', minutes);
    }
    const parts: string[] = [];
    if (days > 0) parts.push(formatShortUnit('day', days));
    if (hours > 0) parts.push(formatShortUnit('hour', hours));
    if (minutes > 0) parts.push(formatShortUnit('minute', minutes));
    if (remainingSeconds > 0 || !parts.length) parts.push(formatShortUnit('second', remainingSeconds));
    return parts.join(' ');
};

const formatElapsedRuntimeFromStartMs = (startTimeMs: number, nowMs: number): string => {
    const createdMs = Number(startTimeMs);
    if (!isFiniteNumber(createdMs)) {
        throw new Error('Process runtime requires a numeric timestamp');
    }
    const elapsed = Math.max(0, (nowMs - createdMs) / 1000);
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const seconds = Math.floor(elapsed % 60);
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    if (minutes > 0) {
        return `${minutes}m ${seconds}s`;
    }
    return `${seconds}s`;
};

const formatSystemInfoDurationFromSeconds = (seconds: number | null): string | null => {
    if (seconds === null || !Number.isFinite(seconds)) return null;
    const totalSeconds = Math.max(0, Math.floor(seconds));
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const remainingSeconds = totalSeconds % 60;
    const parts: string[] = [];
    if (days) parts.push(`${days}d`);
    if (days || hours) parts.push(`${hours}h`);
    if (days || hours || minutes) parts.push(`${minutes}m`);
    if (!parts.length || remainingSeconds) parts.push(`${remainingSeconds}s`);
    return parts.join(' ');
};

const formatSystemInfoDurationFromMilliseconds = (milliseconds: number | null): string | null => {
    if (milliseconds === null || !Number.isFinite(milliseconds)) return null;
    return formatSystemInfoDurationFromSeconds(milliseconds / 1000);
};

export { formatCompactDurationFromMs, formatCompactMillisecondsAsSecondsUnit, formatDuration, formatDurationSeconds, formatElapsedRuntimeFromStartMs, formatHumanDurationFromMs, formatMillisecondsAsSecondsUnit, formatStableElapsedDurationFromMs, formatSystemInfoDurationFromMilliseconds, formatSystemInfoDurationFromSeconds, formatWholeDurationFromMs, normalizeDurationMs, resolveStableElapsedDurationReserveCharacters };
