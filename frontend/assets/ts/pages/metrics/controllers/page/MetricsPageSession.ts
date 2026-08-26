/* SoAI - Metrics page chart, history, table, and request state ownership [frontend/assets/ts/pages/metrics/controllers/page/MetricsPageSession.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { RequestDistributionChartSizeWatcher } from '@core/models/requestDistributionChartSizing.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { METRICS_HISTORY_API_POINT_LIMIT } from '@features/metrics/public.ts';
import { ChartFilters, HistoryChartControlsManager, HistoryChartRuntime, type HistoryChartPresentation } from '@features/charts/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ApiKeyUsageRow, CandlestickDataPoint, CandlestickMetadata, ChartInstanceWithMethods, MetricsCatalogEntry, MetricsData, MetricsHistoryPoint } from '@pages/metrics/types.ts';
import { applyMetricsPageControls } from '@pages/metrics/controllers/page/metricsPageControlsController.ts';

class MetricsPageSession {
    readonly storage: StorageService;
    readonly chartRuntime = new HistoryChartRuntime();
    readonly historyControlsManager = new HistoryChartControlsManager({ chartRuntime: this.chartRuntime });
    readonly distributionChartSizeWatcher = new RequestDistributionChartSizeWatcher();
    chartFilters: ChartFilters | null = null;
    mainChart: ChartInstanceWithMethods | null = null;
    chartPresentation: HistoryChartPresentation | null = null;
    timeRange = 120;
    currentMetrics: MetricsData | null = null;
    currentMetricType = 'requests';
    currentChartType = 'area';
    metricsHistory: MetricsHistoryPoint[] = [];
    candlestickData: CandlestickDataPoint[] = [];
    candlestickMetadata: CandlestickMetadata | null = null;
    candlestickBuckets = new Map<number, CandlestickDataPoint & { count: number }>();
    lastCandlestickRequest: string | null = null;
    isFetchingCandles = false;
    maxHistoryPoints = 50000;
    historyTrimRatio = 1.1;
    chartHardLimit = 50000;
    historyApiPointCap = METRICS_HISTORY_API_POINT_LIMIT;
    baseTimeRangeOptions: number[] | null = null;
    baseCandleIntervals: number[] | null = null;
    candlestickIntervalMinutes = 1;
    lastResolvedCandlestickIntervalMs: number | null = null;
    supportedHistoryIntervalsMs: number[] | null = null;
    supportedHistoryAggregations: string[] | null = null;
    supportsOhlc = true;
    maxRetentionMinutes: number | null = null;
    monitoringIntervalMs = 2000;
    currentPlugins: readonly (JsonValue | null)[] | null = null;
    currentApiKeyUsageRows: ApiKeyUsageRow[] | null = null;
    currentHistoryPointBudget = 0;
    availableTimeRanges: number[] = [];
    pluginHealthSortColumn = 'name';
    pluginHealthSortDirection = 'asc';
    apiKeyUsageSortColumn = 'requests';
    apiKeyUsageSortDirection = 'desc';
    modelTableSortColumn = 'requests';
    modelTableSortDirection = 'desc';
    frontendTelemetrySortColumn = 'metric';
    frontendTelemetrySortDirection = 'asc';
    systemStatsSortColumn = '';
    systemStatsSortDirection = 'asc';
    uiCache = new Map<string, HTMLElement>();
    metricsHistoryExhausted = false;
    candlestickHistoryExhausted = false;
    pendingChartSync = false;
    initialChartViewportFitted = false;
    valueHistoryRequestState = new Map<string, string>();
    valueHistoryRequestToken: number | null = null;
    lastRealtimeMetricValues = new Map<string, number>();
    metricsCatalog: Record<string, MetricsCatalogEntry> | null = null;
    metricsHistoryEnabled = false;

    constructor(storage: StorageService) {
        this.storage = storage;
        applyMetricsPageControls(this);
    }

    resetTransientState(): void {
        this.chartRuntime.reset();
        this.chartFilters = null;
        this.distributionChartSizeWatcher.disconnect();
        this.mainChart = null;
        this.chartPresentation = null;
        this.uiCache.clear();
        this.valueHistoryRequestState.clear();
        this.valueHistoryRequestToken = null;
        this.lastRealtimeMetricValues.clear();
        this.pendingChartSync = false;
        this.initialChartViewportFitted = false;
    }

    metricsSnapshot(): MetricsData | null {
        return this.currentMetrics;
    }
}

export { MetricsPageSession };
