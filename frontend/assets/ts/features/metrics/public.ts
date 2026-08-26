/* SoAI - Metrics feature public surface [frontend/assets/ts/features/metrics/public.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

export { KPI_CONFIG, METRIC_HISTORY_AGGREGATIONS, METRIC_HISTORY_KEYS, METRIC_HISTORY_OHLC_AGGREGATIONS, METRIC_SCALE_BOUNDS, METRICS_HISTORY_API_POINT_LIMIT, SYSTEM_STATS_CONFIG, resolveMetricsTotalTokens, resolveMetricsActiveInferences } from '@features/metrics/Config.ts';
export { resolveMetricsCurrentTokenRate } from '@features/metrics/liveTokenRates.ts';
export type { MetricsKpiHost, ScaleBound } from '@features/metrics/Config.ts';
export type { Metrics } from '@features/metrics/metricsSnapshot.ts';
export { MetricsFormatter } from '@features/metrics/Formatter.ts';
export { FrontendTelemetryPresenter } from '@features/metrics/Telemetry.ts';
export type { FrontendTelemetryHost, TelemetryService } from '@features/metrics/Telemetry.ts';
export { openMetricsAdvancedModal } from '@features/metrics/modals/advancedMetricsModal.ts';
export { refreshMetricsAdvancedModalIfOpen } from '@features/metrics/modals/advancedMetricsModal.ts';
export { METRICS_ADVANCED_MODAL_ID } from '@features/metrics/modals/advancedMetricsModal.ts';
export { setActiveMetricsAdvancedModalHost } from '@features/metrics/modals/advancedMetricsHost.ts';
export type { MetricsAdvancedModalHost } from '@features/metrics/modals/advancedMetricsHost.ts';
