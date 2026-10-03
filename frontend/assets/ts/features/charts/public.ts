/* SoAI - Charts feature public surface [frontend/assets/ts/features/charts/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { isCandlestickModeActive, resolveCandlestickIntervalMs } from '@features/charts/candlestickControls.ts';
export { isOhlcChartType, normalizeChartTypeToken } from '@features/charts/chartTypeNormalization.ts';
export { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
export type { FilterOption, FilterType, FilterValue } from '@features/charts/chartfilters/filterOptionTypes.ts';
export { ChartFilters } from '@features/charts/chartfilters/service.ts';
export type { ChartColorContext } from '@features/charts/chartTypes.ts';
export type { ChartPointInput, ChartValuePointInput } from '@features/charts/data/chartPointTypes.ts';
export type { HistoryChartControlsContract, HistoryChartDataTransformsModule, HistoryChartFiltersContract, HistoryChartInstance, HistoryChartOhlcModule, HistoryChartRuntimeContract } from '@features/charts/historyChartContracts.ts';
export { HistoryChartControlsManager } from '@features/charts/historychartcontrols/service.ts';
export { initializeHistoryChartFilters } from '@features/charts/historyChartFilters.ts';
export { renderHistoryChartStatus, resolveHistoryChartStatusElement } from '@features/charts/historyChartStatus.ts';
export type { HistoryChartStatusView } from '@features/charts/historyChartStatus.ts';
export { applyHistoryChartDefaults, syncHistoryCandlestickFilter, syncHistoryTimeRangeFilter } from '@features/charts/historyChartIntegration.ts';
export { invalidateChartControlSync, isCurrentChartControlSync, nextChartControlSyncSequence } from '@features/charts/historyChartSyncGate.ts';
export { HistoryRangeAvailability, settleHistoryAvailability } from '@features/charts/historyRangeAvailability.ts';
export type { HistoryAvailabilitySettlement } from '@features/charts/historyRangeAvailability.ts';
export { HistorySession } from '@features/charts/historySession.ts';
export { appendHistoryValue } from '@features/charts/historyValueAppend.ts';
export { buildHistoryDisplaySeries } from '@features/charts/historyDisplaySeries.ts';
export type { HistoryDisplaySourcePoint } from '@features/charts/historyDisplaySeries.ts';
export { HistoryPager } from '@features/charts/historyPager.ts';
export type { HistoryPagerPage, HistoryPagerSource } from '@features/charts/historyPager.ts';
export { followHistoryRange } from '@features/charts/historyRangeFollow.ts';
export { HistoryResolutionFollower, resolveHistoryResolutionChange } from '@features/charts/historyResolution.ts';
export type { HistoryResolutionWindow } from '@features/charts/historyResolution.ts';
export { resolveHistoryPagePoints } from '@features/charts/historyPageWindow.ts';
export type { HistoryPageWindow } from '@features/charts/historyPageWindow.ts';
export { subscribeHistoryResync } from '@features/charts/historyResyncSubscription.ts';
export { HistoryChartRuntime } from '@features/charts/HistoryChartRuntime.ts';
export { HISTORY_CHART_DEFAULT_CAP, HISTORY_CHART_MIN_POINTS, clampHistoryChartPointCount, computeHistoryChartPointBudget, resolveHistoryChartPlotWidthPx, resolveHistoryChartPointLimit, resolveHistoryChartStorageCapacity, scaleHistoryChartPointCount } from '@features/charts/historyPointBudget.ts';
export type { HistoryChartPointBudgetConfig } from '@features/charts/historyPointBudget.ts';
export type { BuildCandlestickOptions, CandlestickPoint, ParsedOhlcResult } from '@features/charts/ohlc/types.ts';
export { filterCandlestickBucketsForSeries } from '@features/charts/ohlc/trimming.ts';
export { createHistoryChartPresentation, HistoryChartPresentation } from '@features/charts/presentation/historyChartPresentation.ts';
export { markChartViewportFitted, resetChartViewportState, resolveChartViewportReset } from '@features/charts/viewportState.ts';
export type { ChartViewportStateHost } from '@features/charts/viewportState.ts';
