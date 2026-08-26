/* SoAI - Charts feature time range formatting [frontend/assets/ts/features/charts/timeRangeFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';

type TimeRangeMinuteInput = string | number | boolean | null | undefined;

const MINUTES_PER_HOUR = 60;
const MINUTES_PER_DAY = 1440;
const MINUTES_PER_YEAR = 525600;
const MAX_COMPACT_UNIT_VALUE = 999;

const formatCompactLongRangeMinutes = (minutes: number): string => {
    if (minutes <= MAX_COMPACT_UNIT_VALUE) {
        return `${minutes}m`;
    }
    if (minutes < MINUTES_PER_DAY) {
        return `${Math.floor(minutes / MINUTES_PER_HOUR)}h`;
    }
    const days = Math.floor(minutes / MINUTES_PER_DAY);
    if (days <= MAX_COMPACT_UNIT_VALUE) {
        return `${days}d`;
    }
    return `${Math.max(1, Math.round(minutes / MINUTES_PER_YEAR))}y`;
};

const formatTimeRangeMinutes = (minutes: TimeRangeMinuteInput): string => {
    const numericValue = readCoercedFiniteNumberOrNullValue(minutes) ?? 0;
    const numeric = Math.max(1, Math.round(numericValue));
    if (numeric % MINUTES_PER_YEAR === 0) {
        const years = numeric / MINUTES_PER_YEAR;
        return `${years}y`;
    }
    if (numeric % MINUTES_PER_DAY === 0) {
        const days = numeric / MINUTES_PER_DAY;
        if (days <= MAX_COMPACT_UNIT_VALUE) {
            return `${days}d`;
        }
    }
    if (numeric % MINUTES_PER_HOUR === 0) {
        const hours = numeric / MINUTES_PER_HOUR;
        if (hours <= MAX_COMPACT_UNIT_VALUE) {
            return `${hours}h`;
        }
    }
    return formatCompactLongRangeMinutes(numeric);
};

const formatBucketedTimeRangeMinutes = (minutes: number): string => {
    return formatCompactLongRangeMinutes(Math.max(1, Math.round(minutes)));
};

export { formatBucketedTimeRangeMinutes, formatTimeRangeMinutes };
