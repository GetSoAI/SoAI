/* SoAI - Batched WebSocket event subscription lifecycle helper [frontend/assets/ts/core/realtime/websocketBatchSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import type { WebSocketEventContract, WebSocketEventContractIdentity } from '@core/realtime/eventcontracts/contracts.ts';
import { subscribeManagedWebSocketEvent } from '@core/realtime/websocketSubscription.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isThenable } from '@core/typeGuards.ts';

interface ManagedWebSocketEventBinding {
    eventType: string;
    handler: (payload: JsonValue) => void | Promise<void>;
    label?: string | undefined;
}

interface WebSocketContractBinding extends ManagedWebSocketEventBinding {
    readonly contract: WebSocketEventContractIdentity;
}

interface WebSocketContractBindingOptions<Payload> {
    contract: WebSocketEventContract<Payload>;
    handler: (payload: Payload) => void | Promise<void>;
    invalidPayloadMessage?: string | undefined;
    label?: string | undefined;
    onInvalidPayload?: ((error: Error) => void) | undefined;
}

interface WebSocketEventBatchSubscribe {
    (eventType: string, handler: (payload: JsonValue) => void): () => void;
}

interface ManagedWebSocketEventBatchOptions {
    label: string;
    events: readonly ManagedWebSocketEventBinding[];
    signal?: AbortSignal | null | undefined;
}

interface WebSocketEventBatchOptions extends ManagedWebSocketEventBatchOptions {
    subscribe: WebSocketEventBatchSubscribe;
}

interface WebSocketContractBatchOptions {
    label: string;
    events: readonly WebSocketContractBinding[];
    subscribe: WebSocketEventBatchSubscribe;
    signal?: AbortSignal | null | undefined;
}

interface ManagedWebSocketContractBatchOptions extends Omit<WebSocketContractBatchOptions, 'subscribe'> {
    subscribe?: WebSocketEventBatchSubscribe | undefined;
}

interface ManagedWebSocketContractOptions<Payload> extends WebSocketContractBindingOptions<Payload> {
    signal?: AbortSignal | null | undefined;
}

const isSignalAborted = (signal: AbortSignal | null | undefined): boolean => signal?.aborted === true;

const subscribeWebSocketEventBatch = (options: WebSocketEventBatchOptions): (() => void) => {
    if (isSignalAborted(options.signal)) {
        return (): void => {};
    }
    const disposers: Array<() => void> = [];
    const cleanup = (): void => {
        drainCleanupStack(disposers, (runtimeError) => {
            errorHandler.warn(options.label, 'WebSocket event cleanup failed', runtimeError);
        });
    };

    try {
        for (const event of options.events) {
            const unsubscribe = options.subscribe(event.eventType, (payload: JsonValue): void => {
                try {
                    const result = event.handler(payload);
                    if (isThenable(result)) {
                        void Promise.resolve(result).catch((error) => {
                            errorHandler.warn(event.label ?? options.label, 'WebSocket event handler failed', ensureError(error));
                        });
                    }
                } catch (error) {
                    errorHandler.warn(event.label ?? options.label, 'WebSocket event handler failed', ensureError(error));
                }
            });
            disposers.push(unsubscribe);
        }
        const abortCleanup = (): void => cleanup();
        options.signal?.addEventListener('abort', abortCleanup, { once: true });
        disposers.push(() => options.signal?.removeEventListener('abort', abortCleanup));
        if (isSignalAborted(options.signal)) {
            cleanup();
        }
        return cleanup;
    } catch (error) {
        cleanup();
        throw ensureError(error);
    }
};

const subscribeManagedWebSocketEvents = (options: ManagedWebSocketEventBatchOptions): (() => void) => {
    return subscribeWebSocketEventBatch({
        ...options,
        subscribe: (eventType, handler) =>
            subscribeManagedWebSocketEvent({
                label: options.label,
                eventType,
                handler
            })
    });
};

const subscribeManagedWebSocketContracts = (options: ManagedWebSocketContractBatchOptions): (() => void) => {
    if (options.subscribe) return subscribeWebSocketEventBatch({ ...options, subscribe: options.subscribe });
    return subscribeManagedWebSocketEvents(options);
};

const createWebSocketContractBinding = <Payload>(options: WebSocketContractBindingOptions<Payload>): WebSocketContractBinding => {
    const invalidPayloadMessage = options.invalidPayloadMessage ?? `WebSocket event payload is invalid for "${options.contract.eventType}"`;
    return {
        contract: options.contract,
        eventType: options.contract.eventType,
        ...(options.label ? { label: options.label } : {}),
        handler: (payload: JsonValue): void | Promise<void> => {
            try {
                return options.handler(options.contract.decode(payload));
            } catch (error) {
                const runtimeError = ensureError(error);
                if (options.onInvalidPayload) {
                    options.onInvalidPayload(runtimeError);
                    return;
                }
                errorHandler.error(options.label ?? options.contract.eventType, invalidPayloadMessage, runtimeError);
            }
        }
    };
};

const subscribeManagedWebSocketContract = <Payload>(options: ManagedWebSocketContractOptions<Payload>): (() => void) => {
    const binding = createWebSocketContractBinding(options);
    return subscribeManagedWebSocketContracts({ label: options.label ?? options.contract.eventType, events: [binding], signal: options.signal });
};

export { createWebSocketContractBinding, subscribeManagedWebSocketContract, subscribeManagedWebSocketContracts };
export type { ManagedWebSocketContractBatchOptions, ManagedWebSocketContractOptions, WebSocketContractBinding, WebSocketContractBindingOptions, WebSocketEventBatchSubscribe };
