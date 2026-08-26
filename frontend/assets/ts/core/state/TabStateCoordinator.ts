/* SoAI - Tab selection state coordination [frontend/assets/ts/core/state/TabStateCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getEventConstructor } from '@core/environment/public.ts';
import type { ErrorHandler } from '@core/state/types.ts';
import { isBoolean, isFunction, isNumber, isString } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';

import type { JsonValue } from '@core/types/jsonValues.ts';

type StateValue = JsonValue | null | undefined;

interface TabStatePayload {
    key: string;
    value: StateValue;
    previous: StateValue;
    remote: boolean;
}

type TabStateHandler = (payload: TabStatePayload) => void;

const normalizeTabStateValue = (_key: string, value: StateValue): StateValue => {
    if (value === undefined) {
        return undefined;
    }
    if (value === null || isBoolean(value) || isNumber(value) || isString(value)) {
        return value;
    }
    if (value instanceof Error) {
        return {
            name: value.name,
            message: value.message,
            stack: value.stack || null
        };
    }
    const eventCtor = getEventConstructor();
    if (eventCtor && value instanceof eventCtor) {
        const eventValue = value;
        return {
            type: eventValue.type,
            timeStamp: isNumber(eventValue.timeStamp) ? eventValue.timeStamp : Date.now(),
            data: 'data' in eventValue ? eventValue['data'] : null,
            message: 'message' in eventValue ? eventValue['message'] : null
        };
    }
    return value;
};

class TabStateCoordinator {
    errorHandler: ErrorHandler;
    state: Map<string, StateValue>;
    subscribers: Set<TabStateHandler>;
    constructor(errorHandler: ErrorHandler) {
        this.errorHandler = errorHandler;
        this.state = new Map();
        this.subscribers = new Set();
    }

    set(key: string, value: StateValue): StateValue {
        const hasEntry = this.state.has(key);
        const previous = this.state.get(key);
        if (value === undefined) {
            if (!hasEntry) {
                return undefined;
            }
            this.state.delete(key);
            this.notify({ key, value: undefined, previous, remote: false });
            return undefined;
        }
        const normalized = normalizeTabStateValue(key, value);
        this.state.set(key, normalized);
        this.notify({ key, value: normalized, previous, remote: false });
        return normalized;
    }

    remove(key: string): StateValue {
        if (!this.state.has(key)) {
            return null;
        }
        const previous = this.state.get(key);
        this.state.delete(key);
        this.notify({ key, value: undefined, previous, remote: false });
        return previous;
    }

    get(key: string, defaultValue: StateValue = null): StateValue {
        return this.state.has(key) ? this.state.get(key) : defaultValue;
    }

    snapshot(): Record<string, StateValue> {
        const result: Record<string, StateValue> = {};
        this.state.forEach((value, key) => {
            result[key] = value;
        });
        return result;
    }

    subscribe(handler: TabStateHandler): () => void {
        if (!isFunction(handler)) {
            return () => {};
        }
        this.subscribers.add(handler);
        return () => {
            this.subscribers.delete(handler);
        };
    }

    destroy(): void {
        this.subscribers.clear();
        this.state.clear();
    }

    notify(payload: TabStatePayload): void {
        this.subscribers.forEach((handler) => {
            try {
                handler(payload);
            } catch (error) {
                const runtimeError = ensureError(error);
                this.errorHandler.debug?.('TabState', 'Subscriber failed', runtimeError);
            }
        });
    }
}
export { TabStateCoordinator };
export type TabStateErrorHandler = ErrorHandler;
export type { TabStatePayload, TabStateHandler };
