/* SoAI - Shared telemetry internal contracts [frontend/assets/ts/core/telemetry/internalContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryBatch, TelemetryFields, TelemetryMetric, TelemetryEvent, TelemetryValue } from '@core/telemetry/contracts.ts';

interface SinkEntry {
    handler: (batch: TelemetryBatch, state: TelemetryFields) => void;
    options: {
        includeMetrics: boolean;
        debugOnly: boolean;
    };
    state: TelemetryFields;
}

interface ConsoleSinkState {
    error?: (prefix: string, message: string, data?: TelemetryValue) => void;
    warn?: (prefix: string, message: string, data?: TelemetryValue) => void;
    debug?: (prefix: string, message: string, data?: TelemetryValue) => void;
    log?: (prefix: string, message: string, data?: TelemetryValue) => void;
}

interface FailureReporter {
    (context: string, error: Error): void;
}

interface TelemetryState {
    sinks: Map<string, SinkEntry>;
    eventListeners: Set<(event: TelemetryEvent) => void>;
    metricListeners: Map<string, Set<(metric: TelemetryMetric) => void>>;
    wildcardMetricListeners: Set<(metric: TelemetryMetric) => void>;
    metrics: Map<string, TelemetryMetric>;
    eventQueue: TelemetryEvent[];
    metricQueue: Map<string, TelemetryMetric>;
    throttleMs: number;
    flushTimer: ReturnType<typeof setTimeout> | null;
    eventSequence: number;
    suppressedNotifications: number;
    failureReporter: FailureReporter | null;
    consoleSinkRegistered: boolean;
}

export type { SinkEntry, ConsoleSinkState, FailureReporter, TelemetryState };
