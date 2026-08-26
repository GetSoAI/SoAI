/* SoAI - Shared frontend realtime collections [frontend/assets/ts/core/realtimeCollections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { REALTIME_LIFECYCLE_HANDLER_KEYS, type RealtimeLifecycleArgument, type RealtimeLifecycleHandlerKey } from '@core/componentsupport/realtimeLifecycle.ts';
import type { PageInstance } from '@core/componentsupport/types.ts';
import type { ManagedSubscription, RealtimeCollectionRuntimeConfig } from '@core/realtime/collectionContracts.ts';
import { requireRealtimeService, type SubscriptionOptions } from '@core/realtime/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';

const MODULE_ID = 'core.realtimeCollections';

interface WarningManager {
    set: (value: boolean, ...inputArguments: RealtimeLifecycleArgument[]) => boolean;
    get: () => boolean;
}

interface RealtimeCollectionResult {
    start: () => ManagedSubscription | null;
    stop: () => void;
    restart: () => void;
    setWarning: (value: boolean, ...inputArguments: RealtimeLifecycleArgument[]) => boolean;
    getWarning: () => boolean;
    getSubscription: () => ManagedSubscription | null;
    isActive: () => boolean;
}

type HandlerFunctionValue = (...inputArguments: RealtimeLifecycleArgument[]) => void;

const invoke = (candidate: HandlerFunctionValue | null | undefined, inputArguments: RealtimeLifecycleArgument[]): void => {
    if (typeof candidate !== 'function') {
        return;
    }
    candidate(...inputArguments);
};

const invokeWarningCallback = (functionValue: ((warning: boolean, ...inputArguments: RealtimeLifecycleArgument[]) => void) | undefined, inputArguments: [boolean, ...RealtimeLifecycleArgument[]]): void => {
    if (typeof functionValue !== 'function') {
        return;
    }
    functionValue(...inputArguments);
};

const createWarningManager = (config: RealtimeCollectionRuntimeConfig): WarningManager => {
    let warning = false;
    return {
        set(value: boolean, ...inputArguments: RealtimeLifecycleArgument[]): boolean {
            const normalized = Boolean(value);
            warning = normalized;
            invokeWarningCallback(config.onWarningStateChange, [normalized, ...inputArguments]);
            return normalized;
        },
        get(): boolean {
            return warning;
        }
    };
};

const buildHandlers = (config: RealtimeCollectionRuntimeConfig, warningManager: WarningManager): Record<string, HandlerFunctionValue> => {
    const handlers: Record<string, HandlerFunctionValue> = {};
    const resolveHandler = (name: RealtimeLifecycleHandlerKey): HandlerFunctionValue | null | undefined => {
        switch (name) {
            case 'onInitial':
                return config.onInitial ?? undefined;
            case 'onUpdate':
                return config.onUpdate ?? undefined;
            case 'onConnect':
                return config.onConnect ?? undefined;
            case 'onError':
                return config.onError ?? undefined;
            case 'onFirstError':
                return config.onFirstError ?? undefined;
            case 'onReconnecting':
                return config.onReconnecting ?? undefined;
            case 'onReconnectFailed':
                return config.onReconnectFailed ?? undefined;
            case 'onStartError':
                return config.onStartError ?? undefined;
            case 'onFetchError':
                return config.onFetchError ?? undefined;
            case 'onFetchSuccess':
                return config.onFetchSuccess ?? undefined;
            case 'onManagerUnavailable':
                return config.onManagerUnavailable ?? undefined;
        }
    };
    REALTIME_LIFECYCLE_HANDLER_KEYS.forEach((name) => {
        const handler = resolveHandler(name);
        if (typeof handler === 'function') {
            handlers[name] = (...inputArguments: RealtimeLifecycleArgument[]): void => invoke(handler, inputArguments);
        }
    });

    const wrap = (name: RealtimeLifecycleHandlerKey, before: (...inputArguments: RealtimeLifecycleArgument[]) => void): void => {
        const original = handlers[name];
        handlers[name] = (...inputArguments: RealtimeLifecycleArgument[]): void => {
            before(...inputArguments);
            if (typeof original === 'function') {
                original(...inputArguments);
            }
        };
    };

    wrap('onConnect', () => warningManager.set(false));
    wrap('onFetchSuccess', () => warningManager.set(false));
    wrap('onError', (error: RealtimeLifecycleArgument, ...inputArguments: RealtimeLifecycleArgument[]) => warningManager.set(true, error, ...inputArguments));
    wrap('onReconnectFailed', () => warningManager.set(true));
    wrap('onReconnecting', () => warningManager.set(true));
    wrap('onFetchError', (error: RealtimeLifecycleArgument, ...inputArguments: RealtimeLifecycleArgument[]) => warningManager.set(true, error, ...inputArguments));
    wrap('onStartError', (error: RealtimeLifecycleArgument, ...inputArguments: RealtimeLifecycleArgument[]) => warningManager.set(true, error, ...inputArguments));
    wrap('onFirstError', (error: RealtimeLifecycleArgument, ...inputArguments: RealtimeLifecycleArgument[]) => warningManager.set(true, error, ...inputArguments));

    return handlers;
};

const runFetch = async (config: RealtimeCollectionRuntimeConfig, warningManager: WarningManager): Promise<JsonValue | null> => {
    if (typeof config.fetch !== 'function') {
        return null;
    }
    try {
        const result = await config.fetch();
        warningManager.set(false);
        invoke(config.onFetchSuccess ?? undefined, [result]);
        return result;
    } catch (error) {
        const runtimeError = ensureError(error);
        warningManager.set(true, runtimeError);
        invoke(config.onFetchError ?? undefined, [runtimeError]);
        throw runtimeError;
    }
};

const create = (page: PageInstance, config: RealtimeCollectionRuntimeConfig): RealtimeCollectionResult => {
    if (!isObject(page)) {
        throw new TypeError('realtimeCollections.create requires a page instance');
    }
    if (typeof config.subscribe !== 'function') {
        throw new TypeError('realtimeCollections.create requires a subscribe function');
    }
    const realtime = requireRealtimeService();
    if (!isObject(realtime) || typeof realtime.createManagedSubscription !== 'function') {
        throw new Error('realtimeCollections requires realtime.createManagedSubscription');
    }

    const warningManager = createWarningManager(config);
    const handlers = buildHandlers(config, warningManager);

    const options: SubscriptionOptions = { handlers, subscribe: config.subscribe };
    const key = config.key || config.resource || config.endpoint;
    if (key) {
        options.key = key;
    }
    if (config.endpoint) {
        options.endpoint = config.endpoint;
    }
    if (config.resource) {
        options.resource = config.resource;
    }
    if (config.immediate === true || config.immediate === false) {
        options.immediate = config.immediate;
    }
    if (isFunction(config.decorate)) {
        const decorateFunctionValue = config.decorate;
        options.decorate = (handlers) => {
            const decorated = decorateFunctionValue(handlers);
            if (!isObject(decorated)) {
                return undefined;
            }
            return { ...decorated };
        };
    }
    if (typeof config.onManagerUnavailable === 'function') {
        options.onUnavailable = () => {
            invoke(config.onManagerUnavailable, []);
        };
    }

    let subscription: ManagedSubscription | null = null;

    const start = (): ManagedSubscription | null => {
        runFetch(config, warningManager).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn(MODULE_ID, 'Realtime collection fetch failed', runtimeError);
        });
        subscription = realtime.createManagedSubscription(page, options);
        return subscription;
    };

    const stop = (): void => {
        if (!subscription) {
            return;
        }
        subscription.stop();
        subscription = null;
    };

    const restart = (): void => {
        stop();
        start();
    };

    if (config.autoStart !== false) {
        start();
    }

    return {
        start,
        stop,
        restart,
        setWarning: warningManager.set,
        getWarning: warningManager.get,
        getSubscription: () => subscription,
        isActive: () => Boolean(subscription?.isActive?.())
    };
};

const realtimeCollections = { create };

export { create, realtimeCollections };
