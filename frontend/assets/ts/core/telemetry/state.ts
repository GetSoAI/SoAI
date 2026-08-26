/* SoAI - Shared telemetry state [frontend/assets/ts/core/telemetry/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryState } from '@core/telemetry/internalContracts.ts';

const telemetryState: TelemetryState = {
    sinks: new Map(),
    eventListeners: new Set(),
    metricListeners: new Map(),
    wildcardMetricListeners: new Set(),
    metrics: new Map(),
    eventQueue: [],
    metricQueue: new Map(),
    throttleMs: 200,
    flushTimer: null,
    eventSequence: 0,
    suppressedNotifications: 0,
    failureReporter: null,
    consoleSinkRegistered: false
};

const getTelemetryState = (): TelemetryState => telemetryState;

export { getTelemetryState };
