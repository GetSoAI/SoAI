/* SoAI - Shared telemetry events [frontend/assets/ts/core/telemetry/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { TelemetryBatch, TelemetryEvent, TelemetryMetric } from '@core/telemetry/contracts.ts';
import type { TelemetryState } from '@core/telemetry/internalContracts.ts';
import { reportFailure } from '@core/telemetry/mappers.ts';
import { ensureError } from '@core/errors/coerce.ts';

const notifyEventListeners = (state: TelemetryState, event: TelemetryEvent): void => {
    if (!state.eventListeners.size) {
        return;
    }
    state.eventListeners.forEach((listener) => {
        try {
            listener(event);
        } catch (error) {
            const runtimeError = ensureError(error);
            reportFailure(state, 'Listener failed', runtimeError);
        }
    });
};

const notifyMetricListeners = (state: TelemetryState, metric: TelemetryMetric): void => {
    const scoped = state.metricListeners.get(metric.name);
    if (scoped) {
        scoped.forEach((listener) => {
            try {
                listener(metric);
            } catch (error) {
                const runtimeError = ensureError(error);
                reportFailure(state, 'Metric listener failed', runtimeError);
            }
        });
    }
    if (!state.wildcardMetricListeners.size) {
        return;
    }

    state.wildcardMetricListeners.forEach((listener) => {
        try {
            listener(metric);
        } catch (error) {
            const runtimeError = ensureError(error);
            reportFailure(state, 'Metric listener failed', runtimeError);
        }
    });
};

const flush = (state: TelemetryState): void => {
    const events = state.eventQueue.splice(0, state.eventQueue.length);
    const metrics = Array.from(state.metricQueue.values());
    state.metricQueue.clear();
    if (!events.length && !metrics.length) {
        return;
    }
    state.sinks.forEach((sink) => {
        try {
            const includeMetrics = sink.options.includeMetrics === true;
            const batch: TelemetryBatch = {
                events,
                metrics: includeMetrics ? metrics : []
            };
            sink.handler(batch, sink.state);
        } catch (error) {
            const runtimeError = ensureError(error);
            reportFailure(state, 'Sink failed', runtimeError);
        }
    });
};

const scheduleFlush = (state: TelemetryState): void => {
    if (state.flushTimer !== null) {
        return;
    }
    state.flushTimer = setTimeout(() => {
        state.flushTimer = null;
        flush(state);
    }, state.throttleMs);
};

export { notifyEventListeners, notifyMetricListeners, flush, scheduleFlush };
