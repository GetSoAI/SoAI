/* SoAI - Frontend resource reconciliation lifecycle [frontend/assets/ts/core/realtime/streammanager/resources/resourceLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, isAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import type { ResourceConfig, ResourceContext, ResourceEntry } from '@core/realtime/streammanager/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

interface WebSocketClientContract {
    waitForConnection(timeoutMs?: number, options?: { signal?: AbortSignal | undefined }): Promise<void>;
    requestSnapshot(resource: string, parameters?: JsonObject | null, options?: { signal?: AbortSignal | undefined }): Promise<{ data: JsonValue; resource: string; timestampMs: number | null } | null>;
}

interface ResourceStartOptions {
    forceRefresh?: boolean;
    generation: number;
    signal?: AbortSignal | undefined;
}

interface ResourceStartDependencies {
    getResource(name: string): ResourceEntry | null;
    shouldDeferInitialization(): boolean;
    isMaintenanceActive(): boolean;
    isGenerationActive(generation: number): boolean;
    getWebSocket(): WebSocketClientContract | null;
}

type ResourceTransformOutcome = { updateOutcome: 'applied'; value: JsonValue } | { updateOutcome: 'rejected'; error: Error };

const assertGenerationActive = (generation: number, dependencies: ResourceStartDependencies): void => {
    if (!dependencies.isGenerationActive(generation)) throw createAbortError();
};

const transformResourceValue = (resource: ResourceEntry, config: ResourceConfig, value: JsonValue | null, type: string, raw: JsonValue | null, ownsConfiguration: () => boolean): ResourceTransformOutcome => {
    const context: ResourceContext = {
        type,
        raw,
        resource,
        previousValue: resource.value
    };
    try {
        const normalized = config.normalize(value, context);
        if (!ownsConfiguration()) throw createAbortError();
        const transformed = config.transform(normalized, context);
        if (!ownsConfiguration()) throw createAbortError();
        return { updateOutcome: 'applied', value: transformed };
    } catch (error) {
        const runtimeError = ensureError(error);
        if (!isAbortError(runtimeError)) errorHandler.debug('StreamManager', 'Resource decoder rejected a transport value', runtimeError);
        return { updateOutcome: 'rejected', error: runtimeError };
    }
};

const requireTransformedResourceValue = (resource: ResourceEntry, config: ResourceConfig, value: JsonValue | null, type: string, raw: JsonValue | null, ownsConfiguration: () => boolean): JsonValue => {
    const outcome = transformResourceValue(resource, config, value, type, raw, ownsConfiguration);
    const updateOutcome = outcome.updateOutcome;
    if (updateOutcome === 'rejected') throw outcome.error;
    return outcome.value;
};

const executeFetchAttempt = async (resource: ResourceEntry, config: ResourceConfig, signal: AbortSignal, ownsConfiguration: () => boolean): Promise<JsonValue> => {
    const fetcher = config.fetch;
    if (!fetcher) return resource.value;
    const value = await fetcher({ signal });
    if (!ownsConfiguration()) throw createAbortError();
    return requireTransformedResourceValue(resource, config, value, 'fetch', null, ownsConfiguration);
};

const executeWebSocketAttempt = async (resource: ResourceEntry, config: ResourceConfig, signal: AbortSignal, dependencies: ResourceStartDependencies, ownsConfiguration: () => boolean): Promise<JsonValue> => {
    const websocket = dependencies.getWebSocket();
    if (!websocket) throw new Error('WebSocket client is unavailable');
    const resourceName = resource.name;
    await websocket.waitForConnection(undefined, { signal });
    if (!ownsConfiguration()) throw createAbortError();
    const snapshot = await websocket.requestSnapshot(resourceName, null, { signal });
    if (!ownsConfiguration()) throw createAbortError();
    if (!snapshot) throw new Error(`WebSocket snapshot unavailable: ${resourceName}`);
    if (snapshot.resource !== resourceName) throw new Error(`WebSocket snapshot resource mismatch for ${resourceName}`);
    if (!ownsConfiguration()) throw createAbortError();
    const raw: JsonObject = {
        data: snapshot.data,
        resource: snapshot.resource,
        'timestamp_ms': snapshot.timestampMs
    };
    return requireTransformedResourceValue(resource, config, snapshot.data, 'websocket-initial', raw, ownsConfiguration);
};

const startResource = (resourceName: string, options: ResourceStartOptions, dependencies: ResourceStartDependencies): Promise<JsonValue | null> => {
    throwIfAborted(options.signal);
    assertGenerationActive(options.generation, dependencies);
    const resource = dependencies.getResource(resourceName);
    if (!resource) return Promise.reject(new Error(`Unknown resource: ${resourceName}`));
    if (dependencies.shouldDeferInitialization()) return Promise.reject(new Error('Deferred'));
    if (dependencies.isMaintenanceActive() || resource.reconciler.snapshot.maintenance) return Promise.reject(new Error('Maintenance'));
    const config = resource.config;
    const fetch = config.fetch;
    const normalize = config.normalize;
    const transform = config.transform;
    const websocketOnly = config.websocketOnly === true;
    const reconciler = resource.reconciler;
    const configurationRevision = resource.configurationRevision;
    const ownsConfiguration = (): boolean => resource.config === config && config.fetch === fetch && config.normalize === normalize && config.transform === transform && (config.websocketOnly === true) === websocketOnly && resource.reconciler === reconciler && resource.configurationRevision === configurationRevision;
    const source = websocketOnly ? 'websocket-snapshot' : 'fetch';
    return reconciler.reconcile(
        async ({ signal }): Promise<JsonValue> => {
            assertGenerationActive(options.generation, dependencies);
            if (!ownsConfiguration()) throw createAbortError();
            const value = websocketOnly ? await executeWebSocketAttempt(resource, config, signal, dependencies, ownsConfiguration) : await executeFetchAttempt(resource, config, signal, ownsConfiguration);
            if (!ownsConfiguration()) throw createAbortError();
            assertGenerationActive(options.generation, dependencies);
            return value;
        },
        {
            force: options.forceRefresh === true,
            source,
            ...(options.signal ? { signal: options.signal } : {})
        }
    );
};

const startWebSocketResource = (resourceName: string, options: ResourceStartOptions, dependencies: ResourceStartDependencies): Promise<JsonValue | null> => startResource(resourceName, options, dependencies);

const ensureStart = async (
    resourceName: string,
    options: { signal?: AbortSignal | undefined },
    dependencies: {
        ensureReady(options: { signal?: AbortSignal | undefined }): Promise<void>;
        getResource(name: string): ResourceEntry | null;
        startResource(name: string, options: { signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    }
): Promise<JsonValue | null> => {
    throwIfAborted(options.signal);
    const retainedResource = dependencies.getResource(resourceName);
    if (!retainedResource) throw new Error(`Missing resource: ${resourceName}`);
    if (retainedResource.status === 'ready') return retainedResource.value;
    if (retainedResource.maintenance && retainedResource.value !== null) return retainedResource.value;
    await dependencies.ensureReady(options);
    await dependencies.startResource(resourceName, options);
    const readyResource = dependencies.getResource(resourceName);
    if (!readyResource) throw new Error(`Missing resource: ${resourceName}`);
    if (readyResource.status !== 'ready') throw new Error(`Resource did not become ready: ${resourceName}`);
    return readyResource.value;
};

export { ensureStart, startResource, startWebSocketResource };
