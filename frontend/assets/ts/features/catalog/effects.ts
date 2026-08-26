/* SoAI - Catalog feature effects [frontend/assets/ts/features/catalog/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError } from '@core/apiError.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { CAPS } from '@core/realtime/streammanager/resources/ids.ts';
import { getStreamRuntime, type StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import { isFunction, isInstanceOf } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { TAG } from '@features/catalog/constants.ts';
import type { CatalogStreamController, CatalogStreamOptions, CatalogStreamState, StreamResourceApi } from '@features/catalog/types.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';

type CatalogStreamReadiness = (allowDiscovery: boolean) => Promise<void>;

const createStreamResourceApi = (streamRuntime: StreamRuntimeOwners = getStreamRuntime(), ensureRuntimeReady: CatalogStreamReadiness = async (allowDiscovery): Promise<void> => await ensureStreamManagerReady(streamRuntime.resources, { allowDiscovery })): StreamResourceApi => {
    const requireJsonStreamPayload = (value: JsonValue | void, context: string): JsonValue => {
        if (!isJsonValue(value)) {
            throw new TypeError(`${context} must resolve to JSON`);
        }
        return value;
    };

    const ensureReady = async (options: CatalogStreamOptions = {}): Promise<void> => {
        await ensureRuntimeReady(options['allowDiscovery'] !== false);
    };

    const ensureResourceStarted = async (streamId: string): Promise<JsonValue> => {
        const result = streamRuntime.resources.ensureResourceStarted(streamId);
        return requireJsonStreamPayload(await result, 'Stream manager ensureResourceStarted');
    };

    const refreshResource = async (streamId: string, options: CatalogStreamOptions = {}): Promise<JsonValue> => {
        const resourceOptions = {
            ...(options.allowDiscovery !== undefined ? { allowDiscovery: options.allowDiscovery } : {})
        };
        const result = streamRuntime.resources.refresh(streamId, resourceOptions);
        return requireJsonStreamPayload(await result, 'Stream manager refresh');
    };

    const subscribeResourceState = (streamId: string, callback: (snapshot: ResourceSnapshot) => void, options: CatalogStreamOptions = {}): (() => void) | null => {
        const unsubscribeValue = streamRuntime.subscriptions.subscribeResourceState(
            streamId,
            (snapshot): void => {
                callback(snapshot);
            },
            {
                ...(options.immediate !== undefined ? { immediate: options.immediate } : {})
            }
        );
        return isFunction(unsubscribeValue) ? unsubscribeValue : null;
    };

    return { ensureReady, ensureResourceStarted, refreshResource, subscribeResourceState };
};

const createCatalogCapabilityManifestController = (createResourceApi: () => StreamResourceApi = createStreamResourceApi): CatalogStreamController => {
    const state: CatalogStreamState & {
        data: JsonObject | null;
        error: Error | null;
    } = {
        listeners: new Set(),
        waiters: [],
        data: null,
        error: null
    };

    let bound = false;
    let ensureTask: Promise<void> | null = null;

    const notifyListeners = (): void => {
        if (!state.listeners.size) return;
        const snapshot = state.data;
        state.listeners.forEach((listener): void => {
            try {
                listener(snapshot);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn(TAG, 'Capability manifest listener execution failed', runtimeError);
            }
        });
    };

    const flushWaiters = (): void => {
        const waiters = state.waiters.splice(0);
        for (const waiter of waiters) {
            waiter.resolve(state.data);
        }
    };

    const applySnapshot = (snapshot: ResourceSnapshot): void => {
        if (snapshot.status === 'ready' && isJsonObject(snapshot.value)) {
            state.data = snapshot.value;
            state.error = null;
            notifyListeners();
            flushWaiters();
        }
    };

    const bind = async (): Promise<void> => {
        if (bound) return;
        if (ensureTask) return ensureTask;

        const { ensureReady, ensureResourceStarted, subscribeResourceState } = createResourceApi();

        const task = (async (): Promise<void> => {
            state.error = null;
            await ensureReady({ allowDiscovery: true });
            await ensureResourceStarted(CAPS);
            subscribeResourceState(
                CAPS,
                (snapshot): void => {
                    if (snapshot.status === 'ready') applySnapshot(snapshot);
                },
                { immediate: true }
            );
            bound = true;
            ensureTask = null;
        })().catch((error): void => {
            const runtimeError = ensureError(error);
            state.error = runtimeError;
            errorHandler.warn(TAG, 'Capability manifest subscription failed', runtimeError);
            ensureTask = null;
            if (!isInstanceOf(runtimeError, APIError) || runtimeError.status !== 0) {
                errorHandler.error(TAG, 'Fetch failed', runtimeError);
                throw runtimeError;
            }
        });

        ensureTask = task;
        return task;
    };

    const ensureReady = async (): Promise<JsonObject | null> => {
        await bind();
        if (state.error) throw state.error;
        if (state.data) return state.data;
        const deferred = createDeferred<JsonObject | null>();
        const waiter: {
            resolve: (snapshot: JsonObject | null) => void;
        } = {
            resolve: (snapshot: JsonObject | null): void => {
                deferred.resolve(snapshot);
            }
        };
        state.waiters.push(waiter);
        return deferred.promise;
    };

    const subscribe = (listener: (snapshot: JsonObject | null) => void, { emitCurrent = true }: { emitCurrent?: boolean } = {}): (() => void) => {
        const typedListener = (snapshot: JsonObject | null): void => {
            listener(snapshot);
        };
        state.listeners.add(typedListener);
        if (emitCurrent && state.data) {
            try {
                typedListener(state.data);
            } catch (error) {
                const runtimeError = ensureError(error);
                errorHandler.warn(TAG, 'Capability manifest listener execution failed', runtimeError);
            }
        }
        bind().catch((error): void => {
            errorHandler.debug(TAG, 'Capability manifest binding failed', error);
        });
        return (): void => {
            state.listeners.delete(typedListener);
        };
    };

    const getSnapshot = (): JsonObject | null => state.data;

    return Object.freeze({
        bind,
        ensureReady,
        getSnapshot,
        subscribe
    });
};

export { createCatalogCapabilityManifestController, createStreamResourceApi };
