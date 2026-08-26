/* SoAI - Metrics page contract boundary constants [frontend/assets/ts/pages/metrics/contracts/metricsPageConstants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';

interface MetricTypeOption {
    value: string;
    getLabel: () => string;
}

interface FrontendTelemetryRowConfig {
    id: string;
    getLabel: () => string;
    getInitialValue: () => string;
}

const METRIC_TYPE_OPTIONS: readonly MetricTypeOption[] = Object.freeze([
    { value: 'requests', getLabel: () => i18n.t('metrics.cards.performanceMetrics.metricTypes.requests') },
    { value: 'latency', getLabel: () => i18n.t('metrics.cards.performanceMetrics.metricTypes.latency') },
    { value: 'tokens', getLabel: () => i18n.t('metrics.cards.performanceMetrics.metricTypes.tokens') },
    { value: 'queue', getLabel: () => i18n.t('metrics.cards.performanceMetrics.metricTypes.queueDepth') }
]);

const FRONTEND_TELEMETRY_ROW_CONFIG: readonly FrontendTelemetryRowConfig[] = Object.freeze([
    {
        id: 'frontendConnectionValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.connection'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendLatencyValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.websocketRoundTripLatency'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendStageValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.stage'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendSubscribersValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.subscribers'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendRestartSubscribersValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.restartSubscribers'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendConnectionHoldsValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.connectionHolds'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendQueueValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.queueDepth'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendThrottleValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.telemetryThrottle'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendPendingEventsValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.pendingEvents'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendPendingMetricsValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.pendingMetrics'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.pending')
    },
    {
        id: 'frontendSinksValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.sinks'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.none')
    },
    {
        id: 'frontendLastEventValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.lastEvent'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.lastEventNone')
    },
    {
        id: 'frontendLastEventSeverityValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.lastEventSeverity'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.none')
    },
    {
        id: 'frontendLastEventModuleValue',
        getLabel: (): string => i18n.t('metrics.cards.frontendMetrics.rows.lastEventModule'),
        getInitialValue: (): string => i18n.t('metrics.cards.frontendMetrics.values.none')
    }
]);

const CHART_FONT = '14px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif';

export { METRIC_TYPE_OPTIONS, FRONTEND_TELEMETRY_ROW_CONFIG, CHART_FONT };
export type { MetricTypeOption, FrontendTelemetryRowConfig };
