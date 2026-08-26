/* SoAI - Shared telemetry actions [frontend/assets/ts/core/telemetry/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber, isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { EventListener, MetricListener, SinkOptions, TelemetryBatch, TelemetryEvent, TelemetryEventInput, TelemetryFields, TelemetryMetric, TelemetryValue } from '@core/telemetry/contracts.ts';
import type { TelemetryState } from '@core/telemetry/internalContracts.ts';
import { notifyEventListeners, notifyMetricListeners, scheduleFlush } from '@core/telemetry/events.ts';
import { normalizeEvent } from '@core/telemetry/mappers.ts';

const registerSink = (state: TelemetryState, name: string, handler: (batch: TelemetryBatch, sinkState: TelemetryFields) => void, options: SinkOptions = {}): (() => boolean) => {
    if (!isString(name) || !name.trim()) {
        throw new Error('Telemetry sink requires a name');
    }
    if (!isFunction(handler)) {
        throw new Error('Telemetry sink requires a handler');
    }
    const key = name.trim();
    state.sinks.set(key, {
        handler,
        options: {
            includeMetrics: options.includeMetrics === true,
            debugOnly: options.debugOnly === true
        },
        state: options.state && isObject(options.state) ? { ...options.state } : {}
    });
    return () => unregisterSink(state, key);
};

const unregisterSink = (state: TelemetryState, name: string): boolean => {
    if (!isString(name) || !name.trim()) {
        return false;
    }
    return state.sinks.delete(name.trim());
};

const emit = (state: TelemetryState, ensureSinkRegistration: (state: TelemetryState) => void, input: TelemetryEventInput | string): TelemetryEvent => {
    ensureSinkRegistration(state);
    const event = normalizeEvent(state, input);
    state.eventQueue.push(event);
    if (state.suppressedNotifications === 0) {
        notifyEventListeners(state, event);
    }
    scheduleFlush(state);
    return event;
};

const subscribe = (state: TelemetryState, listener: EventListener): (() => void) => {
    if (!isFunction(listener)) {
        return () => {};
    }
    state.eventListeners.add(listener);
    return () => {
        state.eventListeners.delete(listener);
    };
};

const setThrottle = (state: TelemetryState, value: number): number => {
    if (!isFiniteNumber(value) || value < 0) {
        return state.throttleMs;
    }
    state.throttleMs = value;
    if (state.flushTimer !== null) {
        clearTimeout(state.flushTimer);
        state.flushTimer = null;
        if (state.eventQueue.length || state.metricQueue.size) {
            scheduleFlush(state);
        }
    }
    return state.throttleMs;
};

const publishMetric = (state: TelemetryState, name: string, value: TelemetryValue, meta: TelemetryFields = {}): TelemetryMetric => {
    if (!isString(name) || !name.trim()) {
        throw new Error('Telemetry metric requires a name');
    }
    const key = name.trim();
    const metric: TelemetryMetric = {
        name: key,
        value,
        meta: isObject(meta) ? { ...meta } : {},
        timestamp: Date.now()
    };
    state.metrics.set(key, metric);
    state.metricQueue.set(key, metric);
    notifyMetricListeners(state, metric);
    scheduleFlush(state);
    return metric;
};

const observeMetric = (state: TelemetryState, name: string | null, listener: MetricListener): (() => void) => {
    if (!isFunction(listener)) {
        return () => {};
    }
    if (isString(name) && name.trim()) {
        const key = name.trim();
        let listeners = state.metricListeners.get(key);
        if (!listeners) {
            listeners = new Set();
            state.metricListeners.set(key, listeners);
        }
        listeners.add(listener);
        return () => {
            const scoped = state.metricListeners.get(key);
            if (!scoped) {
                return;
            }
            scoped.delete(listener);
            if (!scoped.size) {
                state.metricListeners.delete(key);
            }
        };
    }
    state.wildcardMetricListeners.add(listener);
    return () => {
        state.wildcardMetricListeners.delete(listener);
    };
};

const getMetric = (state: TelemetryState, name: string): TelemetryMetric | null => {
    if (!isString(name) || !name.trim()) {
        return null;
    }
    return state.metrics.get(name.trim()) || null;
};

const getMetrics = (state: TelemetryState): TelemetryMetric[] => {
    return Array.from(state.metrics.values());
};

const getStatus = (
    state: TelemetryState
): {
    pendingEvents: number;
    pendingMetrics: number;
    throttleMs: number;
    sinks: string[];
} => {
    return {
        pendingEvents: state.eventQueue.length,
        pendingMetrics: state.metricQueue.size,
        throttleMs: state.throttleMs,
        sinks: Array.from(state.sinks.keys())
    };
};

const setFailureReporter = (state: TelemetryState, reporter: ((context: string, error: Error) => void) | null): void => {
    state.failureReporter = isFunction(reporter) ? reporter : null;
};

export { registerSink, unregisterSink, emit, subscribe, setThrottle, publishMetric, observeMetric, getMetric, getMetrics, getStatus, setFailureReporter };
