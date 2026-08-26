/* SoAI - Shared realtime actions [frontend/assets/ts/core/realtime/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { buildHandlers, normalizeUnsubscribe } from '@core/subscriptionmanager/subscriptionExecution.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

import type { RealtimePayload, StreamManagerInterface, SubscriptionController, SubscriptionHandlers, SubscriptionHandle, SubscriptionOptions, SubscriptionSnapshot } from '@core/realtime/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const createSafeOnce = (callback: (() => void) | null | undefined): (() => void) => {
    if (typeof callback !== 'function') {
        return () => {};
    }
    let called = false;
    return () => {
        if (called) {
            return;
        }
        called = true;
        try {
            callback();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.error('Realtime', 'Safe callback execution failed', runtimeError);
        }
    };
};

const buildRealtimeHandlers = (options: SubscriptionOptions): SubscriptionHandlers => {
    if (!options.handlers || !isObject(options.handlers)) {
        throw new Error('buildHandlers requires options.handlers object');
    }
    const base: SubscriptionHandlers = { ...options.handlers };
    const decorator = typeof options.wrapHandlers === 'function' ? options.wrapHandlers : typeof options.decorate === 'function' ? options.decorate : undefined;
    if (!decorator) {
        return base;
    }
    try {
        return buildHandlers(base, decorator);
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.error('Realtime', 'Handler decoration failed', runtimeError);
        return base;
    }
};

const normalizeUnsubscribeHandle = (manager: StreamManagerInterface, result: SubscriptionHandle): (() => void) => createSafeOnce(normalizeUnsubscribe(manager, result));

const subscribeUsingConfig = (manager: StreamManagerInterface, options: SubscriptionOptions, handlers: SubscriptionHandlers): SubscriptionHandle => {
    if (typeof options.subscribe === 'function') {
        return options.subscribe(handlers, options);
    }

    if (options.endpoint) {
        throw new Error('Endpoint subscriptions require an explicit subscribe implementation');
    }

    const resource = options.resource || options.key;
    if (!resource) {
        throw new Error('createManagedSubscription requires subscribe, endpoint, or resource');
    }

    const listener = (snapshot: SubscriptionSnapshot, context: { type: string; raw?: RealtimePayload }): void => {
        const payload = snapshot.value ?? null;
        if (context.type === 'initial') {
            const onInitial = handlers['onInitial'];
            if (isFunction(onInitial)) {
                onInitial(payload, context.raw);
            }
            return;
        }
        if (context.type === 'error') {
            const onError = handlers['onError'];
            if (isFunction(onError)) {
                onError(snapshot.error || context.raw || null);
            }
            return;
        }
        const onUpdate = handlers['onUpdate'];
        if (isFunction(onUpdate)) {
            onUpdate(payload, context.type, context.raw);
        }
    };

    const immediate = options.immediate !== false;
    if (typeof manager.subscribeResourceState !== 'function') throw new Error('StreamManager must expose subscribeResourceState');
    return manager.subscribeResourceState(resource, listener, { immediate, ensureStart: true });
};

const createController = (owner: WeakKey, manager: StreamManagerInterface, baseOptions: SubscriptionOptions): SubscriptionController => {
    let options: SubscriptionOptions = { ...baseOptions };
    let unsubscribe: () => void = () => {};
    let active = false;
    let currentHandlers: SubscriptionHandlers = buildRealtimeHandlers(options);

    const start = (): void => {
        currentHandlers = buildRealtimeHandlers(options);
        const result = subscribeUsingConfig(manager, options, currentHandlers);
        unsubscribe = normalizeUnsubscribeHandle(manager, result === undefined ? undefined : result);
        active = true;
    };

    const controller: SubscriptionController = {
        owner,
        key: options.key || options.resource || options.endpoint,
        stop(): void {
            if (!active) {
                return;
            }
            active = false;
            const finalize = unsubscribe;
            unsubscribe = () => {};
            finalize();
        },
        restart(extraOptions: Partial<SubscriptionOptions> = {}): SubscriptionController {
            controller.stop();
            if (!options.handlers || !isObject(options.handlers)) {
                throw new Error('restart requires options.handlers object');
            }
            const mergedHandlers = extraOptions.handlers
                ? {
                      ...options.handlers,
                      ...(extraOptions.handlers && isObject(extraOptions.handlers) ? extraOptions.handlers : {})
                  }
                : options.handlers;
            options = {
                ...options,
                ...extraOptions,
                handlers: mergedHandlers
            };
            start();
            return controller;
        },
        isActive(): boolean {
            return active;
        },
        getOptions(): SubscriptionOptions {
            return { ...options };
        },
        getHandlers(): SubscriptionHandlers {
            return { ...currentHandlers };
        }
    };

    start();
    return controller;
};

export { createController, buildRealtimeHandlers, normalizeUnsubscribeHandle, subscribeUsingConfig };
