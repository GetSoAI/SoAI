/* SoAI - Charts feature data transforms service [frontend/assets/ts/features/charts/datatransforms/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray } from '@core/typeGuards.ts';
import { readCoercedFiniteNumberOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { minutesToMs, msToMinutes } from '@core/time/durations.ts';
import { DEFAULT_CANDLE_INTERVALS, DEFAULT_TIME_RANGES, MIN_RETENTION_MINUTES } from '@features/charts/datatransforms/constants.ts';
import { ensureMinutesOption, normalizeMinutesList, normalizeMinutesValue, resolveSupportedIntervalMs } from '@features/charts/datatransforms/guards.ts';
import type { CandlestickIntervalSelectionOptions, TimeRangeSelectionOptions } from '@features/charts/datatransforms/types.ts';

const deriveTimeRangeOptions = (retentionMinutes: JsonValue | null | undefined, baseOptions: readonly number[] = DEFAULT_TIME_RANGES): number[] => {
    const retentionValue = readCoercedFiniteNumberOrNullValue(retentionMinutes);
    const sanitizedRetention = Number.isFinite(retentionValue) && retentionValue !== null && retentionValue > 0 ? Math.max(1, Math.round(retentionValue)) : null;

    const uniqueBase = isArray(baseOptions) && baseOptions.length ? Array.from(new Set(baseOptions.map((value: number): number => Math.max(1, Math.round(value))))) : [...DEFAULT_TIME_RANGES];

    let options = sanitizedRetention ? uniqueBase.filter((value: number): boolean => value <= sanitizedRetention) : [...uniqueBase];

    if (!options.length && sanitizedRetention) {
        options = [sanitizedRetention];
    }

    if (sanitizedRetention && !options.includes(sanitizedRetention)) {
        options.push(sanitizedRetention);
    }

    options = Array.from(new Set(options)).sort((firstValue: number, secondValue: number): number => firstValue - secondValue);
    if (!options.length) {
        options = [...DEFAULT_TIME_RANGES];
    }
    return options;
};

const buildTimeRangeSelection = ({ retentionMinutes, baseOptions = DEFAULT_TIME_RANGES, selectedMinutes = null, minimum = MIN_RETENTION_MINUTES }: TimeRangeSelectionOptions = {}): { options: number[]; selected: number } => {
    const options = deriveTimeRangeOptions(retentionMinutes, baseOptions);
    const defaultValue = options[options.length - 1] ?? minimum;
    const retentionNumeric = readCoercedFiniteNumberOrNullValue(retentionMinutes);
    const effectiveMinimum = Number.isFinite(retentionNumeric) && retentionNumeric !== null && retentionNumeric > 0 ? Math.min(minimum, Math.max(1, Math.round(retentionNumeric))) : minimum;
    const normalizedSelected = normalizeMinutesValue(selectedMinutes, defaultValue ?? effectiveMinimum, { minimum: effectiveMinimum });
    const cappedSelected = Number.isFinite(retentionNumeric) && retentionNumeric !== null && retentionNumeric > 0 && normalizedSelected !== null ? Math.min(normalizedSelected, Math.max(effectiveMinimum, Math.round(retentionNumeric))) : (normalizedSelected ?? effectiveMinimum);

    const mergedOptions = ensureMinutesOption(options, cappedSelected, { minimum: effectiveMinimum });
    const selected = mergedOptions.includes(cappedSelected) ? cappedSelected : (mergedOptions[mergedOptions.length - 1] ?? effectiveMinimum);

    return { options: mergedOptions, selected };
};

const deriveCandlestickIntervals = (timeRangeMinutes: JsonValue | null | undefined, baseIntervals: readonly number[] = DEFAULT_CANDLE_INTERVALS): number[] => {
    const rangeValue = readCoercedFiniteNumberOrNullValue(timeRangeMinutes);
    const numericRange = Number.isFinite(rangeValue) && rangeValue !== null && rangeValue > 0 ? Math.round(rangeValue) : null;

    const uniqueBase = isArray(baseIntervals) && baseIntervals.length ? Array.from(new Set(baseIntervals.map((value: number): number => Math.max(1, Math.round(value))))) : [...DEFAULT_CANDLE_INTERVALS];

    const options = numericRange ? uniqueBase.filter((interval: number): boolean => interval <= numericRange) : uniqueBase;
    return options.length ? options : [1];
};

const normalizeCandlestickPointBudget = (pointBudget: JsonValue | null | undefined): number | null => {
    const budgetValue = readCoercedFiniteNumberOrNullValue(pointBudget);
    return Number.isFinite(budgetValue) && budgetValue !== null && budgetValue > 0 ? Math.max(1, Math.floor(budgetValue)) : null;
};

const isCandlestickIntervalWithinBudget = (minutes: number, rangeMinutes: number | null, pointBudget: number | null, tolerance: number): boolean => {
    if (!(Number.isFinite(rangeMinutes) && rangeMinutes !== null && rangeMinutes > 0 && pointBudget !== null)) {
        return true;
    }
    const candleCount = Math.max(1, Math.ceil(rangeMinutes / Math.max(1, minutes)));
    return candleCount <= pointBudget * tolerance;
};

const selectCandlestickInterval = (options: readonly number[], normalizedSelected: number | null, minimum: number): number => {
    if (!options.length) {
        return minimum;
    }
    if (normalizedSelected !== null && options.includes(normalizedSelected)) {
        return normalizedSelected;
    }
    if (normalizedSelected !== null) {
        return options.reduce((best: number, value: number): number => (value <= normalizedSelected ? value : best), options[0] ?? minimum);
    }
    return options[0] ?? minimum;
};

const buildCandlestickIntervalSelection = ({ timeRangeMinutes, baseIntervals = DEFAULT_CANDLE_INTERVALS, supportedIntervalsMs = null, selectedIntervalMinutes = null, pointBudget = null, tolerance = 1.1, minimum = 1, monitoringIntervalMs = null }: CandlestickIntervalSelectionOptions = {}): { options: number[]; selected: number; intervalMs: number } => {
    const rangeMinutes = normalizeMinutesValue(timeRangeMinutes, null, { minimum });
    const base = normalizeMinutesList(baseIntervals, { minimum });
    const supported =
        isArray(supportedIntervalsMs) && supportedIntervalsMs.length
            ? normalizeMinutesList(
                  supportedIntervalsMs.map((milliseconds: number): number => msToMinutes(Number(milliseconds))),
                  { minimum }
              )
            : [];

    let options = [...(supported.length ? supported : base)];
    if (!options.length) {
        options = [minimum];
    }
    const isSupportedInterval = (interval: number): boolean => !supported.length || supported.includes(interval);

    if (Number.isFinite(rangeMinutes) && rangeMinutes !== null && rangeMinutes > 0) {
        const filtered = options.filter((interval: number): boolean => interval <= rangeMinutes);
        if (filtered.length) {
            options = filtered;
        } else {
            options = [options[0] ?? minimum];
        }
    }

    const normalizedBudget = normalizeCandlestickPointBudget(pointBudget);
    if (Number.isFinite(rangeMinutes) && rangeMinutes !== null && rangeMinutes > 0 && normalizedBudget !== null) {
        const filtered = options.filter((minutes: number): boolean => isCandlestickIntervalWithinBudget(minutes, rangeMinutes, normalizedBudget, tolerance));
        if (filtered.length) {
            options = filtered;
        } else {
            options = [options[options.length - 1] ?? minimum];
        }
    }

    const pinnedIntervals = [1, 5];
    if (Number.isFinite(rangeMinutes) && rangeMinutes !== null && rangeMinutes > 0) {
        pinnedIntervals
            .filter((interval: number): boolean => isSupportedInterval(interval) && interval <= rangeMinutes && isCandlestickIntervalWithinBudget(interval, rangeMinutes, normalizedBudget, tolerance))
            .forEach((interval: number): void => {
                if (!options.includes(interval)) {
                    options.push(interval);
                }
            });
    } else {
        pinnedIntervals.forEach((interval: number): void => {
            if (isSupportedInterval(interval) && !options.includes(interval)) {
                options.push(interval);
            }
        });
    }

    options = Array.from(new Set(options)).sort((firstValue: number, secondValue: number): number => firstValue - secondValue);

    const defaultSelected = options.length ? options[0] : minimum;
    const normalizedSelected = normalizeMinutesValue(selectedIntervalMinutes, defaultSelected ?? minimum, {
        minimum
    });
    if (normalizedSelected !== null && isSupportedInterval(normalizedSelected) && isCandlestickIntervalWithinBudget(normalizedSelected, rangeMinutes, normalizedBudget, tolerance)) {
        options = ensureMinutesOption(options, normalizedSelected, { minimum });
    }

    let selected = selectCandlestickInterval(options, normalizedSelected, minimum);
    if (!Number.isFinite(selected)) {
        const lastOption = options[options.length - 1];
        selected = lastOption ?? minimum;
    }

    const targetMs = minutesToMs(selected);
    const defaultMs = Number.isFinite(monitoringIntervalMs) && monitoringIntervalMs !== null && monitoringIntervalMs > 0 ? Math.round(Math.max(1, monitoringIntervalMs)) : targetMs;
    const intervalMs = resolveSupportedIntervalMs(targetMs, supportedIntervalsMs, defaultMs);

    return { options, selected, intervalMs };
};

export { buildCandlestickIntervalSelection, buildTimeRangeSelection, deriveCandlestickIntervals, deriveTimeRangeOptions };
