/* SoAI - Shared realtime resource group subscription [frontend/assets/ts/core/realtime/streammanager/subscriptions/resourceGroupSubscription.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { BundleDefinition, BundleHandlers, ResourceListener, ResourceSnapshot, ResourceSubscriptionOptions, StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';

interface BundleSubscription {
    abort: () => void;
    controller: AbortController;
    resources: string[];
    ready: Promise<void>;
}

const createBundleSubscription = (options: { module: string; bundle: BundleDefinition; handlers: BundleHandlers; signal?: AbortSignal | null; createAbortError: () => Error; safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => void; ensureBundleResources: (bundle: BundleDefinition) => Promise<void>; getCachedState: (stateKey: string) => JsonValue | null; isResourceSnapshot: (value: JsonValue | ResourceSnapshot | null | undefined) => value is ResourceSnapshot; subscribeResourceState: (resourceName: string, listener: ResourceListener, options: ResourceSubscriptionOptions & { signal?: AbortSignal | null }) => () => void; cacheSnapshot: (bundle: BundleDefinition, resourceName: string, snapshot: ResourceSnapshot) => void; deliverSnapshot: (bundle: BundleDefinition, alias: string, resourceName: string, snapshot: ResourceSnapshot, handlers: BundleHandlers) => void }): BundleSubscription => {
    const { module: moduleName, bundle, handlers, signal, createAbortError, safeCall } = options;

    const controller = new AbortController();
    const unsubscribers: Array<(() => void) | { unsubscribe(): void }> = [];
    const cleanupListeners: Array<() => void> = [];
    const resourceList = Object.values(bundle.resources);

    const assertNotAborted = (): void => {
        if (controller.signal.aborted || signal?.aborted) {
            throw createAbortError();
        }
    };

    const abort = (): void => {
        if (controller.signal.aborted) {
            return;
        }
        controller.abort();
        cleanupListeners.forEach((callback) => callback());
        unsubscribers.forEach((entry) => {
            try {
                if (typeof entry === 'function') {
                    entry();
                } else {
                    entry.unsubscribe();
                }
            } catch (error) {
                const err = ensureError(error);
                errorHandler.debug(moduleName, 'Bundle abort cleanup failed', err);
            }
        });
        safeCall(handlers.onAbort, { bundle: bundle.name });
    };

    if (signal?.addEventListener) {
        if (signal.aborted) {
            abort();
        } else {
            const onAbort = (): void => abort();
            signal.addEventListener('abort', onAbort, { once: true });
            cleanupListeners.push(() => {
                try {
                    signal.removeEventListener('abort', onAbort);
                } catch (error) {
                    const err = ensureError(error);
                    errorHandler.debug(moduleName, 'Failed to remove abort listener', err);
                }
            });
        }
    }

    const ready = Promise.resolve().then(async (): Promise<void> => {
        try {
            assertNotAborted();

            const cachedState = options.getCachedState(bundle.stateKey);
            if (isObject(cachedState)) {
                Object.entries(bundle.resources).forEach(([alias, resourceName]) => {
                    const snapshot = cachedState[resourceName];
                    if (options.isResourceSnapshot(snapshot)) {
                        options.deliverSnapshot(bundle, alias, resourceName, snapshot, handlers);
                    }
                });
            }

            Object.entries(bundle.resources).forEach(([alias, resourceName]) => {
                assertNotAborted();
                const unsubscribe = options.subscribeResourceState(
                    resourceName,
                    (snapshot) => {
                        options.cacheSnapshot(bundle, resourceName, snapshot);
                        options.deliverSnapshot(bundle, alias, resourceName, snapshot, handlers);
                    },
                    { immediate: true, signal: controller.signal }
                );
                if (controller.signal.aborted || signal?.aborted) {
                    unsubscribe();
                    assertNotAborted();
                }
                unsubscribers.push(unsubscribe);
            });

            await options.ensureBundleResources(bundle);
            assertNotAborted();
            safeCall(handlers.onReady, { bundle: bundle.name, resources: resourceList });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isAbortError(runtimeError)) {
                safeCall(handlers.onError, runtimeError);
            }
            throw runtimeError;
        }
    });

    return {
        abort,
        controller,
        resources: resourceList,
        ready
    };
};

export { createBundleSubscription };
export type { BundleSubscription };
