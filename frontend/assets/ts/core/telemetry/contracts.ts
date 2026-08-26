/* SoAI - Shared telemetry contracts [frontend/assets/ts/core/telemetry/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type Severity = 'debug' | 'info' | 'warn' | 'error' | 'fatal';

interface TelemetryFields {
    [key: string]: TelemetryValue;
}

type TelemetryValue = JsonValue | Error | WeakKey | bigint | symbol | undefined | void;

interface TelemetryEventInput {
    message?: string | undefined;
    module?: string | undefined;
    severity?: string | undefined;
    level?: string | undefined;
    timestamp?: number | undefined;
    stage?: string | undefined;
    duration?: number | undefined;
    data?: TelemetryValue | undefined;
    details?: TelemetryValue | undefined;
    context?: TelemetryFields | undefined;
    tags?: string[] | undefined;
    attempt?: number | undefined;
    maxAttempts?: number | undefined;
    queueDepth?: number | undefined;
}

interface TelemetryEvent {
    id: number;
    timestamp: number;
    severity: Severity;
    module: string;
    message: string;
    stage: string | null;
    duration: number | null;
    data: TelemetryValue;
    context: TelemetryFields | null;
    tags: string[];
    attempt: number | null;
    maxAttempts: number | null;
    queueDepth: number | null;
}

interface TelemetryMetric {
    name: string;
    value: TelemetryValue;
    meta: TelemetryFields;
    timestamp: number;
}

interface TelemetryBatch {
    events: TelemetryEvent[];
    metrics: TelemetryMetric[];
}

interface SinkOptions {
    includeMetrics?: boolean;
    debugOnly?: boolean;
    state?: TelemetryFields;
}

type EventListener = (event: TelemetryEvent) => void;

type MetricListener = (metric: TelemetryMetric) => void;

interface TelemetryStatus {
    pendingEvents: number;
    pendingMetrics: number;
    throttleMs: number;
    sinks: string[];
}

interface TelemetryService {
    emit: (input: TelemetryEventInput | string) => TelemetryEvent;
    registerSink: (name: string, handler: (batch: TelemetryBatch, state: TelemetryFields) => void, options?: SinkOptions) => () => boolean;
    unregisterSink: (name: string) => boolean;
    subscribe: (listener: EventListener) => () => void;
    setThrottle: (value: number) => number;
    publishMetric: (name: string, value: TelemetryValue, meta?: TelemetryFields) => TelemetryMetric;
    observeMetric: (name: string | null, listener: MetricListener) => () => void;
    getMetric: (name: string) => TelemetryMetric | null;
    getMetrics: () => TelemetryMetric[];
    getStatus: () => TelemetryStatus;
}

export type { Severity, TelemetryEvent, TelemetryEventInput, TelemetryBatch, TelemetryFields, TelemetryMetric, TelemetryService, TelemetryStatus, TelemetryValue, EventListener, MetricListener, SinkOptions };
