/* SoAI - Shared frontend WebSocket client subscription manager [frontend/assets/ts/core/websocketclient/subscriptionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { type EventCallback, type GlobalEventCallback, type WebSocketDispatchContext } from '@core/websocketclient/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const isValidEventType = (eventType: string): boolean => typeof eventType === 'string' && eventType.trim().length > 0;
type DispatchFailureHandler = (error: Error, eventType: string) => void;

class WebSocketEventBus {
    #subscribers: Map<string, Set<EventCallback>> = new Map();
    #globalSubscribers: Set<GlobalEventCallback> = new Set();

    subscribe(eventType: string, callback: EventCallback): () => void {
        if (!isValidEventType(eventType)) throw new Error('Event type must be a non-empty string');
        if (typeof callback !== 'function') throw new Error('Callback must be a function');

        let typeSubscribers = this.#subscribers.get(eventType);
        if (!typeSubscribers) {
            typeSubscribers = new Set();
            this.#subscribers.set(eventType, typeSubscribers);
        }
        typeSubscribers.add(callback);

        return (): void => {
            const subscribers = this.#subscribers.get(eventType);
            if (subscribers) {
                subscribers.delete(callback);
                if (subscribers.size === 0) this.#subscribers.delete(eventType);
            }
        };
    }

    subscribeAll(callback: GlobalEventCallback): () => void {
        if (typeof callback !== 'function') throw new Error('Callback must be a function');
        this.#globalSubscribers.add(callback);
        return (): void => {
            this.#globalSubscribers.delete(callback);
        };
    }

    dispatch(eventType: string, data: JsonValue, context: WebSocketDispatchContext, handleFailure: DispatchFailureHandler): void {
        const typeSubscribers = this.#subscribers.get(eventType);
        if (typeSubscribers) {
            for (const callback of [...typeSubscribers]) {
                try {
                    const result = callback(data, context);
                    if (result !== undefined) {
                        Promise.resolve(result).catch((asyncError) => {
                            handleFailure(ensureError(asyncError), eventType);
                        });
                    }
                } catch (callbackError) {
                    handleFailure(ensureError(callbackError), eventType);
                }
            }
        }

        for (const callback of [...this.#globalSubscribers]) {
            try {
                const result = callback(eventType, data, context);
                if (result !== undefined) {
                    Promise.resolve(result).catch((asyncError) => {
                        handleFailure(ensureError(asyncError), eventType);
                    });
                }
            } catch (callbackError) {
                handleFailure(ensureError(callbackError), eventType);
            }
        }
    }

    clear(): void {
        this.#subscribers.clear();
        this.#globalSubscribers.clear();
    }
}

export { WebSocketEventBus };
export type { DispatchFailureHandler };
