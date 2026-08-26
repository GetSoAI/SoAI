/* SoAI - Shared frontend WebSocket client actions [frontend/assets/ts/core/websocketclient/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { telemetry } from '@core/telemetry/service.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isFiniteNumber, isString } from '@core/typeGuards.ts';
import { CONNECTION_STATES, WEBSOCKET_PROTOCOL_VERSION, type ConnectionState } from '@core/websocketclient/constants.ts';
import { type SnapshotRequestOptions, type SnapshotResponseEnvelope, type WebSocketMessageData } from '@core/websocketclient/types.ts';
import { WebSocketReconnectInterruptionError } from '@core/websocketclient/connectionInterruption.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_MESSAGE_TYPES } from '@core/websocketEvents.ts';
type WebSocketLogData = JsonValue | Error;
type WebSocketLogger = (level: 'debug' | 'warn' | 'error', message: string, data?: WebSocketLogData) => void;
interface IncomingMessageHandlingOptions {
    event: MessageEvent;
    restartHeartbeat: () => void;
    onPing: () => void;
    onLatencyProbeResult: (data: JsonObject) => void;
    resolveSnapshot: (data: WebSocketMessageData, isError: boolean) => void;
    dispatchEvent: (eventType: string, data: JsonObject) => void;
}
interface BaseUrlChangeContext {
    baseUrl: string | null;
    currentState: ConnectionState;
    activeUrl: string | null;
    nextWebSocketUrl: string | null;
}
interface BaseUrlChangePlan {
    connect: boolean;
    disconnect: boolean;
    resetReconnectAttempts: boolean;
    logMessage: string | null;
}
interface SendWebSocketMessageOptions {
    payload: JsonValue;
    waitForConnection: boolean;
    timeoutMs: number | undefined;
    signal?: AbortSignal | undefined;
    awaitConnection: (timeoutMs: number, signal?: AbortSignal | undefined) => Promise<void>;
    isConnected: () => boolean;
    sendPayload: (payload: JsonObject) => boolean;
}
interface RequestSnapshotOptions {
    isConnected: boolean;
    resourceName: string;
    tabId: string;
    parameters: JsonObject | null;
    options?: SnapshotRequestOptions | undefined;
    requestSnapshot: (resourceName: string, tabId: string, parameters: JsonObject | null, sender: (payload: JsonObject) => void, options?: SnapshotRequestOptions | undefined) => Promise<SnapshotResponseEnvelope>;
    sendPayload: (payload: JsonObject) => boolean;
}
interface ConnectionHandlerOptions {
    websocket: {
        onopen: ((event: Event) => void) | null;
        onmessage: ((event: MessageEvent) => void) | null;
        onerror: ((event: Event) => void) | null;
        onclose: ((event: CloseEvent) => void) | null;
    };
    onOpen: () => void;
    onMessage: (event: MessageEvent) => void;
    onError: (event: Event) => void;
    onClose: (event: CloseEvent) => void;
}
const parseWebSocketMessageData = (rawValue: MessageEvent['data']): WebSocketMessageData => {
    try {
        const parsed = parseRequiredJsonText(String(rawValue));
        if (!isJsonObject(parsed) || !isString(parsed['type'])) {
            throw new Error('WebSocket message payload must be an object with a string type');
        }
        const protocolVersion = parsed['protocol_version'];
        if (!isFiniteNumber(protocolVersion)) {
            throw new Error('WebSocket message payload must include a numeric protocol_version');
        }
        const snapshotId = parsed['snapshot_id'];
        const resource = parsed['resource'];
        const timestampMs = parsed['timestamp_ms'];
        return {
            type: parsed['type'],
            protocolVersion,
            snapshotId: isString(snapshotId) ? snapshotId : null,
            resource: isString(resource) ? resource : null,
            data: parsed['data'],
            error: parsed['error'],
            message: parsed['message'],
            timestampMs: isFiniteNumber(timestampMs) ? timestampMs : null,
            raw: parsed
        };
    } catch (parseError) {
        const runtimeError = ensureError(parseError);
        errorHandler.debug('WebSocketClient', 'Failed to parse WebSocket message', runtimeError);
        throw runtimeError;
    }
};

const hasSupportedProtocolVersion = (data: WebSocketMessageData): boolean => {
    return data.protocolVersion === WEBSOCKET_PROTOCOL_VERSION;
};

const handleIncomingMessage = (options: IncomingMessageHandlingOptions): void => {
    options.restartHeartbeat();
    const data = parseWebSocketMessageData(options.event.data);
    if (!hasSupportedProtocolVersion(data)) {
        throw new Error(`Unsupported WebSocket protocol version: ${String(data.protocolVersion)}`);
    }
    if (data.type === WEBSOCKET_EVENT_TYPES.PING) {
        options.onPing();
        return;
    }
    if (data.type === WEBSOCKET_EVENT_TYPES.LATENCY_PROBE_RESULT) {
        options.onLatencyProbeResult(data.raw);
        return;
    }
    if (data.type === WEBSOCKET_EVENT_TYPES.SNAPSHOT_RESPONSE) {
        options.resolveSnapshot(data, false);
        return;
    }
    if (data.type === WEBSOCKET_EVENT_TYPES.SNAPSHOT_ERROR) {
        options.resolveSnapshot(data, true);
        return;
    }
    options.dispatchEvent(data.type, data.raw);
};
const resolveBaseUrlChange = (options: BaseUrlChangeContext): BaseUrlChangePlan => {
    if (!options.baseUrl) {
        const disconnect = options.currentState !== CONNECTION_STATES.DISCONNECTED || options.activeUrl !== null;
        return { connect: false, disconnect, resetReconnectAttempts: true, logMessage: disconnect ? 'Base URL cleared, disconnecting WebSocket' : null };
    }
    const hasActiveConnection = options.currentState === CONNECTION_STATES.CONNECTING || options.currentState === CONNECTION_STATES.CONNECTED;
    const urlChanged = hasActiveConnection && options.nextWebSocketUrl !== options.activeUrl;
    const needsConnect = options.currentState === CONNECTION_STATES.DISCONNECTED || options.currentState === CONNECTION_STATES.RECONNECTING;
    return {
        connect: needsConnect || urlChanged,
        disconnect: urlChanged,
        resetReconnectAttempts: urlChanged,
        logMessage: urlChanged ? 'Base URL changed during active connection, forcing reconnect' : null
    };
};
const sendWebSocketMessage = async (options: SendWebSocketMessageOptions): Promise<void> => {
    throwIfAborted(options.signal);
    if (!isJsonObject(options.payload)) {
        throw new Error('WebSocket payload must be an object');
    }
    const typeValue = options.payload['type'];
    if (!isString(typeValue) || !typeValue.trim()) {
        throw new Error('WebSocket payload requires a type');
    }
    if (options.waitForConnection) {
        const timeout = isFiniteNumber(options.timeoutMs) ? options.timeoutMs : 15000;
        await options.awaitConnection(timeout, options.signal);
    }
    throwIfAborted(options.signal);
    if (!options.isConnected()) {
        throw new Error('WebSocket not connected');
    }
    if (!options.sendPayload(options.payload)) {
        throw new Error('WebSocket not connected');
    }
};
const sendPong = (websocket: Pick<WebSocket, 'readyState' | 'send'> | null, log: WebSocketLogger): void => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
        try {
            websocket.send(JSON.stringify({ type: WEBSOCKET_MESSAGE_TYPES.PONG, 'protocol_version': WEBSOCKET_PROTOCOL_VERSION }));
            log('debug', 'Pong sent');
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('WebSocketClient', 'Failed to send pong', runtimeError);
        }
    }
};
const requestWebSocketSnapshot = async (options: RequestSnapshotOptions): Promise<SnapshotResponseEnvelope> => {
    if (!options.isConnected) {
        throw new WebSocketReconnectInterruptionError('connection unavailable before snapshot send');
    }
    return options.requestSnapshot(
        options.resourceName,
        options.tabId,
        options.parameters,
        (payload) => {
            if (options.sendPayload(payload)) {
                return;
            }
            throw new WebSocketReconnectInterruptionError('connection unavailable during snapshot send');
        },
        options.options
    );
};
const configureConnectionHandlers = (options: ConnectionHandlerOptions): void => {
    options.websocket.onopen = (): void => {
        options.onOpen();
    };
    options.websocket.onmessage = (event: MessageEvent): void => {
        options.onMessage(event);
    };
    options.websocket.onerror = (event: Event): void => {
        options.onError(event);
    };
    options.websocket.onclose = (event: CloseEvent): void => {
        options.onClose(event);
    };
};
const emitWebSocketTelemetryEvent = (stage: string, data: JsonObject = {}, severity: string = 'info'): void => {
    telemetry.emit({
        module: 'WebSocketClient',
        stage,
        severity,
        message: stage,
        data
    });
};
export { configureConnectionHandlers, emitWebSocketTelemetryEvent, handleIncomingMessage, requestWebSocketSnapshot, resolveBaseUrlChange, sendPong, sendWebSocketMessage };
export type { BaseUrlChangeContext, BaseUrlChangePlan };
