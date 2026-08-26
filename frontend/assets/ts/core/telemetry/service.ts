/* SoAI - Shared telemetry service [frontend/assets/ts/core/telemetry/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { emit, getMetric, getMetrics, getStatus, observeMetric, publishMetric, registerSink, setFailureReporter, setThrottle, subscribe, unregisterSink } from '@core/telemetry/actions.ts';
import { ensureConsoleSink } from '@core/telemetry/effects.ts';
import { getTelemetryState } from '@core/telemetry/state.ts';
import type { EventListener, MetricListener, SinkOptions, TelemetryBatch, TelemetryEvent, TelemetryEventInput, TelemetryFields, TelemetryMetric, TelemetryService, TelemetryStatus, TelemetryValue } from '@core/telemetry/contracts.ts';
import type { TelemetryState } from '@core/telemetry/internalContracts.ts';

const createTelemetryService = (state: TelemetryState): TelemetryService => {
    return Object.freeze({
        emit: (input: TelemetryEventInput | string): TelemetryEvent => emit(state, ensureConsoleSink, input),
        registerSink: (name: string, handler: (batch: TelemetryBatch, sinkState: TelemetryFields) => void, options?: SinkOptions): (() => boolean) => registerSink(state, name, handler, options),
        unregisterSink: (name: string): boolean => unregisterSink(state, name),
        subscribe: (listener: EventListener): (() => void) => subscribe(state, listener),
        setThrottle: (value: number): number => setThrottle(state, value),
        publishMetric: (name: string, value: TelemetryValue, meta?: TelemetryFields): TelemetryMetric => publishMetric(state, name, value, meta ?? {}),
        observeMetric: (name: string | null, listener: MetricListener): (() => void) => observeMetric(state, name, listener),
        getMetric: (name: string): TelemetryMetric | null => getMetric(state, name),
        getMetrics: (): TelemetryMetric[] => getMetrics(state),
        getStatus: (): TelemetryStatus => getStatus(state)
    });
};

const telemetry = createTelemetryService(getTelemetryState());

const setTelemetryFailureReporter = (reporter: ((context: string, error: Error) => void) | null): void => {
    setFailureReporter(getTelemetryState(), reporter);
};

export { telemetry, setTelemetryFailureReporter };
