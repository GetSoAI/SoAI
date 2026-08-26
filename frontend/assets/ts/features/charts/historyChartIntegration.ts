/* SoAI - Charts feature history chart integration [frontend/assets/ts/features/charts/historyChartIntegration.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isArray } from '@core/typeGuards.ts';
import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import type { ApplyHistoryChartDefaultsOptions, SyncHistoryCandlestickOptions, SyncHistoryTimeRangeOptions } from '@features/charts/historyChartContracts.ts';

const cloneOptions = (options: readonly number[] | null | undefined): number[] => {
    if (!isArray(options)) {
        return [];
    }
    return [...options];
};

const applyHistoryChartDefaults = ({ defaults, chartFilters, currentTimeRanges, currentCandleIntervals, setTimeRanges, setCandleIntervals }: ApplyHistoryChartDefaultsOptions): void => {
    const timeRanges = defaults?.timeRanges;
    const candleIntervals = defaults?.candleIntervals;
    if (cloneOptions(currentTimeRanges).length === 0 && isArray(timeRanges)) {
        setTimeRanges([...timeRanges]);
    }
    if (cloneOptions(currentCandleIntervals).length === 0 && isArray(candleIntervals)) {
        setCandleIntervals([...candleIntervals]);
    }
    if (!chartFilters) {
        return;
    }
    if (isArray(candleIntervals) && candleIntervals.length > 0) {
        chartFilters.setCandleIntervals(candleIntervals);
    }
};

const syncHistoryTimeRangeFilter = async ({ chartFilters, historyControlsManager, retentionMinutes, baseOptions, selectedMinutes, onSelection, isCurrent }: SyncHistoryTimeRangeOptions): Promise<void> => {
    if (!chartFilters) {
        return;
    }
    const retentionValue = Number(retentionMinutes);
    if (!Number.isFinite(retentionValue) || retentionValue <= 0) {
        chartFilters.setTimeRangeOptions([]);
        return;
    }
    const selection = await historyControlsManager.syncTimeRangeControls({
        retentionMinutes: retentionValue,
        baseOptions: cloneOptions(baseOptions),
        selectedMinutes
    });
    if (isCurrent && !isCurrent()) {
        return;
    }
    onSelection(selection);
    chartFilters.setTimeRangeOptions(selection.options);
    chartFilters.setValue(FILTER_TYPES.TIME_RANGE, selection.selected);
};

const syncHistoryCandlestickFilter = async ({ chartFilters, historyControlsManager, chartType, timeRangeMinutes, baseIntervals, supportedIntervalsMs, selectedIntervalMinutes, pointBudget, monitoringIntervalMs, onSelection, isCurrent }: SyncHistoryCandlestickOptions): Promise<void> => {
    if (!chartFilters) {
        return;
    }
    const selection = await historyControlsManager.syncCandlestickControls({
        timeRangeMinutes,
        baseIntervals: cloneOptions(baseIntervals),
        supportedIntervalsMs: cloneOptions(supportedIntervalsMs),
        selectedIntervalMinutes,
        pointBudget,
        monitoringIntervalMs
    });
    if (isCurrent && !isCurrent()) {
        return;
    }
    onSelection(selection);
    chartFilters.setCandleIntervals(selection.options);
    chartFilters.setValue(FILTER_TYPES.CANDLE_INTERVAL, selection.selected);
    chartFilters.setValue(FILTER_TYPES.CHART_TYPE, chartType);
};

export { applyHistoryChartDefaults, syncHistoryCandlestickFilter, syncHistoryTimeRangeFilter };
