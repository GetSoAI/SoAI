/* SoAI - Metrics page capabilities [frontend/assets/ts/pages/metrics/controllers/page/capabilities.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { decodeMetricsCapabilitiesSnapshot, type MetricsCatalogEntry } from '@core/realtime/streammanager/resources/systemMetricsMetadataContracts.ts';
import { requestWebSocketSnapshotRecord } from '@core/websocketclient/snapshotPayload.ts';
import { HISTORY_CHART_MIN_POINTS } from '@features/charts/public.ts';
import { METRICS_HISTORY_API_POINT_LIMIT } from '@features/metrics/public.ts';
import type { MetricsPageServiceHost } from '@pages/metrics/controllers/page/contracts.ts';
import { recalculateMetricsHistoryPointBudget } from '@pages/metrics/controllers/page/state.ts';
import type { CapabilitiesData } from '@pages/metrics/types.ts';

const normalizeMetricsCatalog = (candidate: Record<string, MetricsCatalogEntry> | undefined): Record<string, MetricsCatalogEntry> | null => (candidate && Object.keys(candidate).length ? candidate : null);

const getMetricsCatalogEntry = (host: MetricsPageServiceHost, metricKey: string): MetricsCatalogEntry | null => {
    if (!metricKey) {
        return null;
    }
    return host.state.metricsCatalog?.[metricKey] ?? null;
};

const applyMetricsCapabilities = (host: MetricsPageServiceHost, data: CapabilitiesData): void => {
    const historyConfiguration = data.historyConfiguration;
    host.state.metricsCatalog = normalizeMetricsCatalog(data.metricsCatalog);

    if (historyConfiguration) {
        if (historyConfiguration.enabled !== undefined) host.state.metricsHistoryEnabled = historyConfiguration.enabled;

        const intervals = historyConfiguration.supportedIntervalsMs;
        if (intervals) {
            host.state.supportedHistoryIntervalsMs = [...new Set(intervals.map(Number).filter((value) => Number.isFinite(value) && value > 0))].sort((firstValue, secondValue) => firstValue - secondValue);
        }

        const normalizedAggregations = (historyConfiguration.supportedAggregations ?? []).map((value) => value.toLowerCase());
        if (normalizedAggregations.length) {
            host.state.supportedHistoryAggregations = normalizedAggregations;
            host.state.supportsOhlc = normalizedAggregations.includes('ohlc') || historyConfiguration.supportsOhlc === true;
        } else {
            host.state.supportsOhlc = historyConfiguration.supportsOhlc === true;
        }

        const retentionHours = historyConfiguration.retentionHours ?? 0;
        if (retentionHours > 0) {
            host.state.maxRetentionMinutes = Math.max(5, retentionHours * 60);
        }

        const loggingInterval = historyConfiguration.loggingIntervalMs ?? 0;
        if (loggingInterval > 0) {
            host.state.monitoringIntervalMs = loggingInterval;
        }

        const maxPoints = historyConfiguration.maxPoints ?? 0;
        if (maxPoints > 0) {
            const sanitized = host.operations.normalizeMetricsInt(maxPoints, 1);
            host.state.historyApiPointCap = Math.min(METRICS_HISTORY_API_POINT_LIMIT, sanitized);
            host.state.maxHistoryPoints = Math.min(host.state.chartHardLimit, Math.max(HISTORY_CHART_MIN_POINTS, sanitized));
        }
    }

    recalculateMetricsHistoryPointBudget(host);
    host.state.mainChart?.settings.update({ maxDataPoints: Math.min(host.state.maxHistoryPoints, host.state.historyApiPointCap) });
};

const loadMetricsCapabilities = async (host: MetricsPageServiceHost, signal: AbortSignal): Promise<void> => {
    if (signal.aborted) {
        return;
    }
    const response = decodeMetricsCapabilitiesSnapshot(await requestWebSocketSnapshotRecord('system.metrics.capabilities'));
    if (signal.aborted) {
        return;
    }
    applyMetricsCapabilities(host, response);
};

export { applyMetricsCapabilities, getMetricsCatalogEntry, loadMetricsCapabilities, normalizeMetricsCatalog };
