/* SoAI - Metrics feature telemetry card values [frontend/assets/ts/features/metrics/telemetryCardValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { filterNonEmptyStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isBoolean, isFiniteNumber, isObject, isString } from '@core/typeGuards.ts';
import type { MetricsFormatter } from '@features/metrics/Formatter.ts';
import { resolveTelemetryStageBaseLabel } from '@features/metrics/telemetryStageLabels.ts';

interface ConnectionMetricValue {
    connected?: boolean | null;
    stage?: string | null;
    restartSubscribers?: number | null;
    holds?: number | null;
}

interface QueueMetricValue {
    depth?: number | null;
    subscribers?: number | string | null;
}

interface TelemetryMetricMetadata {
    subscribers?: number | string | null;
}

interface TelemetryMetric {
    value?: ConnectionMetricValue | QueueMetricValue | number | string | null;
    metadata?: TelemetryMetricMetadata | null;
    meta?: TelemetryMetricMetadata | null;
}

interface TelemetryStatus {
    throttleMs?: number | null;
    pendingEvents?: number | null;
    pendingMetrics?: number | null;
    sinks?: readonly string[] | null;
    state?: string | null;
}

interface TelemetryEvent {
    stage?: string | null;
    message?: string | null;
    timestamp?: number | null;
    severity?: string | null;
    module?: string | null;
}

interface FrontendTelemetryCardValues {
    connection: string;
    latency: string;
    stage: string;
    subscribers: string;
    restartSubscribers: string;
    connectionHolds: string;
    queue: string;
    throttle: string;
    pendingEvents: string;
    pendingMetrics: string;
    sinks: string;
    lastEvent: string;
    lastEventSeverity: string;
    lastEventModule: string;
    status: string;
}

interface BuildFrontendTelemetryCardValuesArguments {
    connection: TelemetryMetric | null;
    latency: TelemetryMetric | null;
    queue: TelemetryMetric | null;
    lastEvent: TelemetryEvent | null;
    status: TelemetryStatus | null;
    formatter: MetricsFormatter;
}

const resolveConnectionValueLabel = (connected: boolean | null): string => {
    if (connected === true) {
        return i18n.t('metrics.cards.frontendMetrics.values.connected');
    }
    if (connected === false) {
        return i18n.t('metrics.cards.frontendMetrics.values.disconnected');
    }
    return i18n.t('metrics.cards.frontendMetrics.values.pending');
};

const resolveFrontendTelemetryStatusLabel = <T>(state: T): string => {
    if (state === null || state === undefined) {
        return i18n.t('metrics.cards.frontendMetrics.statusPending');
    }
    const normalized = String(state).trim().toLowerCase();
    if (!normalized) {
        return i18n.t('metrics.cards.frontendMetrics.statusPending');
    }
    switch (normalized) {
        case 'connected':
            return i18n.t('metrics.cards.frontendMetrics.states.connected');
        case 'connecting':
            return i18n.t('metrics.cards.frontendMetrics.states.connecting');
        case 'disconnected':
            return i18n.t('metrics.cards.frontendMetrics.states.disconnected');
        case 'pending':
            return i18n.t('metrics.cards.frontendMetrics.states.pending');
        case 'ready':
            return i18n.t('metrics.cards.frontendMetrics.states.ready');
        case 'error':
            return i18n.t('metrics.cards.frontendMetrics.states.error');
        case 'unknown':
            return i18n.t('metrics.cards.frontendMetrics.states.unknown');
        default:
            return i18n.t('metrics.cards.frontendMetrics.states.unknown');
    }
};

const resolveTelemetryStageLabel = (stage: string | null): string => {
    if (!stage || !isString(stage)) {
        return i18n.t('metrics.cards.frontendMetrics.values.pending');
    }
    const trimmed = stage.trim();
    if (!trimmed) {
        return i18n.t('metrics.cards.frontendMetrics.values.pending');
    }
    const parts = trimmed.split(/\s+/, 2);
    const baseStage = (parts[0] ?? '').trim();
    const qualifier = (parts[1] ?? '').trim();
    const baseLabel = resolveTelemetryStageBaseLabel(baseStage || trimmed);
    if (!qualifier) {
        return baseLabel;
    }
    return i18n.t('metrics.cards.frontendMetrics.values.stageWithQualifier', { label: baseLabel, qualifier });
};

const buildTelemetryLastEventValue = (event: TelemetryEvent | null, formatter: MetricsFormatter): string => {
    if (!event) {
        return i18n.t('metrics.cards.frontendMetrics.values.lastEventNone');
    }
    const labelSource = isString(event.stage) ? resolveTelemetryStageLabel(event.stage) : event.message;
    const label = labelSource && isString(labelSource) && labelSource.trim() ? labelSource : formatter.unknownLabel();
    const formattedTime = formatter.relativeTime(event.timestamp);
    if (formattedTime) {
        return i18n.t('metrics.cards.frontendMetrics.values.lastEvent', { label, time: formattedTime });
    }
    return i18n.t('metrics.cards.frontendMetrics.values.lastEventNoTime', { label });
};

const resolveLastEventSeverityValue = (event: TelemetryEvent | null): string => {
    if (!event || !isString(event.severity)) {
        return i18n.t('metrics.cards.frontendMetrics.values.none');
    }
    const normalized = event.severity.trim().toLowerCase();
    switch (normalized) {
        case 'debug':
            return i18n.t('metrics.cards.frontendMetrics.values.debug');
        case 'info':
            return i18n.t('metrics.cards.frontendMetrics.values.info');
        case 'warn':
            return i18n.t('metrics.cards.frontendMetrics.values.warn');
        case 'error':
            return i18n.t('metrics.cards.frontendMetrics.values.error');
        case 'fatal':
            return i18n.t('metrics.cards.frontendMetrics.values.fatal');
        default:
            return i18n.t('metrics.cards.frontendMetrics.values.unknown');
    }
};

const resolveConnectionMetricValue = (metric: TelemetryMetric | null): ConnectionMetricValue | null => {
    const candidate = metric?.value;
    if (!isObject(candidate)) {
        return null;
    }
    return 'connected' in candidate || 'stage' in candidate || 'restartSubscribers' in candidate || 'holds' in candidate ? candidate : null;
};

const resolveQueueMetricValue = (metric: TelemetryMetric | null): QueueMetricValue | null => {
    const candidate = metric?.value;
    if (!isObject(candidate)) {
        return null;
    }
    return 'depth' in candidate || 'subscribers' in candidate ? candidate : null;
};

const buildFrontendTelemetryCardValues = (inputArguments: BuildFrontendTelemetryCardValuesArguments): FrontendTelemetryCardValues => {
    const pendingLabel = inputArguments.formatter.pendingLabel();
    const connectionValue = resolveConnectionMetricValue(inputArguments.connection);
    const latencyMetricValue = inputArguments.latency?.value ?? null;
    const queueMetricValue = inputArguments.queue?.value ?? null;
    const queueMetricObject = resolveQueueMetricValue(inputArguments.queue);
    const connected = connectionValue && isBoolean(connectionValue['connected']) ? connectionValue['connected'] : null;
    const stage = connectionValue && isString(connectionValue['stage']) ? connectionValue['stage'] : null;
    const subscribers =
        queueMetricObject && isFiniteNumber(queueMetricObject['subscribers'])
            ? Number(queueMetricObject['subscribers'])
            : queueMetricObject && isString(queueMetricObject['subscribers'])
              ? queueMetricObject['subscribers']
              : (() => {
                    const metadata = inputArguments.queue?.metadata ?? inputArguments.queue?.meta ?? null;
                    return metadata?.subscribers ?? null;
                })();
    const restartSubscribers = connectionValue && isFiniteNumber(connectionValue['restartSubscribers']) ? connectionValue['restartSubscribers'] : null;
    const connectionHolds = connectionValue && isFiniteNumber(connectionValue['holds']) ? connectionValue['holds'] : null;
    const latency = isFiniteNumber(latencyMetricValue) && latencyMetricValue >= 0 ? latencyMetricValue : null;
    const queueDepth = queueMetricObject && isFiniteNumber(queueMetricObject['depth']) ? Number(queueMetricObject['depth']) : isFiniteNumber(queueMetricValue) ? Number(queueMetricValue) : null;
    const throttle = inputArguments.status && isFiniteNumber(inputArguments.status.throttleMs) ? inputArguments.status.throttleMs : null;
    const pendingEvents = inputArguments.status && isFiniteNumber(inputArguments.status.pendingEvents) ? inputArguments.status.pendingEvents : null;
    const pendingMetrics = inputArguments.status && isFiniteNumber(inputArguments.status.pendingMetrics) ? inputArguments.status.pendingMetrics : null;
    const sinks = filterNonEmptyStringArrayValue(inputArguments.status?.sinks);
    return {
        connection: resolveConnectionValueLabel(connected),
        latency: inputArguments.formatter.ms(latency, pendingLabel),
        stage: resolveTelemetryStageLabel(stage),
        subscribers: inputArguments.formatter.number(subscribers, pendingLabel),
        restartSubscribers: inputArguments.formatter.number(restartSubscribers, pendingLabel),
        connectionHolds: inputArguments.formatter.number(connectionHolds, pendingLabel),
        queue: isFiniteNumber(queueDepth) && queueDepth >= 0 ? inputArguments.formatter.number(queueDepth, pendingLabel) : pendingLabel,
        throttle:
            throttle !== null
                ? i18n.t('metrics.cards.frontendMetrics.values.throttle', {
                      ms: inputArguments.formatter.number(throttle, inputArguments.formatter.unknownLabel())
                  })
                : inputArguments.formatter.unknownLabel(),
        pendingEvents: inputArguments.formatter.number(pendingEvents, pendingLabel),
        pendingMetrics: inputArguments.formatter.number(pendingMetrics, pendingLabel),
        sinks: sinks.length
            ? i18n.t('metrics.cards.frontendMetrics.values.sinks', {
                  count: inputArguments.formatter.number(sinks.length, '0'),
                  list: inputArguments.formatter.list(sinks)
              })
            : i18n.t('metrics.cards.frontendMetrics.values.none'),
        lastEvent: buildTelemetryLastEventValue(inputArguments.lastEvent, inputArguments.formatter),
        lastEventSeverity: resolveLastEventSeverityValue(inputArguments.lastEvent),
        lastEventModule: inputArguments.lastEvent && isString(inputArguments.lastEvent.module) && inputArguments.lastEvent.module.trim() ? inputArguments.lastEvent.module.trim() : i18n.t('metrics.cards.frontendMetrics.values.none'),
        status: resolveFrontendTelemetryStatusLabel(inputArguments.status?.state ?? null)
    };
};

export { buildFrontendTelemetryCardValues };
export type { FrontendTelemetryCardValues, TelemetryEvent, TelemetryMetric, TelemetryStatus };
