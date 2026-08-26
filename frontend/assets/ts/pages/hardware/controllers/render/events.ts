/* SoAI - Hardware page render events [frontend/assets/ts/pages/hardware/controllers/render/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { applyHistoryChartDefaults, FILTER_TYPES, invalidateChartControlSync, isCurrentChartControlSync, nextChartControlSyncSequence, syncHistoryCandlestickFilter, syncHistoryTimeRangeFilter, type ChartFilters, type FilterType, type FilterValue, type HistoryChartControlsManager } from '@features/charts/public.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import { getPointBudget, type HardwareChartContext } from '@pages/hardware/controllers/render/effects.ts';
import { buildDeviceCategoryOptions, buildMetricOptions } from '@pages/hardware/mappers/mappers.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ChartDefaultsInput, HardwarePageSnapshot, MetricOption } from '@pages/hardware/types.ts';

type HardwareRenderFiltersContext = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    historyControlsManager: HistoryChartControlsManager;
    chartContext: HardwareChartContext;
    chartFilters: ChartFilters | null;
};

const applyChartDefaults = (context: HardwareRenderFiltersContext, { timeRanges, candleIntervals }: ChartDefaultsInput = {}): void => {
    applyHistoryChartDefaults({
        defaults: { timeRanges, candleIntervals },
        chartFilters: context.chartFilters,
        currentTimeRanges: context.state.baseTimeRangeOptions,
        currentCandleIntervals: context.state.baseCandleIntervals,
        setTimeRanges: (timeRangesValue: number[]) => {
            context.state.baseTimeRangeOptions = timeRangesValue;
        },
        setCandleIntervals: (candleIntervalsValue: number[]) => {
            context.state.baseCandleIntervals = candleIntervalsValue;
        }
    });
};

const refreshChartControls = async (context: HardwareRenderFiltersContext, { range = true, candles = true } = {}): Promise<void> => {
    const syncSequence = nextChartControlSyncSequence(context);
    const isCurrent = (): boolean => isCurrentChartControlSync(context, syncSequence);
    if (range) {
        await syncHistoryTimeRangeFilter({
            chartFilters: context.chartFilters,
            historyControlsManager: context.historyControlsManager,
            retentionMinutes: context.state.maxRetentionMinutes,
            baseOptions: context.state.baseTimeRangeOptions,
            selectedMinutes: context.state.timeRange,
            onSelection: (selection) => {
                context.state.timeRange = selection.selected;
                context.state.availableTimeRanges = selection.options;
            },
            isCurrent
        });
        if (!isCurrent()) {
            return;
        }
    }
    if (candles) {
        await syncHistoryCandlestickFilter({
            chartFilters: context.chartFilters,
            historyControlsManager: context.historyControlsManager,
            chartType: context.state.chartType,
            timeRangeMinutes: context.state.timeRange,
            baseIntervals: context.state.baseCandleIntervals,
            supportedIntervalsMs: context.state.supportedHistoryIntervalsMs,
            selectedIntervalMinutes: context.state.candlestickIntervalMinutes,
            pointBudget: getPointBudget(context.chartContext),
            monitoringIntervalMs: context.state.monitoringIntervalMs,
            onSelection: (selection) => {
                context.state.candlestickIntervalMinutes = selection.selected;
                context.state.lastResolvedCandlestickIntervalMs = selection.intervalMs;
            },
            isCurrent
        });
    }
};

const updateDeviceSelector = (context: HardwareRenderFiltersContext, snapshot: HardwarePageSnapshot | null = context.state.lastSnapshot): boolean => {
    if (!context.chartFilters) return false;
    if (snapshot && snapshot !== context.state.lastSnapshot) {
        context.state.lastSnapshot = snapshot;
    }
    const previousSelection = context.state.selectedDevice;
    const options = buildDeviceCategoryOptions(context.state);
    if (options.length === 0) {
        throw new Error('Hardware device selector requires at least one device option');
    }
    const firstOption = options[0];
    if (!firstOption) {
        throw new Error('Hardware device selector requires at least one device option');
    }
    const available = options.map((entry) => entry.value);
    if (!available.includes(context.state.selectedDevice)) context.state.selectedDevice = firstOption.value;
    context.dataController.ensureMetricForDevice(context.dataController.getSelectedHistoryTarget().type);
    context.chartFilters.setCategories(options);
    context.chartFilters.setValue(FILTER_TYPES.CATEGORY, context.state.selectedDevice);
    syncMetricOptions(context);
    return previousSelection !== context.state.selectedDevice;
};

const syncMetricOptions = (context: HardwareRenderFiltersContext): void => {
    if (!context.chartFilters) return;
    const target = context.dataController.getSelectedHistoryTarget();
    context.dataController.ensureMetricForDevice(target.type);
    context.chartFilters.setSubcategories(buildMetricOptions(context.state, target.type, context.state.selectedMetric));
    context.chartFilters.setValue(FILTER_TYPES.SUBCATEGORY, context.state.selectedMetric);
};

const updateMetricFilterOptions = (context: HardwareRenderFiltersContext, selectedMetric: string): void => {
    if (!context.chartFilters) return;
    const target = context.dataController.getSelectedHistoryTarget();
    const options: MetricOption[] = buildMetricOptions(context.state, target.type, selectedMetric);
    context.chartFilters.setSubcategories(options);
    context.chartFilters.setValue(FILTER_TYPES.SUBCATEGORY, selectedMetric);
};

const updateChartFilterValue = (context: HardwareRenderFiltersContext, filterType: FilterType, value: FilterValue | null): void => {
    context.chartFilters?.setValue(filterType, value);
};

export { applyChartDefaults, invalidateChartControlSync, refreshChartControls, syncMetricOptions, updateChartFilterValue, updateDeviceSelector, updateMetricFilterOptions };
export type { HardwareRenderFiltersContext };
