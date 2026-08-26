/* SoAI - Charts feature public surface [frontend/assets/ts/features/charts/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { isCandlestickModeActive, resolveCandlestickIntervalMs } from '@features/charts/candlestickControls.ts';
export { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
export { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
export type { FilterOption, FilterType, FilterValue } from '@features/charts/chartfilters/filterOptionTypes.ts';
export { ChartFilters } from '@features/charts/chartfilters/service.ts';
export type { ChartColorContext } from '@features/charts/chartTypes.ts';
export type { ChartPointInput, ChartValuePointInput } from '@features/charts/data/chartPointTypes.ts';
export type { HistoryChartControlsContract, HistoryChartDataTransformsModule, HistoryChartFiltersContract, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';
export { HistoryChartControlsManager } from '@features/charts/historychartcontrols/service.ts';
export { initializeHistoryChartFilters } from '@features/charts/historyChartFilters.ts';
export { applyHistoryChartDefaults, syncHistoryCandlestickFilter, syncHistoryTimeRangeFilter } from '@features/charts/historyChartIntegration.ts';
export { invalidateChartControlSync, isCurrentChartControlSync, nextChartControlSyncSequence } from '@features/charts/historyChartSyncGate.ts';
export { HistoryChartRuntime } from '@features/charts/HistoryChartRuntime.ts';
export { HISTORY_CHART_DEFAULT_CAP, HISTORY_CHART_MIN_POINTS, HISTORY_CHART_RESOLUTION_SCALE, clampHistoryChartPointCount, computeHistoryChartPointBudget, deriveHistoryChartPreferredPointCount, estimateHistoryChartIdealSpacing, resolveHistoryChartPointLimit, scaleHistoryChartPointCount } from '@features/charts/historyPointBudget.ts';
export type { HistoryChartPointBudgetConfig } from '@features/charts/historyPointBudget.ts';
export type { BuildCandlestickOptions, CandlestickPoint, ParsedOhlcResult } from '@features/charts/ohlc/types.ts';
export { filterCandlestickBucketsForSeries, trimCandlestickSeriesToTimeRange } from '@features/charts/ohlc/trimming.ts';
export { createHistoryChartPresentation, HistoryChartPresentation } from '@features/charts/presentation/historyChartPresentation.ts';
export { markChartViewportFitted, resetChartViewportState, resolveChartViewportReset } from '@features/charts/viewportState.ts';
export type { ChartViewportStateHost } from '@features/charts/viewportState.ts';
