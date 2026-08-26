/* SoAI - Shared frontend WebSocket client run correlation [frontend/assets/ts/core/websocketclient/runCorrelation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, type APIErrorMetadata } from '@core/apiError.ts';
import { normalizeRequestTimeoutMs } from '@core/api/mappers.ts';
import type { RequestOptions } from '@core/api/types/request.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { generateSecureId } from '@core/primitives/idGenerator.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { WebSocketReconnectInterruptionError } from '@core/websocketclient/connectionInterruption.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import type { WebSocketClient } from '@core/websocketclient/WebSocketClient.ts';
import { isWebSocketProtocolErrorEventType } from '@core/websocketEvents.ts';

interface WebSocketRunCorrelationOptions<T> {
    runId: string;
    acceptedTypes: readonly string[];
    eventCancelled: string;
    eventError: string;
    signal?: AbortSignal | undefined;
    onCancelSend: () => Promise<void>;
    onMessage: (payload: JsonValue, resolve: (value: T) => void, reject: (error: Error) => void) => void;
    connectionEpoch?: number;
    timeoutMs?: number;
    deadlineMs?: number;
    client?: Pick<WebSocketClient, 'connectionEpoch' | 'isConnected' | 'sendMessage' | 'subscribeAll'>;
}

interface WebSocketRunCorrelation<T> {
    result: Promise<T>;
    connectionEpoch: number;
    send(payload: JsonObject): Promise<void>;
    fail(error: Error, sendCancellation?: boolean): void;
    cancel(error?: Error): void;
}

type PreparedWebSocketRunOptions<T> = Omit<WebSocketRunCorrelationOptions<T>, 'connectionEpoch' | 'timeoutMs' | 'deadlineMs'> & {
    requestOptions?: RequestOptions | undefined;
};

const createWebSocketRunId = (prefix: string): string => generateSecureId({ prefix, format: 'hex', separator: '_' });

const readRunErrorString = (payload: JsonValue, field: string): string | null => {
    if (!isJsonObject(payload)) return null;
    const value = payload[field];
    return typeof value === 'string' && value.trim() ? value.trim() : null;
};

const resolveRunErrorStatus = (code: string | null): number => {
    if (code === 'offline_mode' || code === 'network_policy_violation') return 423;
    if (code === 'insufficient_disk_space') return 507;
    return 0;
};

const buildWebSocketRunError = (payload: JsonValue): APIError => {
    const message = readRunErrorString(payload, 'message') ?? 'Request failed';
    const code = readRunErrorString(payload, 'code');
    const taskId = readRunErrorString(payload, 'task_id');
    const metadata: APIErrorMetadata = { payload };
    if (code) metadata.code = code;
    if (taskId) metadata.taskId = taskId;
    return new APIError(resolveRunErrorStatus(code), message, metadata);
};

const createRunTimeoutError = (): APIError => new APIError(0, 'Request timed out');

const resolveCorrelationDeadline = <T>(options: WebSocketRunCorrelationOptions<T>): number | null => {
    if (options.deadlineMs !== undefined) return options.deadlineMs;
    if (options.timeoutMs !== undefined) return monotonicMs() + normalizeRequestTimeoutMs(options.timeoutMs);
    return null;
};

const createWebSocketRunCorrelation = <T>(options: WebSocketRunCorrelationOptions<T>): WebSocketRunCorrelation<T> => {
    const ws = options.client ?? getWebSocketClient();
    const connectionEpoch = options.connectionEpoch ?? ws.connectionEpoch;
    const deadlineMs = resolveCorrelationDeadline(options);
    let settled = false;
    let cancellationSent = false;
    let unsubscribe: (() => void) | null = null;
    let timeout: ReturnType<typeof setTimeout> | null = null;
    let abortListener: (() => void) | null = null;
    let rejectExternally: ((error: Error, sendCancellation: boolean) => void) | null = null;

    const sendCancellation = (): void => {
        if (cancellationSent || ws.connectionEpoch !== connectionEpoch || !ws.isConnected()) return;
        cancellationSent = true;
        void options.onCancelSend().catch((error) => {
            errorHandler.warn('WebSocketRunCorrelation', 'Run cancellation send failed', ensureError(error));
        });
    };

    const result = new Promise<T>((resolve, reject) => {
        const cleanup = (): void => {
            const dispose = unsubscribe;
            unsubscribe = null;
            runCleanup(dispose, (runtimeError) => errorHandler.warn('WebSocketRunCorrelation', 'Run subscription cleanup failed', runtimeError));
            if (timeout !== null) {
                clearTimeout(timeout);
                timeout = null;
            }
            if (abortListener && options.signal) options.signal.removeEventListener('abort', abortListener);
            abortListener = null;
        };

        const settle = (handler: () => void, cancel: boolean): void => {
            if (settled) return;
            settled = true;
            cleanup();
            if (cancel) sendCancellation();
            handler();
        };

        rejectExternally = (error, cancel): void => settle(() => reject(error), cancel);
        abortListener = (): void => rejectExternally?.(createAbortError('Request aborted'), true);
        if (options.signal?.aborted) {
            rejectExternally(createAbortError('Request aborted'), true);
            return;
        }
        if (options.signal) options.signal.addEventListener('abort', abortListener, { once: true });

        if (deadlineMs !== null) {
            const remainingMs = deadlineMs - monotonicMs();
            if (remainingMs <= 0) {
                rejectExternally(createRunTimeoutError(), true);
                return;
            }
            timeout = setTimeout(() => rejectExternally?.(createRunTimeoutError(), true), remainingMs);
        }

        unsubscribe = ws.subscribeAll((eventType: string, payload: JsonValue, context: WebSocketDispatchContext) => {
            if (settled) return;
            if (context.connectionEpoch > connectionEpoch || (eventType === 'disconnected' && context.connectionEpoch === connectionEpoch)) {
                rejectExternally?.(new WebSocketReconnectInterruptionError('connection epoch ended'), false);
                return;
            }
            if (context.connectionEpoch !== connectionEpoch || !isJsonObject(payload)) return;
            const runIdValue = payload['run_id'];
            if (typeof runIdValue !== 'string' || runIdValue.trim() !== options.runId) return;
            if (eventType === options.eventCancelled) {
                rejectExternally?.(new Error('Request cancelled'), false);
                return;
            }
            if (eventType === options.eventError || isWebSocketProtocolErrorEventType(eventType)) {
                rejectExternally?.(buildWebSocketRunError(payload), false);
                return;
            }
            if (!options.acceptedTypes.includes(eventType)) return;
            try {
                options.onMessage(
                    payload,
                    (value) => settle(() => resolve(value), false),
                    (error) => rejectExternally?.(error, true)
                );
            } catch (error) {
                rejectExternally?.(ensureError(error), true);
            }
        });
    });

    const fail = (error: Error, sendCancellationAfterFailure = true): void => rejectExternally?.(error, sendCancellationAfterFailure);
    return {
        result,
        connectionEpoch,
        send: async (payload): Promise<void> => {
            if (settled) throw new Error('WebSocket run is already settled');
            if (ws.connectionEpoch !== connectionEpoch) throw new WebSocketReconnectInterruptionError('connection epoch changed before run message send');
            if (!ws.isConnected()) throw new WebSocketReconnectInterruptionError('connection closed before run message send');
            const sendOptions: { waitForConnection: false; signal?: AbortSignal } = { waitForConnection: false };
            if (options.signal) sendOptions.signal = options.signal;
            await ws.sendMessage(payload, sendOptions);
            if (ws.connectionEpoch !== connectionEpoch) throw new WebSocketReconnectInterruptionError('connection changed during run message send');
        },
        fail,
        cancel: (error = createAbortError('Request aborted')): void => fail(error, true)
    };
};

const waitForWebSocketRunResult = <T>(options: WebSocketRunCorrelationOptions<T>): Promise<T> => createWebSocketRunCorrelation(options).result;

const prepareWebSocketRun = async <T>(options: PreparedWebSocketRunOptions<T>): Promise<WebSocketRunCorrelation<T>> => {
    const ws = getWebSocketClient();
    const timeoutMs = normalizeRequestTimeoutMs(options.requestOptions?.timeoutMs);
    const deadlineMs = monotonicMs() + timeoutMs;
    if (options.requestOptions?.signal?.aborted) throw createAbortError('Request aborted');
    ws.connect();
    try {
        await ws.waitForConnection(Math.max(0, deadlineMs - monotonicMs()), { signal: options.requestOptions?.signal });
    } catch (error) {
        if (options.requestOptions?.signal?.aborted) throw createAbortError('Request aborted');
        const runtimeError = ensureError(error);
        if (runtimeError.message === 'WebSocket connection timeout' || monotonicMs() >= deadlineMs) throw createRunTimeoutError();
        throw runtimeError;
    }
    if (monotonicMs() >= deadlineMs) throw createRunTimeoutError();
    if (!ws.isConnected()) throw new WebSocketReconnectInterruptionError('connection unavailable before run start');
    return createWebSocketRunCorrelation({
        ...options,
        signal: options.requestOptions?.signal,
        connectionEpoch: ws.connectionEpoch,
        deadlineMs,
        client: ws
    });
};

export { createWebSocketRunCorrelation, createWebSocketRunId, prepareWebSocketRun, waitForWebSocketRunResult };
export type { WebSocketRunCorrelation };
