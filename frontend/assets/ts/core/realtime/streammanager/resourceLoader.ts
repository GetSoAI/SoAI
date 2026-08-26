/* SoAI - Frontend stream resource loading and readiness ownership [frontend/assets/ts/core/realtime/streammanager/resourceLoader.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiRequestBody } from '@core/api/types/request.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { createAbortSignalScope, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleCancellationError, isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { fetchStreamPayload, requestStreamResponse } from '@core/realtime/streammanager/effects.ts';
import { toBundleList } from '@core/realtime/streammanager/internals.ts';
import { startAutoResources } from '@core/realtime/streammanager/resources/autoResourceLifecycle.ts';
import { getAutoResourceState, subscribeAutoResourceState } from '@core/realtime/streammanager/autoresources/state.ts';
import { createGpuSlotsResource } from '@core/realtime/streammanager/resources/gpuSlotsResource.ts';
import { HARDWARE_GPU_SLOTS } from '@core/realtime/streammanager/resources/ids.ts';
import type { StreamResourceStore } from '@core/realtime/streammanager/resourceStore.ts';
import { StreamReadiness } from '@core/realtime/streammanager/streamReadiness.ts';
import type { StreamTransport } from '@core/realtime/streammanager/streamTransport.ts';
import type { ApiServiceInterface, AutoResourceState, BundleDefinition, DeferredReadyOptions, DiagnosticsSnapshot, ResourceConfig, ResourceEntry, ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { GpuSlotsBuilderResult } from '@core/types/streamTypes.ts';
import type { StreamResourceId, StreamResourceValue } from '@core/realtime/streammanager/resourceRegistry.ts';
import { isFunction } from '@core/typeGuards.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

const MODULE = 'StreamManager';

class StreamResourceLoader {
    #apiClient: ApiServiceInterface;
    #store: StreamResourceStore;
    #transport: StreamTransport;
    #readiness: StreamReadiness;
    #autoTask: Promise<Array<JsonValue | null>> | null = null;
    #autoAbort: AbortController | null = null;
    #restoreTask: Promise<void> | null = null;
    #disposed = false;

    constructor(apiClient: ApiServiceInterface, store: StreamResourceStore, readiness: StreamReadiness, transport: StreamTransport) {
        this.#apiClient = apiClient;
        this.#store = store;
        this.#readiness = readiness;
        this.#transport = transport;
    }

    get ready(): boolean {
        return this.#readiness.ready;
    }

    getResource<ResourceId extends StreamResourceId>(name: ResourceId, options: { state: true }): ResourceSnapshot<StreamResourceValue<ResourceId>> | null;
    getResource<ResourceId extends StreamResourceId>(name: ResourceId, options?: { state?: false }): StreamResourceValue<ResourceId> | null;
    getResource(name: string, options?: { state?: boolean }): ResourceSnapshot | JsonValue | null;
    getResource(name: string, options: { state?: boolean } = {}): ResourceSnapshot | JsonValue | null {
        return options.state ? this.#store.snapshot(name) : this.#store.value(name);
    }

    getDiagnostics(): DiagnosticsSnapshot {
        return this.#store.diagnostics(this.ready);
    }

    shouldDeferInitialization(): boolean {
        return this.#readiness.shouldDefer();
    }

    resetDeferredReady(): void {
        this.#requireActive();
        this.#readiness.resetDeferred();
    }

    settleDeferredReady(): void {
        this.#requireActive();
        this.#readiness.settleDeferred();
    }

    async ensureApiReady(options: { allowDiscovery?: boolean; signal?: AbortSignal | null } = {}): Promise<string> {
        return this.#readiness.ensureApi(options);
    }

    async request(endpoint: string, options: { method?: string; body?: ApiRequestBody; headers?: Record<string, string>; allowDiscovery?: boolean; signal?: AbortSignal | null } = {}): Promise<Response> {
        return requestStreamResponse({ ensureApiReady: (requestOptions) => this.ensureApiReady(requestOptions), request: (method, requestEndpoint, body, requestOptions) => this.#apiClient.request(method, requestEndpoint, body, requestOptions) }, endpoint, options);
    }

    createApiFetcher(endpoint: string): (options?: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null> {
        return async (options = {}) => {
            const requestOptions: { allowDiscovery: boolean; signal?: AbortSignal | null } = { allowDiscovery: true };
            if (options.signal) requestOptions.signal = options.signal;
            const payload = await fetchStreamPayload({ ensureApiReady: (readyOptions) => this.ensureApiReady(readyOptions), request: (method, requestEndpoint, body, apiOptions) => this.#apiClient.request(method, requestEndpoint, body, apiOptions) }, endpoint, requestOptions);
            if (!isJsonValue(payload)) throw new Error(`${endpoint} response must be JSON.`);
            return payload;
        };
    }

    createGpuSlotsResource(): Partial<ResourceConfig<GpuSlotsBuilderResult>> {
        return createGpuSlotsResource({ fetch: this.#transport.createSnapshotFetcher(HARDWARE_GPU_SLOTS) });
    }

    registerResource(name: string, options: Partial<ResourceConfig> & { initialValue?: JsonValue | null } = {}): ResourceEntry {
        this.#requireActive();
        return this.#store.register(name, options, this.#readiness.ready, (resourceName) => this.startResource(resourceName));
    }

    startResource<ResourceId extends StreamResourceId>(name: ResourceId, options?: { forceRefresh?: boolean; signal?: AbortSignal | undefined }): Promise<StreamResourceValue<ResourceId> | null>;
    startResource(name: string, options?: { forceRefresh?: boolean; signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    async startResource(name: string, { forceRefresh = false, signal }: { forceRefresh?: boolean; signal?: AbortSignal | undefined } = {}): Promise<JsonValue | null> {
        if (this.#disposed) return Promise.reject(new LifecycleCancellationError('Stream resource loader is disposed', 'stream-resource-disposed'));
        this.#transport.ensureInitialized();
        const generation = this.#readiness.generation;
        const signalScope = createAbortSignalScope([this.#readiness.resetSignal, signal]);
        try {
            return await this.#store.start(
                name,
                { forceRefresh, signal: signalScope.signal, generation },
                {
                    shouldDeferInitialization: () => this.shouldDeferInitialization(),
                    isGenerationActive: (startedGeneration) => startedGeneration === this.#readiness.generation,
                    getWebSocket: () => this.#transport.webSocket
                }
            );
        } finally {
            signalScope.cleanup();
        }
    }

    ensureResourceStarted<ResourceId extends StreamResourceId>(name: ResourceId, options?: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined }): Promise<StreamResourceValue<ResourceId> | null>;
    ensureResourceStarted(name: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined }): Promise<JsonValue | null>;
    async ensureResourceStarted(name: string, options: { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined } = {}): Promise<JsonValue | null> {
        try {
            this.#store.requireStartAllowed();
            if (!this.#readiness.ready) await this.ensureReady({ allowDiscovery: options.allowDiscovery !== false, signal: options.signal });
            const signalScope = createAbortSignalScope([this.#readiness.resetSignal, options.signal]);
            return await this.#store.ensureStarted(name, signalScope.signal, (resourceName, startOptions) => this.startResource(resourceName, startOptions)).finally(signalScope.cleanup);
        } catch (error) {
            if (options.throwOnError === false) return null;
            throw error;
        }
    }

    async ensureBundleResources(definition: BundleDefinition, options: { allowDiscovery?: boolean } = {}): Promise<(JsonValue | null)[]> {
        await this.ensureReady(options);
        return Promise.all(toBundleList(definition).map((name) => this.ensureResourceStarted(name)));
    }

    async startAuto(options: { signal?: AbortSignal | undefined } = {}): Promise<(JsonValue | null)[]> {
        this.#requireActive();
        if (this.#autoTask) return options.signal ? raceWithAbortSignal(this.#autoTask, options.signal) : this.#autoTask;
        if (this.#store.maintenanceActive) return [];
        this.#autoAbort = new AbortController();
        const signalScope = createAbortSignalScope([this.#readiness.resetSignal, this.#autoAbort.signal]);
        const task = startAutoResources({ isMaintenanceActive: () => this.#store.maintenanceActive, resources: this.#store.listAutoResourceStarts(), ensureStart: (name, startOptions) => this.ensureResourceStarted(name, startOptions), signal: signalScope.signal }).finally(() => {
            signalScope.cleanup();
            if (this.#autoTask === task) {
                this.#autoTask = null;
                this.#autoAbort = null;
            }
        });
        this.#autoTask = task;
        return options.signal ? raceWithAbortSignal(task, options.signal) : task;
    }

    subscribeAutoState(listener: (state: AutoResourceState) => void, options: { emitCurrent?: boolean } = {}): () => void {
        this.#requireActive();
        if (!isFunction(listener)) return () => {};
        const unsubscribe = subscribeAutoResourceState(listener);
        if (options.emitCurrent !== false) {
            try {
                listener(getAutoResourceState());
            } catch (error) {
                errorHandler.debug(MODULE, 'Auto-resource state listener emit failed', ensureError(error));
            }
        }
        return unsubscribe;
    }

    startOwned(name: string, label: string): void {
        this.startResource(name).catch((error) => this.#logOwnedError(`${label} failed for ${name}`, error));
    }

    startAutoOwned(label: string): void {
        this.startAuto().catch((error) => this.#logOwnedError(`${label} failed`, error));
    }

    #logOwnedError(message: string, error: Error): void {
        const runtimeError = ensureError(error);
        if (!isLifecycleCancellationError(runtimeError) && !isAbortError(runtimeError)) errorHandler.warn(MODULE, message, runtimeError);
    }

    async ensureReady(options: DeferredReadyOptions & { allowDiscovery?: boolean; throwOnError?: boolean; signal?: AbortSignal | undefined } = {}): Promise<void> {
        if (this.#disposed) throw new LifecycleCancellationError('Stream resource loader is disposed', 'stream-resource-disposed');
        await this.#readiness.ensure(options);
        this.#store.startListenedResources((name) => this.startOwned(name, 'Ready listener resource start'));
    }

    refresh<ResourceId extends StreamResourceId>(name: ResourceId, options?: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<StreamResourceValue<ResourceId> | null>;
    refresh(name: string, options?: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<JsonValue | null>;
    refresh(name: string, options: { allowDiscovery?: boolean; throwOnError?: boolean } = {}): Promise<JsonValue | null> {
        const resourceName = name.trim();
        if (!resourceName) return Promise.reject(new Error('Name required'));
        return this.#refreshResource(resourceName, options);
    }

    async #refreshResource(name: string, options: { allowDiscovery?: boolean; throwOnError?: boolean }): Promise<JsonValue | null> {
        try {
            await this.ensureReady(options);
            if (!this.#store.has(name)) throw new Error(`Missing: ${name}`);
            return await this.startResource(name, { forceRefresh: true });
        } catch (error) {
            const runtimeError = ensureError(error);
            if (options.throwOnError !== false) throw runtimeError;
            errorHandler.debug(MODULE, 'refresh suppressed error', runtimeError);
            return null;
        }
    }

    enterMaintenance(reason: string | null = null): void {
        this.#requireActive();
        this.#store.enterMaintenance(reason);
    }

    async exitMaintenance(): Promise<void> {
        this.#requireActive();
        if (this.#restoreTask) return this.#restoreTask;
        const previouslyActive = this.#store.beginMaintenanceExit();
        if (!previouslyActive) return;
        const task = (async () => {
            await this.startAuto();
            const restore = previouslyActive.filter((name) => !this.#store.isAutoStart(name));
            await Promise.allSettled(restore.map((name) => this.startResource(name, { forceRefresh: true })));
        })().finally(() => {
            if (this.#restoreTask === task) this.#restoreTask = null;
        });
        this.#restoreTask = task;
        return task;
    }

    reset(clearValues: boolean): void {
        if (this.#disposed) return;
        this.#readiness.reset();
        this.#store.resetRuntime(clearValues);
        this.#transport.reset();
        this.#restoreTask = null;
        this.#autoAbort?.abort();
        this.#autoTask = null;
        this.#autoAbort = null;
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#readiness.dispose();
        this.#autoAbort?.abort();
        this.#autoTask = null;
        this.#autoAbort = null;
        this.#restoreTask = null;
        this.#store.resetRuntime(true, true);
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream resource loader is disposed', 'stream-resource-disposed');
    }
}

export { StreamResourceLoader };
