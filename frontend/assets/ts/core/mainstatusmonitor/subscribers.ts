/* SoAI - Shared main status monitor subscribers [frontend/assets/ts/core/mainstatusmonitor/subscribers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { StatusCallback } from '@core/mainstatusmonitor/types.ts';

type SubscriberLog = (message: string, error: Error) => void;

class StatusSubscribers {
    #subscribers: Set<StatusCallback>;
    #logWarn: SubscriberLog;

    constructor(inputArguments: { logWarn: SubscriberLog }) {
        this.#subscribers = new Set();
        this.#logWarn = inputArguments.logWarn;
    }

    clear(): void {
        this.#subscribers.clear();
    }

    notify(state: string): void {
        for (const callback of this.#subscribers) {
            try {
                callback(state);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#logWarn('Subscriber callback failed', runtimeError);
            }
        }
    }

    subscribe(callback: StatusCallback, initialState: string): () => void {
        if (!isFunction(callback)) {
            throw new TypeError('MainStatusMonitor.subscribe requires a callback');
        }
        this.#subscribers.add(callback);
        if (initialState) {
            try {
                callback(initialState);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#logWarn('Failed to deliver initial state', runtimeError);
            }
        }
        return () => {
            this.#subscribers.delete(callback);
        };
    }
}

export { StatusSubscribers };
