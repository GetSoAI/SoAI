/* SoAI - Charts feature history chart controls actions [frontend/assets/ts/features/charts/historychartcontrols/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { readPositiveNumberRoundedIntegerOrNullValue, readRequiredPositiveNumberRoundedIntegerValue } from '@core/types/numberCoercionReaders.ts';
import { minutesToMs } from '@core/time/durations.ts';
import type { CandlestickSelection, TimeRangeSelection } from '@features/charts/controlsTypes.ts';
import { resolveCachedChartDataTransforms, resolveChartDataTransforms } from '@features/charts/historychartcontrols/guards.ts';
import type { ResolveCandlestickIntervalMsResolverOptions, ResolveCandlestickSelectionOptions, ResolveTimeRangeSelectionOptions } from '@features/charts/historychartcontrols/types.ts';

const resolveTimeRangeSelection = async ({ chartRuntime, retentionMinutes, baseOptions, selectedMinutes, minimum }: ResolveTimeRangeSelectionOptions): Promise<TimeRangeSelection> => {
    const dataTransforms = await resolveChartDataTransforms(chartRuntime);
    const defaults = dataTransforms.constants.DEFAULT_TIME_RANGES;
    if (!defaults.length) {
        throw new Error('Chart data utilities require at least one default time range');
    }
    const selection = dataTransforms.buildTimeRangeSelection({
        retentionMinutes,
        baseOptions: isArray(baseOptions) && baseOptions.length ? baseOptions : defaults,
        selectedMinutes,
        minimum
    });
    if (!isArray(selection.options) || !selection.options.length) {
        throw new Error('Time range selection requires at least one option');
    }
    return selection;
};

const resolveCandlestickSelection = async ({ chartRuntime, timeRangeMinutes, baseIntervals, supportedIntervalsMs, selectedIntervalMinutes, pointBudget, monitoringIntervalMs }: ResolveCandlestickSelectionOptions): Promise<CandlestickSelection> => {
    const dataTransforms = await resolveChartDataTransforms(chartRuntime);
    const defaults = dataTransforms.constants.DEFAULT_CANDLE_INTERVALS;
    if (!defaults.length) {
        throw new Error('Chart data utilities require at least one default candlestick interval');
    }
    return dataTransforms.buildCandlestickIntervalSelection({
        timeRangeMinutes,
        baseIntervals: isArray(baseIntervals) && baseIntervals.length ? baseIntervals : defaults,
        supportedIntervalsMs,
        selectedIntervalMinutes,
        pointBudget,
        monitoringIntervalMs
    });
};

const resolveCandlestickIntervalMs = ({ chartRuntime, metadataIntervalMs, lastResolvedIntervalMs, requestedIntervalMinutes, supportedHistoryIntervalsMs, monitoringIntervalMs }: ResolveCandlestickIntervalMsResolverOptions): number => {
    const metadataIntervalValue = readPositiveNumberRoundedIntegerOrNullValue(metadataIntervalMs);
    if (metadataIntervalValue !== null) {
        return metadataIntervalValue;
    }

    const resolvedIntervalValue = readPositiveNumberRoundedIntegerOrNullValue(lastResolvedIntervalMs);
    if (resolvedIntervalValue !== null) {
        return resolvedIntervalValue;
    }

    const requestedMs = minutesToMs(readRequiredPositiveNumberRoundedIntegerValue(requestedIntervalMinutes, 'History chart controls require a positive candlestick interval in minutes'));
    const baselineMs = readPositiveNumberRoundedIntegerOrNullValue(monitoringIntervalMs) ?? requestedMs;
    if (!isArray(supportedHistoryIntervalsMs) || !supportedHistoryIntervalsMs.length) {
        return baselineMs;
    }

    const dataTransforms = resolveCachedChartDataTransforms(chartRuntime);
    const resolved = dataTransforms.resolveSupportedIntervalMs(requestedMs, supportedHistoryIntervalsMs, baselineMs);
    const normalized = readPositiveNumberRoundedIntegerOrNullValue(resolved);
    if (normalized === null) {
        throw new Error('History chart controls failed to resolve candlestick interval');
    }
    return normalized;
};

export { resolveTimeRangeSelection, resolveCandlestickSelection, resolveCandlestickIntervalMs };
