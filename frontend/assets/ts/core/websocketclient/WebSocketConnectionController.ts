/* SoAI - WebSocket connection lifecycle and recovery controller [frontend/assets/ts/core/websocketclient/WebSocketConnectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getConnectionState } from '@core/connectionstate/service.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getMaintenanceCoordinator, type MaintenanceState } from '@core/maintenanceCoordinator.ts';
import { createModuleLogger, type ModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { configureConnectionHandlers, emitWebSocketTelemetryEvent, resolveBaseUrlChange } from '@core/websocketclient/actions.ts';
import { WebSocketConnectionWaitRegistry } from '@core/websocketclient/connectionWaitRegistry.ts';
import { waitForWebSocketConnection } from '@core/websocketclient/connectionWait.ts';
import { CONNECTION_STATES, CONNECTION_TIMEOUT_MS, RECONNECT_STABILITY_MS, WEBSOCKET_PROTOCOL_VERSION, type ConnectionState } from '@core/websocketclient/constants.ts';
import type { ConnectionControllerEvents } from '@core/websocketclient/contracts.ts';
import { buildWebSocketUrl, clearTimers, startHeartbeatTimer } from '@core/websocketclient/effects.ts';
import { resolveWebSocketMaintenanceTransition } from '@core/websocketclient/maintenance.ts';
import { resolveWebSocketSessionClosure } from '@core/websocketclient/sessionClosure.ts';
import { type ConnectionStateInterface, type TimerState, type WaitForConnectionOptions } from '@core/websocketclient/types.ts';
import { WebSocketReconnectScheduler } from '@core/websocketclient/WebSocketReconnectScheduler.ts';
import { ensureError } from '@core/errors/coerce.ts';

const log: ModuleLogger = createModuleLogger('WebSocketClient', { defaultLevel: 'debug' });

class WebSocketConnectionController {
    #events: ConnectionControllerEvents;
    #websocket: WebSocket | null = null;
    #state: ConnectionState = CONNECTION_STATES.DISCONNECTED;
    #timers: TimerState = { heartbeat: null, connectionTimeout: null, reconnectStability: null };
    #connectionState: ConnectionStateInterface;
    #reconnect: WebSocketReconnectScheduler;
    #connectionStateUnsubscribe: (() => void) | null = null;
    #isDestroyed: boolean = false;
    #maintenanceHold: boolean = false;
    #activeUrl: string | null = null;
    #maintenanceUnsubscribe: (() => void) | null = null;
    #waitRegistry: WebSocketConnectionWaitRegistry = new WebSocketConnectionWaitRegistry();
    #connectionRequested: boolean = false;
    #sessionRotationHold: boolean = false;

    constructor(events: ConnectionControllerEvents) {
        this.#events = events;
        this.#connectionState = getConnectionState();
        this.#reconnect = new WebSocketReconnectScheduler({
            isBlocked: (): boolean => this.#isDestroyed || this.#maintenanceHold || this.#sessionRotationHold,
            reconnect: (): void => this.#connect(),
            log,
            emit: emitWebSocketTelemetryEvent
        });
        this.#maintenanceUnsubscribe = getMaintenanceCoordinator().subscribe((state: MaintenanceState): void => this.#handleMaintenance(state));
    }

    getWebSocket(): WebSocket | null {
        return this.#websocket;
    }

    getState(): ConnectionState {
        return this.#state;
    }

    isConnected(): boolean {
        return this.#state === CONNECTION_STATES.CONNECTED;
    }

    isDestroyed(): boolean {
        return this.#isDestroyed;
    }

    connect(): void {
        if (this.#isDestroyed) throw new Error('WebSocketClient has been destroyed');
        this.#connectionRequested = true;
        if (this.#connectionStateUnsubscribe) {
            if (this.#state === CONNECTION_STATES.DISCONNECTED && !this.#maintenanceHold) this.#connect();
            return;
        }
        void this.#connectionState.initialize().catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn('WebSocketClient', 'ConnectionState initialization failed', runtimeError);
        });
        this.#connectionStateUnsubscribe = this.#connectionState.onChange((baseUrl): void => this.#handleBaseUrlChange(baseUrl), { immediate: true });
    }

    disconnect(): void {
        clearTimers(this.#timers);
        this.#reconnect.reset();
        this.#connectionRequested = false;
        this.#sessionRotationHold = false;
        this.#closeWebSocket({ reason: 'manual', retrying: false });
        if (this.#connectionStateUnsubscribe) {
            this.#connectionStateUnsubscribe();
            this.#connectionStateUnsubscribe = null;
        }
        log('debug', 'WebSocket disconnected');
        emitWebSocketTelemetryEvent('disconnected');
    }

    destroy(): void {
        this.#isDestroyed = true;
        if (this.#maintenanceUnsubscribe) {
            this.#maintenanceUnsubscribe();
            this.#maintenanceUnsubscribe = null;
        }
        this.disconnect();
        log('debug', 'WebSocket client destroyed');
    }

    waitForConnection(timeoutMs: number = 15000, options: WaitForConnectionOptions = {}): Promise<void> {
        return waitForWebSocketConnection({
            timeoutMs,
            signal: options.signal,
            isConnected: () => this.isConnected(),
            isDestroyed: () => this.#isDestroyed,
            subscribeConnected: (listener) => this.#waitRegistry.subscribeConnected(listener),
            subscribeClosed: (listener) => this.#waitRegistry.subscribeClosed(listener)
        });
    }

    send(payload: JsonObject): boolean {
        if (this.#websocket && this.#websocket.readyState === WebSocket.OPEN) {
            this.#websocket.send(JSON.stringify({ ...payload, 'protocol_version': WEBSOCKET_PROTOCOL_VERSION }));
            return true;
        }
        return false;
    }

    restartHeartbeatTimer(): void {
        startHeartbeatTimer({
            timers: this.#timers,
            log,
            emit: emitWebSocketTelemetryEvent,
            closeConnection: (): void => this.#closeWebSocket({ reason: 'heartbeat-timeout', retrying: true }),
            reconnect: (): void => this.scheduleReconnect()
        });
    }

    closeWithReason(reason: string, data: JsonObject | undefined = undefined, retrying: boolean = false): void {
        if (data === undefined) {
            this.#closeWebSocket({ reason, retrying });
            return;
        }
        this.#closeWebSocket({ reason, data, retrying });
    }

    scheduleReconnect(): void {
        const plan = this.#reconnect.schedule();
        if (plan.status === 'scheduled') this.#state = CONNECTION_STATES.RECONNECTING;
    }

    resumeAfterSessionRotation(): void {
        this.#sessionRotationHold = false;
        if (this.#state === CONNECTION_STATES.DISCONNECTED) this.#connect();
    }

    #startReconnectStabilityTimer(): void {
        if (this.#timers.reconnectStability !== null) {
            clearTimeout(this.#timers.reconnectStability);
        }
        this.#timers.reconnectStability = setTimeout(() => {
            this.#timers.reconnectStability = null;
            if (this.#state !== CONNECTION_STATES.CONNECTED) {
                return;
            }
            this.#reconnect.reset();
            emitWebSocketTelemetryEvent('reconnect:stable');
        }, RECONNECT_STABILITY_MS);
    }

    #closeWebSocket(context: { reason: string; retrying: boolean; data?: JsonObject; dispatchEvent?: boolean }): void {
        clearTimers(this.#timers);
        this.#reconnect.cancel();
        const dispatchEvent = context.dispatchEvent !== false;
        const hadWebSocket = this.#websocket !== null;
        const shouldDispatch = dispatchEvent && (hadWebSocket || this.#state !== CONNECTION_STATES.DISCONNECTED || this.#activeUrl !== null);
        if (this.#websocket) {
            try {
                this.#websocket.onopen = null;
                this.#websocket.onmessage = null;
                this.#websocket.onerror = null;
                this.#websocket.onclose = null;
                this.#websocket.close();
            } catch (closeError) {
                const runtimeError = ensureError(closeError);
                errorHandler.debug('WebSocketClient', 'Error closing WebSocket', runtimeError);
            }
            this.#websocket = null;
        }
        this.#activeUrl = null;
        this.#state = CONNECTION_STATES.DISCONNECTED;
        const reason = context.reason;
        if (!context.retrying) this.#waitRegistry.notifyClosed(reason);
        if (hadWebSocket) this.#events.onClosed({ reason, retrying: context.retrying });
        if (shouldDispatch) {
            const payload: JsonObject = { reason, 'session_closure': 'none' };
            if (context.data) {
                Object.assign(payload, context.data);
            }
            this.#events.onDisconnectedEvent(payload);
        }
    }

    #connect(): void {
        if (!this.#connectionRequested || this.#isDestroyed || this.#maintenanceHold || this.#sessionRotationHold) return;
        const wsUrl = buildWebSocketUrl(this.#connectionState);
        if (!wsUrl) {
            log('debug', 'No base URL available, waiting for connection state');
            return;
        }
        this.#closeWebSocket({ reason: 'reset', retrying: true, dispatchEvent: false });
        this.#state = CONNECTION_STATES.CONNECTING;
        log('debug', `Connecting to WebSocket: ${wsUrl}`);
        emitWebSocketTelemetryEvent('connecting', { url: wsUrl });
        try {
            const ws = new WebSocket(wsUrl);
            this.#websocket = ws;
            this.#activeUrl = wsUrl;
            const connectionTimeoutId = setTimeout(() => {
                if (this.#websocket === ws && this.#state === CONNECTION_STATES.CONNECTING) {
                    log('warn', 'Connection timeout');
                    emitWebSocketTelemetryEvent('connection:timeout', {}, 'warn');
                    this.#closeWebSocket({ reason: 'timeout', retrying: true });
                    this.scheduleReconnect();
                }
            }, CONNECTION_TIMEOUT_MS);
            this.#timers.connectionTimeout = connectionTimeoutId;
            configureConnectionHandlers({
                websocket: ws,
                onOpen: () => {
                    if (this.#websocket !== ws || this.#state !== CONNECTION_STATES.CONNECTING) return;
                    clearTimeout(connectionTimeoutId);
                    this.#timers.connectionTimeout = null;
                    this.#state = CONNECTION_STATES.CONNECTED;
                    this.#startReconnectStabilityTimer();
                    log('debug', 'WebSocket connected');
                    emitWebSocketTelemetryEvent('connected', { url: wsUrl });
                    this.#events.onConnected({ url: wsUrl });
                    this.#waitRegistry.notifyConnected();
                    this.restartHeartbeatTimer();
                },
                onMessage: (event) => {
                    if (this.#websocket === ws) this.#events.onMessage(event);
                },
                onError: (event) => {
                    if (this.#websocket !== ws) return;
                    log('debug', 'WebSocket error', { event });
                    emitWebSocketTelemetryEvent('error', {}, 'error');
                },
                onClose: (event) => {
                    if (this.#websocket !== ws) return;
                    log('debug', `WebSocket closed: code=${event.code}, reason=${event.reason}`);
                    emitWebSocketTelemetryEvent('closed', { code: event.code, reason: event.reason });
                    const sessionClosure = resolveWebSocketSessionClosure(event.code, event.reason);
                    const retrying = sessionClosure !== 'invalidate';
                    this.#sessionRotationHold = sessionClosure === 'rotate';
                    if (!retrying) this.#connectionRequested = false;
                    this.#closeWebSocket({ reason: 'closed', retrying, data: { code: event.code, reason: event.reason, 'session_closure': sessionClosure } });
                    if (sessionClosure !== 'none') return;
                    this.scheduleReconnect();
                }
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('WebSocketClient', 'Failed to create WebSocket', runtimeError);
            emitWebSocketTelemetryEvent('error', { error: runtimeError.message || 'Unknown error' }, 'error');
            this.scheduleReconnect();
        }
    }

    #handleBaseUrlChange(baseUrl: string | null): void {
        const plan = resolveBaseUrlChange({
            baseUrl,
            currentState: this.#state,
            activeUrl: this.#activeUrl,
            nextWebSocketUrl: buildWebSocketUrl(this.#connectionState)
        });
        if (plan.logMessage) log('debug', plan.logMessage);
        if (plan.disconnect) this.#closeWebSocket({ reason: 'base-url-change', retrying: plan.connect });
        if (plan.resetReconnectAttempts) this.#reconnect.reset();
        if (plan.connect) this.#connect();
    }

    #handleMaintenance(state: MaintenanceState): void {
        const transition = resolveWebSocketMaintenanceTransition(state, {
            baseUrl: this.#connectionState.getBaseUrl(),
            connectionRequested: this.#connectionRequested,
            connectionState: this.#state
        });
        this.#maintenanceHold = transition.maintenanceHold;
        if (transition.closeConnection) {
            this.#closeWebSocket({ reason: 'maintenance', retrying: false });
        }
        if (transition.destroyConnection) {
            this.destroy();
            return;
        }
        if (transition.reconnect) this.#connect();
    }
}

export { WebSocketConnectionController };
export type { ConnectionControllerEvents };
