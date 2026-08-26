/* SoAI - Shared lifecycle model service [frontend/assets/ts/core/lifecyclemodel/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createModuleLogger, createSafeInvoker, type ModuleLogger, type SafeInvoker } from '@core/moduleContext.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import type { GetStreamManagerOptions, PeekStreamManagerOptions, StreamManagerCacheHost, StreamRuntimeOwners, SubscribeResourceHost, SubscribeResourceOptions } from '@core/lifecyclemodel/types.ts';
import type { DisposableResource } from '@core/resourcetracker/types.ts';
import { ensureError } from '@core/errors/coerce.ts';

const TAG = 'LifecycleModel';
const log: ModuleLogger = createModuleLogger(TAG, { defaultLevel: 'warn' });
const safeInvoke: SafeInvoker = createSafeInvoker(log, 'warn');
const NOOP = (): void => {};

const createFinalizer = (functionValue: (() => void) | undefined, label: string): (() => void) => {
    if (!isFunction(functionValue)) {
        return NOOP;
    }
    let done = false;
    return (): void => {
        if (done) {
            return;
        }
        done = true;
        safeInvoke(functionValue, [], `${label} cleanup failed`);
    };
};

interface DisposableMethodCarrier {
    unsubscribe?: () => void;
    stop?: () => void;
    dispose?: () => void;
    destroy?: () => void;
    close?: () => void;
    abort?: () => void;
    cancel?: () => void;
}

const resolveDisposableMethod = (candidate: DisposableMethodCarrier): (() => void) | null => {
    if ('unsubscribe' in candidate && isFunction(candidate.unsubscribe)) return candidate.unsubscribe;
    if ('stop' in candidate && isFunction(candidate.stop)) return candidate.stop;
    if ('dispose' in candidate && isFunction(candidate.dispose)) return candidate.dispose;
    if ('destroy' in candidate && isFunction(candidate.destroy)) return candidate.destroy;
    if ('close' in candidate && isFunction(candidate.close)) return candidate.close;
    if ('abort' in candidate && isFunction(candidate.abort)) return candidate.abort;
    if ('cancel' in candidate && isFunction(candidate.cancel)) return candidate.cancel;
    return null;
};

const peekLifecycleStreamManager = (host: StreamManagerCacheHost, options?: PeekStreamManagerOptions): StreamRuntimeOwners | null => {
    const required = options?.required ?? false;
    const manager = host.getCachedStreamManager() || host.resolveGlobalStreamManager();
    if (!manager) {
        if (required) {
            throw new Error('Stream manager is not available');
        }
        return null;
    }
    host.setCachedStreamManager(manager);
    return manager;
};

const resetLifecycleStreamManagerCache = (host: StreamManagerCacheHost): void => {
    host.setCachedStreamManager(null);
};

const getLifecycleStreamManager = async (host: StreamManagerCacheHost, options?: GetStreamManagerOptions): Promise<StreamRuntimeOwners> => {
    const shouldEnsureReady = options?.ensureReady ?? true;
    const allowDiscovery = options?.allowDiscovery ?? true;
    const signal = options?.signal;
    const manager = peekLifecycleStreamManager(host, { required: true });
    if (!manager) {
        throw new Error('Stream manager is not available');
    }
    if (shouldEnsureReady) {
        await manager.resources.ensureReady({ allowDiscovery, signal });
    }
    return manager;
};

const subscribeLifecycleResource = (host: SubscribeResourceHost, resource: string, handler: (snapshot: { name?: string; status?: string; error?: Error | { name?: string; message?: string } | null }) => void, options: SubscribeResourceOptions = {}): (() => void) => {
    if (!resource || !isFunction(handler)) {
        return NOOP;
    }
    const { ensureStarted = false, onUnavailable, onError, ...subscriptionOptions } = options;

    const normalizeDisposable = (disposable: DisposableResource | string): (() => void) => {
        if (!disposable) {
            return NOOP;
        }
        if (isFunction(disposable)) {
            return createFinalizer(disposable, `Disposable callback for ${resource}`);
        }
        if (isString(disposable)) {
            return createFinalizer(() => {
                host.peekStreamManager()?.subscriptions.unsubscribe(disposable);
            }, `Stream manager unsubscribe (${resource})`);
        }
        if (isObject(disposable)) {
            const method = resolveDisposableMethod(disposable);
            if (method) {
                return createFinalizer(() => {
                    method();
                }, `Disposable cleanup for ${resource}`);
            }
        }
        return NOOP;
    };

    let cleanup = NOOP;
    let disposed = false;
    let retryTimer: number | null = null;
    let attemptTask: Promise<void> | null = null;

    const scheduleRetry = (): void => {
        if (disposed || retryTimer !== null) {
            return;
        }
        retryTimer = host.setTimeout(() => {
            retryTimer = null;
            terminateHandledPromise(attempt());
        }, 2500);
    };

    const runOnce = async (): Promise<boolean> => {
        try {
            const manager = await host.getStreamManager({
                ensureReady: false,
                allowDiscovery: true
            });
            if (ensureStarted) {
                await manager.resources.ensureResourceStarted(resource);
            }
            if (disposed) {
                return false;
            }
            try {
                cleanup = normalizeDisposable(manager.subscriptions.subscribeResourceState(resource, handler, subscriptionOptions));
                host.trackDisposable(cleanup);
                return true;
            } catch (error) {
                const runtimeError = ensureError(error);
                if (isFunction(onError)) {
                    onError(runtimeError);
                } else {
                    log('warn', `subscribeResourceState failed for ${resource}`, runtimeError);
                }
            }
        } catch (error) {
            const runtimeError = ensureError(error);
            if (isFunction(onUnavailable)) {
                onUnavailable(runtimeError);
            } else {
                log('warn', `Failed to initialize subscription for ${resource}`, runtimeError);
            }
        }
        return false;
    };

    const attempt = async (): Promise<void> => {
        if (disposed || attemptTask) {
            return;
        }
        attemptTask = (async () => {
            const wasSuccessful = await runOnce();
            if (!wasSuccessful) {
                scheduleRetry();
            }
        })().finally(() => {
            attemptTask = null;
        });
        await attemptTask;
    };

    terminateHandledPromise(attempt());

    return (): void => {
        disposed = true;
        host.clearTimer(retryTimer);
        retryTimer = null;
        try {
            cleanup();
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(TAG, `Resource cleanup failed for ${resource}`, runtimeError);
        } finally {
            host.untrackDisposable(cleanup);
        }
    };
};

export { getLifecycleStreamManager, peekLifecycleStreamManager, resetLifecycleStreamManagerCache, subscribeLifecycleResource };
