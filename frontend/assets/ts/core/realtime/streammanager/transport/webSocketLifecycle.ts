/* SoAI - Shared realtime WebSocket lifecycle [frontend/assets/ts/core/realtime/streammanager/transport/webSocketLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { SequenceToken } from '@core/concurrency/sequenceToken.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { emitStreamEvent } from '@core/realtime/streammanager/internals.ts';
import { handleResourceWebSocketEvent, recoverMalformedResourceWebSocketEvent } from '@core/realtime/streammanager/transport/handleResourceWebSocketEvent.ts';
import { normalizeWebSocketPayload } from '@core/realtime/streammanager/transport/normalizeWebSocketPayload.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceEntry, ResourceUpdateOutcome, StreamSafeCallback, StreamSafeCallbackArgument, StreamWebSocketClient } from '@core/realtime/streammanager/types.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { getWebSocketClient } from '@core/websocketclient/service.ts';
import { WEBSOCKET_LIFECYCLE_EVENT_TYPES, getResourcesForEventType, isKnownEventType, isTaskWebSocketEventType, isWebSocketProtocolErrorEventType, isWebSocketUpdatedResource } from '@core/websocketEvents.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';

interface HandleStreamWebSocketEventOptions {
    module: string;
    eventType: string;
    data: JsonValue;
    handleTaskWebSocketEvent: (eventType: string, payload: JsonObject) => void;
    listResources: () => Iterable<ResourceEntry>;
    getResource: (name: string) => ResourceEntry | null;
    updateResource: (name: string, payload: JsonValue | null, updateType: string, raw: JsonValue | null) => ResourceUpdateOutcome;
    notifyResource?: (name: string, updateType: string, raw: JsonValue | null) => void;
    startResource: (name: string, options: { forceRefresh: boolean }) => Promise<JsonValue | null>;
}

const markWebSocketResourcesDisconnected = (options: HandleStreamWebSocketEventOptions): void => {
    for (const resource of options.listResources()) {
        const receivesWebSocketUpdates = resource.config.websocketOnly === true || isWebSocketUpdatedResource(resource.name);
        if (!receivesWebSocketUpdates || resource.reconciler.snapshot.maintenance || (resource.status !== 'ready' && resource.status !== 'initializing' && resource.status !== 'recovering')) {
            continue;
        }
        resource.reconciler.disconnect();
        options.notifyResource?.(resource.name, 'websocket-disconnected', options.data);
    }
};

const handleStreamWebSocketEvent = (options: HandleStreamWebSocketEventOptions): void => {
    if (!isObject(options)) {
        throw new Error('handleStreamWebSocketEvent requires options');
    }
    const { eventType, data } = options;
    if (eventType === WEBSOCKET_LIFECYCLE_EVENT_TYPES.DISCONNECTED) {
        markWebSocketResourcesDisconnected(options);
        return;
    }
    if (eventType === WEBSOCKET_LIFECYCLE_EVENT_TYPES.CONNECTED) {
        return;
    }
    if (!isKnownEventType(eventType)) {
        errorHandler.warn(options.module, 'Ignored unrecognized WebSocket event', { eventType });
        emitStreamEvent('websocket:unrecognized-event', { eventType }, 'warn');
        return;
    }

    const resourcesForEventType = getResourcesForEventType(eventType);
    emitStreamEvent('websocket:event', { eventType, resources: resourcesForEventType });
    if (resourcesForEventType.length === 0 && !isTaskWebSocketEventType(eventType) && !isWebSocketProtocolErrorEventType(eventType)) {
        return;
    }

    const normalized = normalizeWebSocketPayload(data);
    if (!normalized) {
        errorHandler.warn(options.module, 'Rejected malformed known WebSocket event', { eventType });
        emitStreamEvent('websocket:malformed-event', { eventType }, 'warn');
        recoverMalformedResourceWebSocketEvent({
            module: options.module,
            raw: data,
            resourcesForEventType,
            getResource: options.getResource,
            ...(options.notifyResource ? { notifyResource: options.notifyResource } : {}),
            startResource: options.startResource
        });
        return;
    }
    const payload: JsonObject = { ...normalized, type: eventType };

    options.handleTaskWebSocketEvent(eventType, payload);

    handleResourceWebSocketEvent({
        module: options.module,
        eventType,
        payload,
        resourcesForEventType,
        getResource: options.getResource,
        ...(options.notifyResource ? { notifyResource: options.notifyResource } : {}),
        updateResource: options.updateResource,
        startResource: options.startResource
    });
};

interface InitializeStreamWebSocketOptions {
    module: string;
    isAuthenticated: boolean;
    currentWsSub: (() => void) | null;
    currentConnectedSub: (() => void) | null;
    hasAssignedWebSocket: (ws: StreamWebSocketClient) => boolean;
    safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void;
    handleAllEvents: (eventType: string, data: JsonValue, context: WebSocketDispatchContext) => void | Promise<void>;
    onConnected: () => Promise<void>;
}

interface InitializeStreamWebSocketResult {
    ws: StreamWebSocketClient | null;
    wsSub: (() => void) | null;
    wsConnectedSub: (() => void) | null;
}

const initializeStreamWebSocket = (options: InitializeStreamWebSocketOptions): InitializeStreamWebSocketResult => {
    if (!isObject(options)) {
        throw new Error('initializeStreamWebSocket requires options');
    }
    if (!isFunction(options.safeCall)) {
        throw new Error('initializeStreamWebSocket requires safeCall');
    }
    if (!isFunction(options.handleAllEvents)) {
        throw new Error('initializeStreamWebSocket requires handleAllEvents');
    }

    try {
        if (options.currentWsSub) {
            options.safeCall(options.currentWsSub);
        }
        if (options.currentConnectedSub) {
            options.safeCall(options.currentConnectedSub);
        }

        if (!options.isAuthenticated) {
            return { ws: null, wsSub: null, wsConnectedSub: null };
        }

        const ws = getWebSocketClient();
        const wsSub = ws.subscribeAll(options.handleAllEvents);
        const connectedSequence = new SequenceToken();
        let completedConnectedSequence = 0;
        let connectedTask: Promise<void> | null = null;
        const wsConnectedSub = ws.subscribe(WEBSOCKET_LIFECYCLE_EVENT_TYPES.CONNECTED, async () => {
            if (!options.hasAssignedWebSocket(ws)) {
                return;
            }
            const requestedSequence = connectedSequence.next();
            while (completedConnectedSequence < requestedSequence) {
                if (!options.hasAssignedWebSocket(ws)) {
                    return;
                }
                const activeTask = connectedTask;
                if (activeTask) {
                    await activeTask;
                    continue;
                }
                const targetSequence = connectedSequence.value;
                const taskCompletion = createDeferred<void>();
                const nextTask = taskCompletion.promise;
                connectedTask = nextTask;
                try {
                    await options.onConnected();
                } catch (error) {
                    errorHandler.debug(options.module, 'WebSocket connected handler failed', ensureError(error));
                } finally {
                    completedConnectedSequence = targetSequence;
                    taskCompletion.resolve();
                    if (connectedTask === nextTask) {
                        connectedTask = null;
                    }
                }
            }
        });

        return { ws, wsSub, wsConnectedSub };
    } catch (error) {
        const err = ensureError(error);
        errorHandler.debug(options.module, 'WebSocket initialization failed', err);
        throw ensureError(error);
    }
};

export { handleStreamWebSocketEvent, initializeStreamWebSocket };
export type { HandleStreamWebSocketEventOptions, InitializeStreamWebSocketOptions, InitializeStreamWebSocketResult };
