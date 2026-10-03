/* SoAI - Metrics page effects [frontend/assets/ts/pages/metrics/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readRoundedPositiveIntegerOrNullValue } from '@core/types/numberCoercionReaders.ts';
import { isString } from '@core/typeGuards.ts';
import { applyHistoryChartDefaults, FILTER_TYPES, createHistoryChartPresentation, invalidateChartControlSync, isCurrentChartControlSync, isOhlcChartType, nextChartControlSyncSequence, syncHistoryCandlestickFilter, syncHistoryTimeRangeFilter, type HistoryChartPresentation } from '@features/charts/public.ts';
import { METRIC_TYPE_OPTIONS } from '@pages/metrics/contracts/metricsPageConstants.ts';
import type { MetricsPageActionsHost, MetricsPageEffectsHost } from '@pages/metrics/controllers/page/contracts.ts';
import { resetMetricsData, updateMetricsMainChart } from '@pages/metrics/controllers/page/metricsUpdateProcessing.ts';
import { persistMetricsPageControls } from '@pages/metrics/controllers/page/metricsPageControlsController.ts';
import { getMetricsMetricScaleBounds, isMetricsCandlestickActive, recalculateMetricsHistoryPointBudget, updateMetricsChartConfiguration } from '@pages/metrics/controllers/page/state.ts';
import { requireMetricsUi } from '@pages/metrics/dom.ts';
import { applyFrontendTelemetrySort } from '@pages/metrics/widgets/events.ts';
import { updateDistributionChart } from '@pages/metrics/widgets/effects.ts';
import { initializeMetricsChartFilters } from '@pages/metrics/widgets/metricsChartFilters.ts';

const setupMetricsPage = async (host: MetricsPageEffectsHost): Promise<void> => {
    const ui = requireMetricsUi(host);
    host.state.uiCache.clear();
    const setupSequence = nextChartControlSyncSequence(host);
    if (host.state.chartFilters) {
        host.state.chartFilters.dispose();
        host.state.chartFilters = null;
    }

    await host.state.chartRuntime.loadDefaults();
    if (!isCurrentChartControlSync(host, setupSequence)) {
        return;
    }
    applyHistoryChartDefaults({
        defaults: host.state.chartRuntime.getDefaults(),
        chartFilters: null,
        currentTimeRanges: host.state.baseTimeRangeOptions,
        currentCandleIntervals: host.state.baseCandleIntervals,
        setTimeRanges: (ranges: number[]) => {
            host.state.baseTimeRangeOptions = ranges;
        },
        setCandleIntervals: (intervals: number[]) => {
            host.state.baseCandleIntervals = intervals;
        }
    });

    const filtersContainer = host.owners.pageDom.requireHTMLElement('#metricsChartFilters', ui.root);
    const chartFilters = initializeMetricsChartFilters({
        container: filtersContainer,
        chartRuntime: host.state.chartRuntime,
        metricTypeOptions: METRIC_TYPE_OPTIONS,
        timeRangeOptions: host.state.availableTimeRanges,
        candleIntervals: host.state.baseCandleIntervals ?? [],
        initial: {
            chartType: host.state.currentChartType,
            metricType: host.state.currentMetricType,
            timeRange: host.state.timeRange,
            candleIntervalMinutes: host.state.candlestickIntervalMinutes
        },
        handlers: {
            onChartTypeChange: (value: string | number) => {
                const next = isString(value) ? value.trim() : String(value ?? '').trim();
                if (!next || next === host.state.currentChartType) {
                    return;
                }
                const kindChanged = isOhlcChartType(next) !== isOhlcChartType(host.state.currentChartType);
                if (kindChanged) host.history.dispose();
                host.state.currentChartType = next;
                persistMetricsPageControls(host.state);
                if (!kindChanged) {
                    updateMetricsMainChart(host);
                    return;
                }
                resetMetricsData(host);
                recalculateMetricsHistoryPointBudget(host);
                host.owners.pageLifecycle.runDetached('metrics:chartTypeChanged', async () => {
                    await syncMetricsChartControls(host, { candles: true, range: false });
                    await reloadMetricsChartData(host);
                });
            },
            onMetricTypeChange: (value: string | number) => {
                const next = isString(value) ? value.trim() : String(value ?? '').trim();
                if (!next || next === host.state.currentMetricType) {
                    return;
                }
                getMetricsChartPresentation(host).begin();
                host.history.dispose();
                host.state.currentMetricType = next;
                persistMetricsPageControls(host.state);
                updateMetricsChartConfiguration(host);
                resetMetricsData(host, true);
                host.owners.pageLifecycle.runDetached('metrics:metricTypeChanged', async () => {
                    await reloadMetricsChartData(host);
                });
            },
            onTimeRangeChange: (value: string | number) => {
                const next = readRoundedPositiveIntegerOrNullValue(value);
                if (next === null || next === host.state.timeRange) {
                    return;
                }
                host.history.dispose();
                host.state.timeRange = next;
                resetMetricsData(host);
                persistMetricsPageControls(host.state);
                recalculateMetricsHistoryPointBudget(host);
                host.owners.pageLifecycle.runDetached('metrics:timeRangeChanged', async () => {
                    await syncMetricsChartControls(host, { candles: true, range: false });
                    await reloadMetricsChartData(host);
                    updateDistributionChart(host);
                });
            },
            onCandleIntervalChange: (value: string | number) => {
                const next = readRoundedPositiveIntegerOrNullValue(value);
                if (next === null || next === host.state.candlestickIntervalMinutes) {
                    return;
                }
                host.state.candlestickIntervalMinutes = next;
                resetMetricsData(host);
                persistMetricsPageControls(host.state);
                if (!isMetricsCandlestickActive(host)) {
                    return;
                }
                host.history.dispose();
                recalculateMetricsHistoryPointBudget(host);
                host.owners.pageLifecycle.runDetached('metrics:candleIntervalChanged', async () => {
                    await reloadMetricsChartData(host);
                });
            }
        }
    });
    host.state.chartFilters = chartFilters;
    chartFilters.setValue(FILTER_TYPES.SUBCATEGORY, host.state.currentMetricType, false);
    chartFilters.setValue(FILTER_TYPES.CHART_TYPE, host.state.currentChartType, false);
    await syncMetricsChartControls(host);
};

const getMetricsChartPresentation = (host: MetricsPageEffectsHost): HistoryChartPresentation => {
    if (!host.state.chartPresentation) {
        host.state.chartPresentation = createHistoryChartPresentation(host.owners.pageDom.requireHTMLElement('#mainChartContainer'));
    }
    return host.state.chartPresentation;
};

const teardownMetricsChartUi = async (host: MetricsPageEffectsHost): Promise<void> => {
    invalidateChartControlSync(host);
    host.history.dispose();
    if (host.state.chartFilters) {
        host.state.chartFilters.dispose();
        host.state.chartFilters = null;
    }
    if (host.state.mainChart) {
        const chart = host.state.mainChart;
        host.state.mainChart = null;
        await chart.lifecycle.destroy();
    }
    host.state.chartPresentation?.destroy();
    host.state.chartPresentation = null;
    host.state.uiCache.clear();
};

const syncMetricsChartControls = async (host: MetricsPageEffectsHost, { range = true, candles = true }: { range?: boolean; candles?: boolean } = {}): Promise<void> => {
    const chartFilters = host.state.chartFilters;
    if (!chartFilters) {
        return;
    }
    const syncSequence = nextChartControlSyncSequence(host);
    const isCurrent = (): boolean => isCurrentChartControlSync(host, syncSequence);
    await host.state.chartRuntime.loadDefaults();
    if (!isCurrent() || host.state.chartFilters !== chartFilters) {
        return;
    }
    applyHistoryChartDefaults({
        defaults: host.state.chartRuntime.getDefaults(),
        chartFilters,
        currentTimeRanges: host.state.baseTimeRangeOptions,
        currentCandleIntervals: host.state.baseCandleIntervals,
        setTimeRanges: (ranges: number[]) => {
            host.state.baseTimeRangeOptions = ranges;
        },
        setCandleIntervals: (intervals: number[]) => {
            host.state.baseCandleIntervals = intervals;
        }
    });

    if (range) {
        await syncHistoryTimeRangeFilter({
            chartFilters,
            historyControlsManager: host.state.historyControlsManager,
            rangeAvailability: host.history.rangeAvailability,
            seriesKey: host.history.seriesKey(),
            retentionMinutes: host.state.maxRetentionMinutes,
            baseOptions: host.state.baseTimeRangeOptions,
            selectedMinutes: host.state.timeRange,
            onSelection: (selection) => {
                host.state.timeRange = selection.selected;
                host.state.availableTimeRanges = selection.options;
                recalculateMetricsHistoryPointBudget(host);
            },
            isCurrent
        });
        if (!isCurrent()) {
            return;
        }
    }

    if (candles) {
        await syncHistoryCandlestickFilter({
            chartFilters,
            historyControlsManager: host.state.historyControlsManager,
            chartType: host.state.currentChartType,
            timeRangeMinutes: host.state.timeRange,
            baseIntervals: host.state.baseCandleIntervals,
            supportedIntervalsMs: host.state.supportedHistoryIntervalsMs,
            selectedIntervalMinutes: host.state.candlestickIntervalMinutes,
            pointBudget: host.operations.pointBudget(),
            monitoringIntervalMs: host.state.monitoringIntervalMs,
            onSelection: (selection) => {
                host.state.candlestickIntervalMinutes = selection.selected;
            },
            isCurrent
        });
        if (!isCurrent()) {
            return;
        }
    }

    chartFilters.setValue(FILTER_TYPES.SUBCATEGORY, host.state.currentMetricType, false);
    chartFilters.setValue(FILTER_TYPES.CHART_TYPE, host.state.currentChartType, false);
};

const initializeMetricsMainChart = async (host: MetricsPageEffectsHost, signal: AbortSignal): Promise<void> => {
    if (host.state.mainChart) {
        return;
    }
    const container = host.operations.getCachedUI('mainChartContainer') ?? host.owners.pageDom.requireHTMLElement('#mainChartContainer');
    getMetricsChartPresentation(host).reset();
    const maxDataPoints = host.state.maxHistoryPoints;
    const chart = await host.state.chartRuntime.initializeChart({
        container,
        chartType: host.state.currentChartType,
        options: {
            maxDataPoints,
            history: host.history.pager,
            onTimeRangeChange: (visibleStartTs: number, visibleEndTs: number) => host.history.followRange(visibleStartTs, visibleEndTs)
        },
        signal
    });
    if (signal.aborted) {
        await chart.lifecycle.destroy();
        return;
    }
    host.state.mainChart = chart;
    chart.settings.update({ maxDataPoints, scaleBounds: getMetricsMetricScaleBounds(host.state.currentMetricType) });
    updateMetricsChartConfiguration(host);
    recalculateMetricsHistoryPointBudget(host);
    updateMetricsMainChart(host, { resetView: true });
    updateDistributionChart(host);
};

const initializeMetricsFrontendTelemetryCard = async (host: MetricsPageActionsHost): Promise<void> => {
    if (!host.metricsServices.telemetryPresenter) {
        return;
    }
    await host.metricsServices.telemetryPresenter.initialize();
    applyFrontendTelemetrySort(host);
};

const reloadMetricsChartData = async (host: MetricsPageEffectsHost): Promise<void> => {
    host.state.mainChart?.settings.update({ maxDataPoints: host.state.maxHistoryPoints });
    await host.history.load();
};

export { getMetricsChartPresentation, initializeMetricsFrontendTelemetryCard, initializeMetricsMainChart, reloadMetricsChartData, setupMetricsPage, syncMetricsChartControls, teardownMetricsChartUi };
