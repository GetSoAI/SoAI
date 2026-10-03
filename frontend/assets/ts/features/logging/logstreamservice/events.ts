/* SoAI - Logging feature log stream service events [frontend/assets/ts/features/logging/logstreamservice/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LogStreamError } from '@core/realtime/streammanager/transport/logStreamError.ts';
import { APIError, isNetworkError } from '@core/apiError.ts';
import { shouldReportReconnectAttempt } from '@core/websocketclient/WebSocketReconnectScheduler.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isFunction, isObject } from '@core/typeGuards.ts';
import type { TelemetryFields } from '@core/telemetry/contracts.ts';
import { getNow, RECONNECT_NOTICE_DELAY_MS } from '@features/logging/logstreamservice/constants.ts';
import { type LogStreamLogger } from '@features/logging/logstreamservice/actions.ts';
import { normalizeStreamEventType, normalizeStreamMessage } from '@features/logging/logstreamservice/mappers.ts';
import { handleLogBatch, handleSingleLogLine, type StreamUpdateContext } from '@features/logging/logstreamservice/streamUpdateHandlers.ts';
import type { LogStreamEvent, StreamManagerWithLogs, StreamSubscriptionHandle } from '@features/logging/logstreamservice/types.ts';
import type { LogStreamMutableState } from '@features/logging/logstreamservice/state.ts';

interface StreamConnectionContext {
    state: LogStreamMutableState;
    connectionGeneration: number;
    logger: LogStreamLogger;
    publishMetric: (metric: string, value: number, tags: TelemetryFields) => void;
    notify: (event: LogStreamEvent) => void;
    teardownConnection: () => void;
    ensureConnection: () => Promise<StreamSubscriptionHandle | null>;
    clearTimer: (timerId: number | null | undefined) => void;
    setTimer: (callback: () => void, delayMs: number) => number | null;
}

const clearReconnectNotice = (context: Pick<StreamConnectionContext, 'state' | 'clearTimer'>): void => {
    if (context.state.reconnectNoticeTimerId !== null) {
        context.clearTimer(context.state.reconnectNoticeTimerId);
        context.state.reconnectNoticeTimerId = null;
    }
};

const closeStreamSubscriptionHandle = (handle: StreamSubscriptionHandle | null, streamManager: StreamManagerWithLogs | null, detachOnly = false): void => {
    if (handle) {
        if (detachOnly && isFunction(handle.detach)) {
            handle.detach();
        } else if (isFunction(handle.unsubscribe)) {
            handle.unsubscribe();
        } else if (isFunction(handle.close)) {
            handle.close();
        } else if (isFunction(handle.abort)) {
            handle.abort();
        } else if (streamManager) {
            streamManager.subscriptions.unsubscribe(handle);
        }
    }
};

const teardownStreamConnection = (context: Pick<StreamConnectionContext, 'state' | 'clearTimer'>, handle: StreamSubscriptionHandle | null, streamManager: StreamManagerWithLogs | null, detachOnly = false): void => {
    if (context.state.teardownInProgress) {
        return;
    }
    context.state.teardownInProgress = true;
    try {
        context.state.connectionGeneration += 1;
        context.state.connectionAbort?.abort();
        context.state.connectionAbort = null;
        context.state.connectPromise = null;
        context.state.recovery.cancel();
        context.state.connectionHandle = null;
        context.state.isConnected = false;
        clearReconnectNotice(context);
        context.state.connectionStartedAt = 0;
        closeStreamSubscriptionHandle(handle, streamManager, detachOnly);
    } finally {
        context.state.teardownInProgress = false;
    }
};

const handleStreamOpen = (context: StreamConnectionContext): void => {
    if (context.state.connectionGeneration !== context.connectionGeneration) {
        return;
    }
    if (context.state.recoverySuspended) {
        context.teardownConnection();
        return;
    }
    if (context.state.subscribers.size === 0) {
        context.teardownConnection();
        return;
    }
    context.state.recoveryStopped = false;
    context.state.recovery.markHealthy();
    context.state.isConnected = true;
    clearReconnectNotice(context);
    if (context.state.connectionStartedAt) {
        const duration = getNow() - context.state.connectionStartedAt;
        context.state.connectionStartedAt = 0;
        context.publishMetric('logs.stream.connectDuration', duration, { source: context.state.snapshotMeta.source });
    }
    context.notify({ type: 'connection', status: 'connected' });
};

const scheduleReconnectNotice = (context: StreamConnectionContext): void => {
    if (context.state.recoverySuspended || context.state.subscribers.size === 0 || context.state.reconnectNoticeTimerId !== null) {
        return;
    }
    context.state.reconnectNoticeTimerId = context.setTimer(() => {
        context.state.reconnectNoticeTimerId = null;
        if (context.state.subscribers.size > 0 && !context.state.isConnected) {
            context.publishMetric('logs.stream.reconnectNotice', 1, { source: context.state.snapshotMeta.source });
            context.notify({ type: 'connection', status: 'reconnecting' });
        }
    }, RECONNECT_NOTICE_DELAY_MS);
};

const scheduleRecovery = (context: StreamConnectionContext, error?: Error): void => {
    const state = context.state;
    const eligible = (): boolean => !state.recoverySuspended && !state.recoveryStopped && state.subscribers.size > 0 && !state.connectionHandle && !state.connectPromise;
    state.recovery.setLiveDemand(state.subscribers.size > 0 && !state.recoverySuspended);
    const scheduled = state.recovery.scheduled;
    state.recovery.schedule(eligible, () => terminateHandledPromise(context.ensureConnection()));
    if (!scheduled && state.recovery.scheduled && error && shouldReportReconnectAttempt(state.recovery.attemptCount)) context.logger.logWarn('Log stream recovery scheduled', error);
    if (eligible()) scheduleReconnectNotice(context);
};

const handleStreamClosed = (context: StreamConnectionContext): void => {
    if (context.state.connectionGeneration !== context.connectionGeneration) return;
    teardownStreamConnection(context, context.state.connectionHandle, context.state.streamManager, true);
    context.state.recoveryStopped = false;
    context.publishMetric('logs.stream.closed', 1, { source: context.state.snapshotMeta.source });
    scheduleRecovery(context);
};

const handleStreamError = (context: StreamConnectionContext, error: Error): void => {
    const state = context.state;
    if (state.connectionGeneration !== context.connectionGeneration) return;
    if (state.recoverySuspended || state.subscribers.size === 0) {
        context.teardownConnection();
        return;
    }
    const awaitingConnection = error instanceof LogStreamError && error.recovery === 'await-connection';
    const retryable = error instanceof LogStreamError ? error.recovery === 'retry' : isNetworkError(error) || (error instanceof APIError && error.status >= 500);
    if (!awaitingConnection) teardownStreamConnection(context, state.connectionHandle, state.streamManager, true);
    state.isConnected = false;
    state.recoveryStopped = !retryable;
    context.publishMetric('logs.stream.error', 1, { source: state.snapshotMeta.source });
    const generation = state.connectionGeneration;
    context.notify({ type: 'connection', status: 'error' });
    if (generation !== state.connectionGeneration || state.subscribers.size === 0 || state.recoverySuspended) return;
    if (retryable) scheduleRecovery(context, error);
    else context.logger.logWarn('Log stream unavailable', error);
};

const handleStreamUpdate = (context: StreamUpdateContext, payload: JsonValue | null | undefined, type: JsonValue | null | undefined, raw: JsonValue | null | undefined): void => {
    const message = normalizeStreamMessage(payload, type, raw);
    if (!message) {
        return;
    }
    const normalizedType = normalizeStreamEventType(message.type);
    if (normalizedType === 'logbatch') {
        const payloadValue = message.payload;
        const entries = payloadValue?.['entries'];
        if (!isArray(entries)) {
            context.logger.logWarn('Received log batch without entries array', message.payload);
            return;
        }
        handleLogBatch(context, entries, payloadValue?.['source'], payloadValue?.['mode']);
        return;
    }
    if (normalizedType === 'logline') {
        if (!message.payload || !isObject(message.payload)) {
            context.logger.logDebug('Invalid logline payload');
            return;
        }
        handleSingleLogLine(context, message.payload);
        return;
    }
    if (message.payload?.['entry'] !== undefined) {
        handleSingleLogLine(context, message.payload);
    }
};

export { clearReconnectNotice, closeStreamSubscriptionHandle, handleStreamClosed, handleStreamError, handleStreamOpen, handleStreamUpdate, scheduleReconnectNotice, teardownStreamConnection };
export type { StreamConnectionContext, StreamUpdateContext };
