/* SoAI - Logging feature log stream service events [frontend/assets/ts/features/logging/logstreamservice/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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

const closeStreamSubscriptionHandle = (handle: StreamSubscriptionHandle | null, streamManager: StreamManagerWithLogs | null): void => {
    if (handle) {
        if (isFunction(handle.unsubscribe)) {
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

const teardownStreamConnection = (context: Pick<StreamConnectionContext, 'state' | 'clearTimer'>, handle: StreamSubscriptionHandle | null, streamManager: StreamManagerWithLogs | null): void => {
    if (context.state.teardownInProgress) {
        return;
    }
    context.state.teardownInProgress = true;
    try {
        context.state.connectionHandle = null;
        context.state.isConnected = false;
        clearReconnectNotice(context);
        context.state.connectionStartedAt = 0;
        closeStreamSubscriptionHandle(handle, streamManager);
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
            void context.ensureConnection().catch((error) => {
                if (context.state.recoverySuspended) {
                    return;
                }
                context.logger.logError('Reconnection failed', error);
            });
        }
    }, RECONNECT_NOTICE_DELAY_MS);
};

const handleStreamClosed = (context: StreamConnectionContext): void => {
    if (context.state.connectionGeneration !== context.connectionGeneration) {
        return;
    }
    context.state.isConnected = false;
    clearReconnectNotice(context);
    context.state.connectionHandle = null;
    context.state.connectPromise = null;
    context.publishMetric('logs.stream.closed', 1, { source: context.state.snapshotMeta.source });
    if (context.state.recoverySuspended) {
        return;
    }
    if (!context.state.teardownInProgress && context.state.subscribers.size > 0) {
        scheduleReconnectNotice(context);
        return;
    }
    if (context.state.subscribers.size === 0) {
        context.teardownConnection();
    }
};

const handleStreamError = (context: StreamConnectionContext, error: Error): void => {
    if (context.state.connectionGeneration !== context.connectionGeneration) {
        return;
    }
    context.state.isConnected = false;
    clearReconnectNotice(context);
    context.state.connectionHandle = null;
    context.state.connectPromise = null;
    context.state.connectionStartedAt = 0;
    if (context.state.recoverySuspended) {
        return;
    }
    if (context.state.subscribers.size === 0) {
        context.teardownConnection();
        return;
    }
    context.publishMetric('logs.stream.error', 1, { source: context.state.snapshotMeta.source });
    context.logger.logWarn('Stream error', error);
    context.notify({ type: 'connection', status: 'error' });
    scheduleReconnectNotice(context);
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
