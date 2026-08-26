/* SoAI - Frontend realtime WebSocket transport ownership [frontend/assets/ts/core/realtime/streammanager/streamTransport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { resolveLogSource } from '@core/realtime/streammanager/logSnapshotNormalization.ts';
import { LiveResourceInterestState } from '@core/realtime/streammanager/resources/liveResourceInterests.ts';
import { streamLogs, type StreamLogHandlers, type StreamLogsOptions } from '@core/realtime/streammanager/transport/logStream.ts';
import { initializeStreamWebSocket } from '@core/realtime/streammanager/transport/webSocketLifecycle.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import type { AuthManagerContract, StreamSafeCallback, StreamSafeCallbackArgument, StreamWebSocketClient } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import { WEBSOCKET_EVENT_TYPES, WEBSOCKET_LIFECYCLE_EVENT_TYPES } from '@core/websocketEvents.ts';

const MODULE = 'StreamManager';

interface StreamTransportRuntime {
    auth: AuthManagerContract | null;
    onInterestRejected(resources: readonly string[]): void;
}

type StreamEventListener = (eventType: string, data: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>;
type StreamConnectedListener = () => void | Promise<void>;

interface LogStreamOptions {
    historyLimit?: number;
}

interface PendingChatPresentationAcknowledgement {
    token: string;
    conversationId: string;
    minimumGeneration: number;
    completion: Deferred<void>;
}

class StreamTransport {
    #auth: AuthManagerContract | null;
    #onInterestRejected: (resources: readonly string[]) => void;
    #interests = new LiveResourceInterestState();
    #pendingChatPresentationAcknowledgement: PendingChatPresentationAcknowledgement | null = null;
    #chatPresentationAcknowledgedGeneration = -1;
    #connected = false;
    #eventListeners = new Set<StreamEventListener>();
    #connectedListeners = new Set<StreamConnectedListener>();
    #webSocket: StreamWebSocketClient | null = null;
    #eventUnsubscribe: (() => void) | null = null;
    #connectedUnsubscribe: (() => void) | null = null;
    #disposed = false;

    constructor(runtime: StreamTransportRuntime) {
        this.#auth = runtime.auth;
        this.#onInterestRejected = runtime.onInterestRejected;
    }

    get webSocket(): StreamWebSocketClient | null {
        return this.#webSocket;
    }

    initialize(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream transport is disposed', 'stream-transport-disposed');
        const result = initializeStreamWebSocket({
            module: MODULE,
            isAuthenticated: this.#auth?.isAuthenticated === true,
            currentWsSub: this.#eventUnsubscribe,
            currentConnectedSub: this.#connectedUnsubscribe,
            hasAssignedWebSocket: (candidate) => this.#webSocket === candidate,
            safeCall: (callback, ...inputArguments) => this.#safe(callback, ...inputArguments),
            handleAllEvents: (eventType, data, context) => this.#handleIncomingEvent(eventType, data, context),
            onConnected: () => this.#emitConnected()
        });
        this.#webSocket = result.ws;
        this.#eventUnsubscribe = result.wsSub;
        this.#connectedUnsubscribe = result.wsConnectedSub;
        this.#webSocket?.connect();
    }

    ensureInitialized(): StreamWebSocketClient | null {
        if (this.#disposed) throw new LifecycleCancellationError('Stream transport is disposed', 'stream-transport-disposed');
        if (!this.#webSocket || this.#webSocket.isDestroyed?.() === true) this.initialize();
        return this.#webSocket;
    }

    subscribeEvents(listener: StreamEventListener): () => void {
        this.#requireActive();
        this.#eventListeners.add(listener);
        return () => this.#eventListeners.delete(listener);
    }

    subscribeConnected(listener: StreamConnectedListener): () => void {
        this.#requireActive();
        this.#connectedListeners.add(listener);
        return () => this.#connectedListeners.delete(listener);
    }

    async #emitEvent(eventType: string, data: JsonValue, context: WebSocketDispatchContext): Promise<void> {
        for (const listener of [...this.#eventListeners]) {
            try {
                await listener(eventType, data, context);
            } catch (error) {
                errorHandler.error(MODULE, 'Transport handler failed', ensureError(error));
            }
        }
    }

    async #handleIncomingEvent(eventType: string, data: JsonValue, context: WebSocketDispatchContext): Promise<void> {
        if (eventType === WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED) {
            this.#connected = false;
            this.#chatPresentationAcknowledgedGeneration = -1;
            this.#cancelChatPresentationAcknowledgement('chat-presentation-interest-connection-closed');
        }
        if (eventType === WEBSOCKET_EVENT_TYPES.RESOURCE_INTERESTS_APPLIED || eventType === WEBSOCKET_EVENT_TYPES.INVALID_RESOURCE_INTEREST) {
            const outcome = this.#interests.parseServerEvent(eventType, data);
            if (outcome.type === 'acknowledged' && this.#connected) {
                this.#chatPresentationAcknowledgedGeneration = outcome.generation;
                const pending = this.#pendingChatPresentationAcknowledgement;
                if (pending && outcome.generation >= pending.minimumGeneration && this.#interests.chatPresentationGeneration(pending.token, pending.conversationId) !== null) {
                    this.#pendingChatPresentationAcknowledgement = null;
                    pending.completion.resolve();
                }
            } else if (outcome.type === 'rejected') {
                this.#rejectChatPresentationAcknowledgement(outcome.generation);
                this.#onInterestRejected(outcome.resources);
            }
            return;
        }
        await this.#emitEvent(eventType, data, context);
    }

    async #emitConnected(): Promise<void> {
        this.#connected = true;
        this.#chatPresentationAcknowledgedGeneration = -1;
        this.#cancelChatPresentationAcknowledgement('chat-presentation-interest-connection-replaced');
        for (const listener of [...this.#connectedListeners]) {
            try {
                await listener();
            } catch (error) {
                errorHandler.error(MODULE, 'Transport connected handler failed', ensureError(error));
            }
        }
    }

    #safe(callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]): void {
        if (!callback) return;
        try {
            const result = callback(...inputArguments);
            result?.catch((error) => errorHandler.error(MODULE, 'Transport handler failed', ensureError(error)));
        } catch (error) {
            errorHandler.error(MODULE, 'Transport handler failed', ensureError(error));
        }
    }

    acquireInterest(resourceName: string): string | null {
        this.#requireActive();
        const result = this.#interests.acquire(resourceName);
        if (result.changed) this.#syncOwned('Live resource interest sync');
        return result.token;
    }

    acquireChatPresentationInterest(conversationId: string): string | null {
        this.#requireActive();
        const result = this.#interests.acquireChatPresentation(conversationId);
        if (result.changed) {
            this.#cancelSupersededChatPresentationAcknowledgement();
            this.#syncOwned('Chat presentation interest sync');
        }
        return result.token;
    }

    updateChatPresentationInterest(token: string | null, conversationId: string): void {
        this.#requireActive();
        if (this.#interests.updateChatPresentation(token, conversationId)) {
            this.#cancelSupersededChatPresentationAcknowledgement();
            this.#syncOwned('Chat presentation interest update sync');
        }
    }

    async waitForChatPresentationInterest(token: string, conversationId: string): Promise<void> {
        this.#requireActive();
        const generation = this.#interests.chatPresentationGeneration(token, conversationId);
        if (generation === null) {
            throw new LifecycleCancellationError('Chat presentation interest was superseded', 'chat-presentation-interest-superseded');
        }
        if (this.#connected && this.#chatPresentationAcknowledgedGeneration >= generation) return;
        const existing = this.#pendingChatPresentationAcknowledgement;
        if (existing?.token === token && existing.conversationId === conversationId) {
            await existing.completion.promise;
            return;
        }
        const pending: PendingChatPresentationAcknowledgement = {
            token,
            conversationId,
            minimumGeneration: generation,
            completion: createDeferred<void>()
        };
        this.#pendingChatPresentationAcknowledgement = pending;
        await pending.completion.promise;
    }

    releaseInterest(token: string | null): void {
        this.#requireActive();
        if (this.#interests.release(token)) {
            this.#cancelSupersededChatPresentationAcknowledgement();
            this.#syncOwned('Live resource interest release sync');
        }
    }

    async syncInterests(): Promise<void> {
        this.#requireActive();
        if (!this.#webSocket) return;
        await this.#webSocket.sendMessage(this.#interests.buildMessage());
    }

    #syncOwned(label: string): void {
        this.syncInterests().catch((error) => errorHandler.warn(MODULE, label, ensureError(error)));
    }

    createSnapshotFetcher(resourceName: string): (options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null> {
        return async (options = {}) => {
            const webSocket = this.ensureInitialized();
            if (!webSocket) throw new Error('WebSocket client is unavailable');
            webSocket.connect();
            await webSocket.waitForConnection(undefined, { signal: options.signal });
            const snapshot = await webSocket.requestSnapshot(resourceName, null, { signal: options.signal });
            if (snapshot === null) throw new Error(`WebSocket snapshot unavailable: ${resourceName}`);
            if (snapshot.resource !== resourceName) throw new Error(`WebSocket snapshot resource mismatch for ${resourceName}`);
            return snapshot.data;
        };
    }

    streamLogs(sourceName: string, handlers: StreamLogHandlers, options: LogStreamOptions = {}): { unsubscribe: () => void; close: () => void; abort: () => void; detach: () => void } {
        const webSocket = this.ensureInitialized();
        if (!webSocket) throw new Error('WebSocket client is unavailable');
        const streamOptions: StreamLogsOptions = {
            module: MODULE,
            ws: webSocket,
            source: resolveLogSource(sourceName),
            handlers: isObject(handlers) ? handlers : {},
            safe: (callback, ...inputArguments) => this.#safe(callback, ...inputArguments)
        };
        if (typeof options.historyLimit === 'number') streamOptions.historyLimit = options.historyLimit;
        return streamLogs(streamOptions);
    }

    reset(): void {
        this.#requireActive();
        if (this.#eventUnsubscribe) this.#safe(this.#eventUnsubscribe);
        if (this.#connectedUnsubscribe) this.#safe(this.#connectedUnsubscribe);
        this.#eventUnsubscribe = null;
        this.#connectedUnsubscribe = null;
        this.#webSocket = null;
        this.#connected = false;
        this.#chatPresentationAcknowledgedGeneration = -1;
        this.#cancelChatPresentationAcknowledgement('chat-presentation-interest-transport-reset');
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        if (this.#eventUnsubscribe) this.#safe(this.#eventUnsubscribe);
        if (this.#connectedUnsubscribe) this.#safe(this.#connectedUnsubscribe);
        this.#eventUnsubscribe = null;
        this.#connectedUnsubscribe = null;
        this.#webSocket = null;
        this.#eventListeners.clear();
        this.#connectedListeners.clear();
        this.#cancelChatPresentationAcknowledgement('chat-presentation-interest-disposed');
        this.#interests.clear();
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream transport is disposed', 'stream-transport-disposed');
    }

    #rejectChatPresentationAcknowledgement(generation: number): void {
        const pending = this.#pendingChatPresentationAcknowledgement;
        if (!pending || !this.#connected || generation < pending.minimumGeneration) return;
        this.#pendingChatPresentationAcknowledgement = null;
        pending.completion.reject(new Error('Chat presentation resource interest was rejected'));
    }

    #cancelSupersededChatPresentationAcknowledgement(): void {
        const pending = this.#pendingChatPresentationAcknowledgement;
        if (!pending || this.#interests.chatPresentationGeneration(pending.token, pending.conversationId) !== null) return;
        this.#cancelChatPresentationAcknowledgement('chat-presentation-interest-superseded');
    }

    #cancelChatPresentationAcknowledgement(reason: string): void {
        const pending = this.#pendingChatPresentationAcknowledgement;
        if (!pending) return;
        this.#pendingChatPresentationAcknowledgement = null;
        pending.completion.reject(new LifecycleCancellationError('Chat presentation interest acknowledgement was cancelled', reason));
    }
}

export { StreamTransport };
export type { LogStreamOptions, StreamConnectedListener, StreamEventListener };
