/* SoAI - Logging feature log stream service actions [frontend/assets/ts/features/logging/logstreamservice/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { coerceErrorMessage, ensureError } from '@core/errors/coerce.ts';
import type { TelemetryFields, TelemetryValue } from '@core/telemetry/contracts.ts';
import type { LogDataValidator } from '@core/logvalidation/public.ts';
import type { LogEntry } from '@core/logNormalization.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { isArray, isFunction, isNullOrUndefined } from '@core/typeGuards.ts';
import { DEFAULT_REPLAY_LIMIT, MAX_BUFFER_SIZE } from '@features/logging/logstreamservice/constants.ts';
import type { LogEvent, LogStreamEvent, LogStreamListener, SnapshotMeta, SnapshotPayload } from '@features/logging/logstreamservice/types.ts';

interface LogStreamSubscriberState {
    subscribers: Map<LogStreamListener, number>;
    replayedSubscribers: Set<LogStreamListener>;
    logBuffer: LogEntry[];
    sharedSnapshotEntries: LogEntry[];
    snapshotMeta: SnapshotMeta;
    currentBufferSize: number;
}

interface LogStreamLogger {
    logError: (message: string, detail?: TelemetryValue) => void;
    logWarn: (message: string, detail?: TelemetryValue) => void;
    logDebug: (message: string, detail?: TelemetryValue) => void;
}

const cloneLogEntry = (entry: LogEntry): LogEntry => {
    return Object.freeze({ ...entry });
};

const cloneLogStreamEvent = (event: LogStreamEvent, source: string): LogStreamEvent => {
    if (event.type === 'log') {
        return { ...event, source, entry: { ...event.entry } };
    }
    if (event.type === 'history') {
        return { ...event, source, entries: event.entries.map((entry) => ({ ...entry })) };
    }
    return { ...event, source };
};

const updateBufferFromResolved = (state: LogStreamSubscriberState, resolved: SnapshotPayload): void => {
    state.logBuffer = resolved.entries.slice(-MAX_BUFFER_SIZE);
    state.sharedSnapshotEntries = state.logBuffer.map((entry) => cloneLogEntry(entry));
    const size = Math.min(resolved.entries.length, MAX_BUFFER_SIZE);
    if (size > state.currentBufferSize) {
        state.currentBufferSize = size;
    }
    state.snapshotMeta = { source: resolved.source, limit: resolved.limit, receivedAt: resolved.receivedAt };
};

const safeNotifySubscriber = (callback: LogStreamListener, event: LogStreamEvent, logger: LogStreamLogger, publishMetric: (metric: string, value: number, tags: TelemetryFields) => void, source: string): void => {
    try {
        callback(event);
    } catch (error) {
        const runtimeError = ensureError(error);
        logger.logWarn('Subscriber callback threw error', runtimeError);
        publishMetric('logs.stream.subscriberError', 1, { eventType: event.type, source });
    }
};

const notifySubscribers = (state: LogStreamSubscriberState, event: LogStreamEvent, logger: LogStreamLogger, publishMetric: (metric: string, value: number, tags: TelemetryFields) => void): void => {
    state.subscribers.forEach((_unusedValue, callback) => {
        const source = event.source ?? state.snapshotMeta.source;
        const payload = cloneLogStreamEvent(event, source);
        safeNotifySubscriber(callback, payload, logger, publishMetric, state.snapshotMeta.source);
    });
};

const notifySubscribersBatch = (state: LogStreamSubscriberState, events: LogStreamEvent[], logger: LogStreamLogger, publishMetric: (metric: string, value: number, tags: TelemetryFields) => void): void => {
    if (!isArray(events) || events.length === 0) {
        return;
    }
    state.subscribers.forEach((_unusedValue, callback) => {
        events.forEach((event) => {
            const source = event.source ?? state.snapshotMeta.source;
            const payload = cloneLogStreamEvent(event, source);
            safeNotifySubscriber(callback, payload, logger, publishMetric, state.snapshotMeta.source);
        });
    });
};

const validateReplayLimit = (validator: LogDataValidator, limit: number | undefined, logger: Pick<LogStreamLogger, 'logError'>): number => {
    if (isNullOrUndefined(limit)) {
        return DEFAULT_REPLAY_LIMIT;
    }
    const result = validator.validateReplayLimit(limit);
    if (!result.valid) {
        const message = coerceErrorMessage(result.error, 'Unknown validation error');
        logger.logError(`Invalid replay limit: ${message}`, result.error === undefined ? undefined : ensureError(result.error));
        return DEFAULT_REPLAY_LIMIT;
    }
    return result.limit;
};

const replayBufferToSubscriber = (state: Pick<LogStreamSubscriberState, 'logBuffer' | 'snapshotMeta'>, callback: LogStreamListener, limit: number): void => {
    if (!isFunction(callback)) {
        throw new Error('Replay callback must be a function');
    }
    const validatedLimit = clampNumber(limit, 1, MAX_BUFFER_SIZE);
    const start = Math.max(0, state.logBuffer.length - validatedLimit);
    const slice = state.logBuffer.slice(start);
    slice.forEach((entry) => {
        callback({ type: 'log', entry: { ...entry }, source: state.snapshotMeta.source, mode: 'replay' });
    });
    callback({
        type: 'snapshot',
        status: 'replay-complete',
        total: slice.length,
        limit: validatedLimit,
        source: state.snapshotMeta.source
    });
};

const addEntryToBuffer = (state: Pick<LogStreamSubscriberState, 'logBuffer' | 'sharedSnapshotEntries' | 'currentBufferSize'>, entry: LogEntry | null | undefined, validator: LogDataValidator, logger: Pick<LogStreamLogger, 'logError'>, onBufferChanged: () => void): void => {
    if (!entry) {
        logger.logError('Cannot add null or undefined to buffer');
        return;
    }
    const validation = validator.validateLogEntry(entry);
    if (!validation.valid) {
        logger.logError(`Invalid log entry: ${validation.errors.join(', ')}`);
        return;
    }
    state.logBuffer.push(entry);
    state.sharedSnapshotEntries.push(cloneLogEntry(entry));
    if (state.logBuffer.length > state.currentBufferSize) {
        const excess = state.logBuffer.length - state.currentBufferSize;
        state.logBuffer.splice(0, excess);
        state.sharedSnapshotEntries.splice(0, excess);
    }
    onBufferChanged();
};

const updateCurrentBufferSize = (state: Pick<LogStreamSubscriberState, 'subscribers' | 'currentBufferSize' | 'logBuffer' | 'sharedSnapshotEntries'>, ensureHistoricalCoverage: (targetLimit: number) => Promise<void>, onBufferChanged: () => void): void => {
    if (state.subscribers.size === 0) {
        state.currentBufferSize = DEFAULT_REPLAY_LIMIT;
        return;
    }
    const maxLimit = Math.max(...Array.from(state.subscribers.values()));
    state.currentBufferSize = Math.min(maxLimit, MAX_BUFFER_SIZE);

    if (state.logBuffer.length > state.currentBufferSize) {
        const excess = state.logBuffer.length - state.currentBufferSize;
        state.logBuffer.splice(0, excess);
        state.sharedSnapshotEntries.splice(0, excess);
    }
    if (state.logBuffer.length < state.currentBufferSize) {
        terminateHandledPromise(ensureHistoricalCoverage(state.currentBufferSize));
    }
    onBufferChanged();
};

const toLogEvent = (entry: LogEntry, source: string, mode: string | null): LogEvent => {
    const event: LogEvent = { type: 'log', entry, source };
    if (mode === 'history' || mode === 'replay') {
        event.mode = mode;
    }
    return event;
};

export { addEntryToBuffer, cloneLogEntry, notifySubscribers, notifySubscribersBatch, replayBufferToSubscriber, toLogEvent, updateBufferFromResolved, updateCurrentBufferSize, validateReplayLimit };
export type { LogStreamLogger, LogStreamSubscriberState };
