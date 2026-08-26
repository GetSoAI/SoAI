/* SoAI - Subscription lifecycle execution [frontend/assets/ts/core/subscriptionmanager/subscriptionExecution.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { ResourceSubscriptionHandler, UnsubscribeEntry } from '@core/subscriptionmanager/contracts.ts';
import type { SubscriptionHandle, SubscriptionHandlers } from '@core/realtime/types.ts';

interface SubscriptionExecutionOptions {
    immediate?: boolean;
    ensureStart?: boolean;
}

interface SubscriptionManagerContract {
    subscribe?(endpoint: string, handlers: ResourceSubscriptionHandler | SubscriptionHandlers, options?: SubscriptionExecutionOptions): UnsubscribeEntry;
    subscribeResourceState?(resource: string, listener: ResourceSubscriptionHandler | SubscriptionHandlers, options?: SubscriptionExecutionOptions): UnsubscribeEntry;
    unsubscribe?(id: string): void;
}

const normalizeUnsubscribe = (manager: Pick<SubscriptionManagerContract, 'unsubscribe'>, result: SubscriptionHandle | UnsubscribeEntry): (() => void) => {
    if (isFunction(result)) return result;
    if (isString(result)) return () => manager.unsubscribe?.(result);
    if (isObject(result)) {
        if ('unsubscribe' in result && isFunction(result.unsubscribe)) {
            const unsubscribe = result.unsubscribe;
            return () => unsubscribe();
        }
        if ('stop' in result && isFunction(result.stop)) {
            const stop = result.stop;
            return () => stop();
        }
        if ('abort' in result && isFunction(result.abort)) {
            const abort = result.abort;
            return () => abort();
        }
        if ('cancel' in result && isFunction(result.cancel)) {
            const cancel = result.cancel;
            return () => cancel();
        }
        if ('close' in result && isFunction(result.close)) {
            const close = result.close;
            return () => close();
        }
    }
    return () => {};
};

const buildHandlers = <T>(handlers: T, decorator?: (height: T) => T | undefined): T => {
    if (!decorator) return handlers;
    const transformed = decorator(handlers);
    return transformed ?? handlers;
};

const executeSubscription = (manager: Pick<SubscriptionManagerContract, 'subscribe' | 'subscribeResourceState'>, options: { endpoint?: string; resource?: string; subscribeOptions?: SubscriptionExecutionOptions }, handlers: ResourceSubscriptionHandler): UnsubscribeEntry => {
    if (options.resource && typeof manager.subscribeResourceState === 'function') {
        return manager.subscribeResourceState(options.resource, handlers, options.subscribeOptions);
    }
    if (options.endpoint && typeof manager.subscribe === 'function') {
        return manager.subscribe(options.endpoint, handlers, options.subscribeOptions);
    }
    return undefined;
};

export { buildHandlers, executeSubscription, normalizeUnsubscribe };
export type { SubscriptionManagerContract };
