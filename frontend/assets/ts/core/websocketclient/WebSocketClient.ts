/* SoAI - Shared frontend WebSocket client implementation [frontend/assets/ts/core/websocketclient/WebSocketClient.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { handleIncomingMessage, requestWebSocketSnapshot, sendPong, sendWebSocketMessage } from '@core/websocketclient/actions.ts';
import { SNAPSHOT_TIMEOUT_MESSAGE_PREFIX, SNAPSHOT_TIMEOUT_MS, type ConnectionState } from '@core/websocketclient/constants.ts';
import { isWebSocketReconnectInterruption, WebSocketReconnectInterruptionError } from '@core/websocketclient/connectionInterruption.ts';
import { WebSocketLatencyProbe } from '@core/websocketclient/latencyProbe.ts';
import type { EventCallback, GlobalEventCallback, SnapshotRequestOptions, SnapshotResponseEnvelope, WaitForConnectionOptions, WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import { WebSocketConnectionController } from '@core/websocketclient/WebSocketConnectionController.ts';
import { WebSocketSnapshotManager } from '@core/websocketclient/snapshotManager.ts';
import { WebSocketEventBus } from '@core/websocketclient/subscriptionManager.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { throwIfAborted } from '@core/errors/abort.ts';

type WebSocketLogData = JsonValue | Error;
type WebSocketLogger = (level: 'debug' | 'warn' | 'error', message: string, data?: WebSocketLogData) => void;

const log: WebSocketLogger = (level, message, data = null): void => {
    if (level === 'debug') {
        errorHandler.debug('WebSocketClient', message, data);
        return;
    }
    if (level === 'warn') {
        errorHandler.warn('WebSocketClient', message, data);
        return;
    }
    errorHandler.error('WebSocketClient', message, data);
};

class WebSocketClient {
    #eventBus: WebSocketEventBus = new WebSocketEventBus();
    #snapshotManager: WebSocketSnapshotManager = new WebSocketSnapshotManager((level, message): void => {
        log(level, message);
    });
    #controller: WebSocketConnectionController;
    #latencyProbe: WebSocketLatencyProbe;
    #connectionEpoch = 0;
    #receiveSequence = 0;
    #subscriberRecoveryEpoch = -1;

    constructor() {
        let controller: WebSocketConnectionController | null = null;
        const requireController = (): WebSocketConnectionController => {
            if (controller === null) {
                throw new Error('WebSocket controller is not initialized');
            }
            return controller;
        };
        this.#latencyProbe = new WebSocketLatencyProbe({
            isConnected: () => requireController().isConnected(),
            sendPayload: (payload) => requireController().send(payload)
        });
        controller = new WebSocketConnectionController({
            onConnected: (payload) => {
                this.#advanceConnectionEpoch();
                this.#latencyProbe.start();
                this.#dispatchEvent('connected', payload, this.#connectionEpoch);
            },
            onDisconnectedEvent: (payload) => this.#dispatchEvent('disconnected', payload, this.#connectionEpoch),
            onClosed: (payload) => {
                this.#latencyProbe.stop();
                if (payload.retrying) {
                    this.#snapshotManager.rejectPendingSnapshots(new WebSocketReconnectInterruptionError(payload.reason));
                    return;
                }
                this.#advanceConnectionEpoch();
                this.#snapshotManager.rejectPendingSnapshots(new LifecycleCancellationError('WebSocket disconnected during lifecycle transition', payload.reason));
            },
            onMessage: (event) => this.#handleMessage(event)
        });
        this.#controller = controller;
    }

    #handleMessage(event: MessageEvent): void {
        try {
            handleIncomingMessage({
                event,
                restartHeartbeat: () => this.#controller.restartHeartbeatTimer(),
                onPing: () => {
                    log('debug', 'Ping received, sending pong');
                    sendPong(this.#controller.getWebSocket(), log);
                },
                onLatencyProbeResult: (data) => this.#latencyProbe.handleResult(data),
                resolveSnapshot: (data, isError) => this.#snapshotManager.resolveSnapshot(data, isError),
                dispatchEvent: (eventType, data) => this.#dispatchEvent(eventType, data, this.#connectionEpoch)
            });
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn('WebSocketClient', 'Incoming message handling failed', runtimeError);
            this.#controller.closeWithReason('message-error', undefined, true);
            this.#controller.scheduleReconnect();
        }
    }

    #dispatchEvent(eventType: string, data: JsonValue, epoch: number): void {
        if (epoch !== this.#connectionEpoch) return;
        this.#receiveSequence += 1;
        const context: WebSocketDispatchContext = Object.freeze({
            connectionEpoch: epoch,
            receiveSequence: this.#receiveSequence
        });
        this.#eventBus.dispatch(eventType, data, context, (error, failedEventType): void => this.#recoverSubscriberFailure(error, failedEventType, epoch));
    }

    #advanceConnectionEpoch(): void {
        this.#connectionEpoch += 1;
        this.#receiveSequence = 0;
    }

    #recoverSubscriberFailure(error: Error, eventType: string, epoch: number): void {
        if (epoch !== this.#connectionEpoch || this.#subscriberRecoveryEpoch === epoch || this.#controller.isDestroyed()) {
            return;
        }
        this.#subscriberRecoveryEpoch = epoch;
        errorHandler.warn('WebSocketClient', `Subscriber failed while applying ${eventType}`, error);
        if (!this.#controller.isConnected()) {
            return;
        }
        this.#controller.closeWithReason('subscriber-error', { eventType }, true);
        this.#controller.scheduleReconnect();
    }

    connect(): void {
        this.#controller.connect();
    }

    resumeAfterSessionRotation(): void {
        this.#controller.resumeAfterSessionRotation();
    }

    disconnect(): void {
        this.#advanceConnectionEpoch();
        this.#controller.disconnect();
    }

    destroy(): void {
        this.#snapshotManager.rejectPendingSnapshots(new LifecycleCancellationError('WebSocket client destroyed during lifecycle transition', 'destroyed'));
        this.#latencyProbe.stop();
        this.#controller.destroy();
        this.#eventBus.clear();
    }

    subscribe(eventType: string, callback: EventCallback): () => void {
        return this.#eventBus.subscribe(eventType, callback);
    }

    subscribeAll(callback: GlobalEventCallback): () => void {
        return this.#eventBus.subscribeAll(callback);
    }

    getState(): ConnectionState {
        return this.#controller.getState();
    }

    isConnected(): boolean {
        return this.#controller.isConnected();
    }

    isDestroyed(): boolean {
        return this.#controller.isDestroyed();
    }

    get connectionEpoch(): number {
        return this.#connectionEpoch;
    }

    waitForConnection(timeoutMs: number = 15000, options: WaitForConnectionOptions = {}): Promise<void> {
        return this.#controller.waitForConnection(timeoutMs, options);
    }

    async requestSnapshot(resourceName: string, parameters: JsonObject | null = null, options: SnapshotRequestOptions = {}): Promise<SnapshotResponseEnvelope> {
        throwIfAborted(options.signal);
        this.connect();
        const totalTimeoutMs = typeof options.timeoutMs === 'number' && Number.isFinite(options.timeoutMs) && options.timeoutMs > 0 ? options.timeoutMs : SNAPSHOT_TIMEOUT_MS;
        const deadlineMs = monotonicMs() + totalTimeoutMs;
        while (true) {
            const remainingMs = Math.max(0, deadlineMs - monotonicMs());
            if (remainingMs <= 0) {
                throw new Error(`${SNAPSHOT_TIMEOUT_MESSAGE_PREFIX} ${resourceName}`);
            }
            await this.waitForConnection(remainingMs, { signal: options.signal });
            throwIfAborted(options.signal);
            const attemptTimeoutMs = Math.max(0, deadlineMs - monotonicMs());
            if (attemptTimeoutMs <= 0) {
                throw new Error(`${SNAPSHOT_TIMEOUT_MESSAGE_PREFIX} ${resourceName}`);
            }
            try {
                return await requestWebSocketSnapshot({
                    isConnected: this.isConnected(),
                    resourceName,
                    tabId: windowIdentity.current(),
                    parameters,
                    options: { ...options, timeoutMs: attemptTimeoutMs },
                    requestSnapshot: (requestedResourceName, tabId, requestParameters, sender, requestOptions) => this.#snapshotManager.requestSnapshot(requestedResourceName, tabId, requestParameters, sender, requestOptions),
                    sendPayload: (payload) => this.#controller.send(payload)
                });
            } catch (error) {
                const runtimeError = ensureError(error);
                if (!isWebSocketReconnectInterruption(runtimeError) || options.retryOnReconnect !== true) {
                    throw runtimeError;
                }
            }
        }
    }

    async sendMessage(payload: JsonObject, options: { waitForConnection?: boolean; timeoutMs?: number; signal?: AbortSignal } = {}): Promise<void> {
        throwIfAborted(options.signal);
        this.connect();
        await sendWebSocketMessage({
            payload,
            waitForConnection: options.waitForConnection !== false,
            timeoutMs: options.timeoutMs,
            signal: options.signal,
            awaitConnection: (timeoutMs, signal) => this.waitForConnection(timeoutMs, { signal }),
            isConnected: () => this.isConnected(),
            sendPayload: (messagePayload) => this.#controller.send(messagePayload)
        });
    }
}

export { WebSocketClient };
