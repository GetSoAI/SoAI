/* SoAI - Shared realtime log stream [frontend/assets/ts/core/realtime/streammanager/transport/logStream.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isJsonArray, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isObject, isPlainObject } from '@core/typeGuards.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_LIFECYCLE_EVENT_TYPES, WEBSOCKET_LOG_STREAM_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { CONNECTION_WAIT_TIMEOUT_MS, SNAPSHOT_TIMEOUT_MS } from '@core/websocketclient/constants.ts';
import { LogStreamError } from '@core/realtime/streammanager/transport/logStreamError.ts';
import { requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';

interface WebSocketClientContract {
    subscribe: (eventType: string, handler: (payload: JsonValue) => void | Promise<void>) => () => void;
    sendMessage: (payload: JsonObject, options?: { signal?: AbortSignal; waitForConnection?: boolean }) => Promise<void>;
    waitForConnection: (timeoutMs: number, options: { signal: AbortSignal }) => Promise<void>;
    isConnected: () => boolean;
    readonly connectionEpoch: number;
}

interface StreamLogHandlers {
    onOpen?: () => void;
    onUpdate?: (payload: JsonObject, eventType: string, raw: JsonValue) => void;
    onError?: (error: Error) => void;
    onClose?: () => void;
}

interface StreamLogsOptions {
    module: string;
    ws: WebSocketClientContract;
    source: string;
    handlers: StreamLogHandlers;
    safe: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void;
    historyLimit?: number;
}

const serializeLogStreamSubscription = (type: string, source: string, historyLimit?: number): JsonObject => {
    const serialized: JsonObject = { type, 'source_name': source };
    if (historyLimit !== undefined) serialized['history_limit'] = historyLimit;
    return serialized;
};

const streamLogs = (options: StreamLogsOptions): { unsubscribe: () => void; close: () => void; abort: () => void; detach: () => void } => {
    if (!isObject(options)) {
        throw new Error('streamLogs requires options');
    }
    const moduleName = options.module;
    const { ws, source } = options;
    const handlers = options.handlers;
    const safe = options.safe;

    const unsubscribers: Array<() => void> = [];
    let closed = false;
    let manualClose = false;
    let acknowledged = false;
    let subscriptionEpoch: number | null = null;
    const controller = new AbortController();
    const acknowledgementTimer = new TimeoutTimer(SNAPSHOT_TIMEOUT_MS, () => {
        if (!closed && !acknowledged) safe(handlers.onError, new LogStreamError('Log subscription acknowledgement timed out', 'await-connection'));
    });
    const safeClose = (): void => {
        if (closed) return;
        closed = true;
        controller.abort();
        acknowledgementTimer.stop();
        unsubscribers.splice(0, unsubscribers.length).forEach((callback) => {
            try {
                callback();
            } catch (error) {
                const err = ensureError(error);
                errorHandler.debug(moduleName, 'Log stream unsubscribe failed', err);
            }
        });
        if (!manualClose) safe(handlers.onClose);
    };
    const fail = (error: Error): void => {
        if (closed) return;
        manualClose = true;
        safeClose();
        safe(handlers.onError, error);
    };
    const matchesSource = (payload: JsonValue): string | null => {
        const record = isPlainObject(payload) ? payload : null;
        if (!record) return null;
        const sourceName = toTrimmedString(record['source_name']);
        return sourceName && sourceName === source ? sourceName : null;
    };
    const handleBatch = (payload: JsonValue): void => {
        const sourceName = matchesSource(payload);
        if (!sourceName || closed) return;
        const record = isPlainObject(payload) ? payload : null;
        if (!record) {
            fail(new LogStreamError('Log batch payload must be an object', 'stop'));
            return;
        }
        const entries = record['entries'];
        if (!isJsonArray(entries)) {
            fail(new LogStreamError('Log batch missing entries', 'stop'));
            return;
        }
        const mode = record['mode'];
        const updatePayload: JsonObject = {
            type: WEBSOCKET_EVENT_TYPES.LOG_BATCH,
            source: sourceName,
            entries,
            ...(isJsonValue(mode) ? { mode } : {})
        };
        safe(handlers.onUpdate, updatePayload, WEBSOCKET_EVENT_TYPES.LOG_BATCH, payload);
    };
    const handleSubscribed = (payload: JsonValue): void => {
        const sourceName = matchesSource(payload);
        if (!sourceName || closed) return;
        if (acknowledged) return;
        acknowledged = true;
        acknowledgementTimer.stop();
        safe(handlers.onOpen);
    };
    const handleClosed = (payload: JsonValue): void => {
        const sourceName = matchesSource(payload);
        if (!sourceName || closed || !acknowledged) return;
        safeClose();
    };
    const handleError = (payload: JsonValue): void => {
        if (closed || !isPlainObject(payload)) return;
        const detail = payload['error'];
        const details = isPlainObject(detail) && isPlainObject(detail['details']) ? detail['details'] : null;
        const sourceName = toTrimmedString(details?.['source_name']) || toTrimmedString(payload['source_name']);
        if (sourceName !== source) return;
        try {
            const record = requireRecord(detail, 'Log stream error');
            const code = readRequiredTrimmedStringValue(record['code'], 'Log stream error.code');
            const traceId = toTrimmedString(record['trace_id']) || null;
            const message = readRequiredTrimmedStringValue(payload['message'], 'Log stream error.message');
            fail(new LogStreamError(message, code === 'service_unavailable' || code === 'server_error' ? 'retry' : 'stop', traceId));
        } catch (error) {
            fail(new LogStreamError(ensureError(error).message, 'stop'));
        }
    };
    const handleStreamEvent = (eventType: string, payload: JsonValue): void => {
        switch (eventType) {
            case WEBSOCKET_EVENT_TYPES.LOG_BATCH:
                handleBatch(payload);
                return;
            case WEBSOCKET_EVENT_TYPES.LOG_STREAM_SUBSCRIBED:
                handleSubscribed(payload);
                return;
            case WEBSOCKET_EVENT_TYPES.LOG_STREAM_CLOSED:
            case WEBSOCKET_EVENT_TYPES.LOG_STREAM_UNSUBSCRIBED:
            case WEBSOCKET_EVENT_TYPES.LOG_STREAM_RECONFIGURED:
                handleClosed(payload);
                return;
            case WEBSOCKET_EVENT_TYPES.LOG_STREAM_ERROR:
                handleError(payload);
                return;
        }
    };

    unsubscribers.push(...WEBSOCKET_LOG_STREAM_EVENT_TYPES.map((eventType) => ws.subscribe(eventType, (payload) => handleStreamEvent(eventType, payload))));
    unsubscribers.push(
        ws.subscribe(WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED, () => {
            if (closed) return;
            safeClose();
        })
    );

    const historyLimit = typeof options.historyLimit === 'number' && Number.isInteger(options.historyLimit) && options.historyLimit > 0 ? options.historyLimit : undefined;
    const subscribePayload = serializeLogStreamSubscription(WEBSOCKET_MESSAGE_TYPES.SUBSCRIBE_LOG_STREAM, source, historyLimit);
    void ws
        .waitForConnection(CONNECTION_WAIT_TIMEOUT_MS, { signal: controller.signal })
        .then(async () => {
            if (closed) return;
            subscriptionEpoch = ws.connectionEpoch;
            acknowledgementTimer.start();
            await ws.sendMessage(subscribePayload, { signal: controller.signal, waitForConnection: false });
        })
        .catch((error) => {
            if (!closed) fail(new LogStreamError(ensureError(error).message, 'retry'));
        });

    const unsubscribe = (): void => {
        if (closed) return;
        manualClose = true;
        safeClose();
        if (subscriptionEpoch !== null && ws.isConnected() && ws.connectionEpoch === subscriptionEpoch) {
            void ws.sendMessage(serializeLogStreamSubscription(WEBSOCKET_MESSAGE_TYPES.UNSUBSCRIBE_LOG_STREAM, source), { waitForConnection: false }).catch((error) => {
                errorHandler.debug(moduleName, 'Log stream unsubscribe send failed', ensureError(error));
            });
        }
    };
    const detach = (): void => {
        if (closed) return;
        manualClose = true;
        safeClose();
    };

    return {
        unsubscribe,
        close: unsubscribe,
        abort: unsubscribe,
        detach
    };
};

export { streamLogs };
export type { WebSocketClientContract, StreamLogHandlers, StreamLogsOptions };
