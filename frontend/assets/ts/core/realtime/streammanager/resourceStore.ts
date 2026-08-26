/* SoAI - Frontend realtime stream resource state ownership [frontend/assets/ts/core/realtime/streammanager/resourceStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { enterMaintenanceMode } from '@core/realtime/streammanager/maintenance/maintenanceMode.ts';
import { isResourceSnapshot } from '@core/realtime/streammanager/internals.ts';
import { applyResourceError, applyResourceUpdate, getResourceSnapshot, notifyResourceUpdate } from '@core/realtime/streammanager/resources/resourceState.ts';
import { registerStreamResource } from '@core/realtime/streammanager/resources/registerStreamResource.ts';
import { cacheBundleSnapshotInState, callSafe, defineBundle, deliverBundleSnapshot, publishQueueDepthMetric, runUnsubscribeTarget, type UnsubscribeTarget } from '@core/realtime/streammanager/service.ts';
import { createBundleSubscription } from '@core/realtime/streammanager/subscriptions/resourceGroupSubscription.ts';
import type { BundleDefinition, BundleHandlers, DiagnosticsSnapshot, ResourceConfig, ResourceEntry, ResourceListener, ResourceSnapshot, ResourceSubscriptionOptions, ResourceSubscriptionRuntime, ResourceUpdateOutcome, StateServiceInterface, StreamManagerMaintenanceState, StreamSafeCallback, StreamSafeCallbackArgument } from '@core/realtime/streammanager/types.ts';
import { buildDiagnosticsSnapshot } from '@core/realtime/streammanager/diagnostics/buildDiagnosticsSnapshot.ts';
import { createOptionalResourceRules } from '@core/realtime/streammanager/resources/optionalResourceRules.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { ensureStart, startResource } from '@core/realtime/streammanager/resources/resourceLifecycle.ts';
import { handleStreamWebSocketEvent } from '@core/realtime/streammanager/transport/webSocketLifecycle.ts';
import { hasResourceLiveDemand, listAutoResourceStarts, listReconnectResources, startListenedResources } from '@core/realtime/streammanager/resources/resourceActivationPolicy.ts';
import { resetResourceRuntime } from '@core/realtime/streammanager/resources/resourceRuntimeReset.ts';
import { bindResourceReconciliation } from '@core/realtime/streammanager/resources/resourceSnapshotProjection.ts';
import { applyResourceTransportEvent } from '@core/realtime/streammanager/resources/resourceTransportEpoch.ts';
import type { WebSocketDispatchContext } from '@core/websocketclient/types.ts';

const MODULE = 'StreamManager';

class StreamResourceStore {
    #resources = new Map<string, ResourceEntry>();
    #bundles = new Map<string, BundleDefinition>();
    #maintenance: StreamManagerMaintenanceState = { active: false, reason: null, resources: [] };
    #eventTarget = new EventTarget();
    #stateService: StateServiceInterface;
    #optionalRules = createOptionalResourceRules();
    #transportEpoch = 0;
    #receiveSequence = 0;
    #runtimeGeneration = 0;

    constructor(stateService: StateServiceInterface) {
        this.#stateService = stateService;
    }

    get eventTarget(): EventTarget {
        return this.#eventTarget;
    }

    get maintenanceActive(): boolean {
        return this.#maintenance.active;
    }

    requireStartAllowed(): void {
        if (this.#maintenance.active) throw new Error('Maintenance');
    }

    get(name: string): ResourceEntry | null {
        return this.#resources.get(name) || null;
    }

    listAutoResourceStarts(): { name: string; autoStart: boolean; status: string; pending: boolean }[] {
        return listAutoResourceStarts(this.#resources);
    }

    has(name: string): boolean {
        return this.#resources.has(name);
    }

    isAutoStart(name: string): boolean {
        return this.#resources.get(name)?.config.autoStart === true;
    }

    startListenedResources(startOwned: (name: string) => void): void {
        startListenedResources(this.#resources, startOwned);
    }

    activeReconnectResources(): string[] {
        return listReconnectResources(this.#resources);
    }

    start(
        name: string,
        options: { forceRefresh?: boolean; generation: number; signal?: AbortSignal | undefined },
        runtime: {
            shouldDeferInitialization(): boolean;
            isGenerationActive(generation: number): boolean;
            getWebSocket(): { waitForConnection(timeoutMs?: number, options?: { signal?: AbortSignal | undefined }): Promise<void>; requestSnapshot(resource: string, parameters?: JsonObject | null, options?: { signal?: AbortSignal | undefined }): Promise<{ data: JsonValue; resource: string; timestampMs: number | null } | null> } | null;
        }
    ): Promise<JsonValue | null> {
        return startResource(name, options, {
            getResource: (resourceName) => this.get(resourceName),
            shouldDeferInitialization: runtime.shouldDeferInitialization,
            isMaintenanceActive: () => this.maintenanceActive,
            isGenerationActive: runtime.isGenerationActive,
            getWebSocket: runtime.getWebSocket
        });
    }

    async ensureStarted(name: string, signal: AbortSignal | undefined, start: (resourceName: string, options: { signal?: AbortSignal | undefined }) => Promise<JsonValue | null>): Promise<JsonValue | null> {
        this.requireStartAllowed();
        return ensureStart(name, { signal }, { ensureReady: async () => {}, getResource: (resourceName) => this.get(resourceName), startResource: start });
    }

    handleWebSocketEvent(eventType: string, data: JsonValue, context: WebSocketDispatchContext, handleTask: (type: string, payload: JsonObject) => void, start: (name: string, options: { forceRefresh: boolean }) => Promise<JsonValue | null>): void {
        if (!this.#acceptTransportEvent(context)) return;
        const runtimeGeneration = this.#runtimeGeneration;
        const ownsEvent = (): boolean => this.#runtimeGeneration === runtimeGeneration && this.#transportEpoch === context.connectionEpoch && this.#receiveSequence === context.receiveSequence;
        if (!applyResourceTransportEvent(this.#resources.values(), context, ownsEvent)) return;
        handleStreamWebSocketEvent({
            module: MODULE,
            eventType: eventType,
            data,
            handleTaskWebSocketEvent: handleTask,
            listResources: () => this.#resources.values(),
            getResource: (name) => this.get(name),
            updateResource: (name, payload, updateType, raw) => this.update(name, payload, updateType, raw, context),
            startResource: start
        });
    }

    register(name: string, options: Partial<ResourceConfig> & { initialValue?: JsonValue | null }, ready: boolean, start: (name: string) => Promise<JsonValue | null>): ResourceEntry {
        const entry = registerStreamResource({
            module: MODULE,
            name,
            options,
            resources: this.#resources,
            isReady: ready,
            attemptStartResource: start
        });
        if (entry.reconciliationUnsubscribe === null) {
            bindResourceReconciliation(entry, (snapshot): void => {
                this.publishQueueDepth();
                this.notify(entry.name, snapshot.transitionType);
            });
        }
        entry.reconciler.setLiveDemand(hasResourceLiveDemand(entry));
        return entry;
    }

    defineBundle(name: string, config: Partial<BundleDefinition> & { resources: Record<string, string> }): BundleDefinition {
        return defineBundle('@stream.bundle.', this.#bundles, name, config);
    }

    getBundle(name: string): BundleDefinition | null {
        return this.#bundles.get(name) || null;
    }

    snapshot(name: string): ResourceSnapshot | null {
        return getResourceSnapshot(this.get(name));
    }

    value(name: string): JsonValue | null {
        return this.get(name)?.value ?? null;
    }

    safe(callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]): void {
        callSafe(callback, inputArguments, (error) => errorHandler.error(MODULE, 'Handler fail', error));
    }

    notify(name: string, updateType: string, raw?: JsonValue | null): void {
        const resource = this.get(name);
        if (!resource) return;
        const options = {
            module: MODULE,
            eventTarget: this.#eventTarget,
            resource,
            updateType,
            safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => this.safe(callback, ...inputArguments)
        };
        if (raw === undefined) notifyResourceUpdate(options);
        else notifyResourceUpdate({ ...options, raw });
    }

    update(name: string, payload: JsonValue | null, updateType: string, raw: JsonValue | null, transportContext: WebSocketDispatchContext): ResourceUpdateOutcome {
        return applyResourceUpdate({
            module: MODULE,
            name,
            payload,
            updateType,
            raw,
            transportContext,
            getResource: (resourceName) => this.get(resourceName)
        });
    }

    #acceptTransportEvent(context: WebSocketDispatchContext): boolean {
        if (!Number.isSafeInteger(context.connectionEpoch) || context.connectionEpoch < 0 || !Number.isSafeInteger(context.receiveSequence) || context.receiveSequence <= 0) return false;
        if (context.connectionEpoch < this.#transportEpoch) return false;
        if (context.connectionEpoch > this.#transportEpoch) {
            this.#transportEpoch = context.connectionEpoch;
            this.#receiveSequence = 0;
        }
        if (context.receiveSequence <= this.#receiveSequence) return false;
        this.#receiveSequence = context.receiveSequence;
        return true;
    }

    setError(name: string, error: Error | JsonValue | null | undefined): void {
        applyResourceError({
            module: MODULE,
            name,
            error,
            getResource: (resourceName) => this.get(resourceName),
            optionRules: this.#optionalRules
        });
    }

    publishQueueDepth(): void {
        publishQueueDepthMetric(this.#resources, 'core.streamManager');
    }

    subscribe(name: string, listener: ResourceListener, options: ResourceSubscriptionOptions & { signal?: AbortSignal | null }, runtime: ResourceSubscriptionRuntime): () => void {
        const resource = this.get(name);
        const signal = options.signal ?? null;
        if (!resource || signal?.aborted) return () => {};
        const token = runtime.acquireInterest(name);
        resource.listeners.add(listener);
        resource.reconciler.setLiveDemand(true);
        let active = true;
        const unsubscribe = (): void => {
            if (!active) return;
            active = false;
            signal?.removeEventListener('abort', unsubscribe);
            resource.listeners.delete(listener);
            resource.reconciler.setLiveDemand(hasResourceLiveDemand(resource));
            runtime.releaseInterest(token);
        };
        signal?.addEventListener('abort', unsubscribe, { once: true });
        const immediate = options.immediate !== false;
        const snapshot = immediate ? this.snapshot(name) : null;
        if (snapshot) this.safe(listener, snapshot, { type: 'immediate' });
        const shouldStartUnavailable = resource.status === 'unavailable' && (resource.config.autoStart || options.ensureStart !== false);
        const shouldArmSeededResource = resource.status === 'ready';
        if (active && runtime.ready && (shouldStartUnavailable || shouldArmSeededResource)) runtime.startOwned(name);
        return unsubscribe;
    }

    createBundleSubscription(definition: BundleDefinition, handlers: BundleHandlers, signal: AbortSignal | null, ensureResources: (definition: BundleDefinition) => Promise<void>, subscribeResourceState: (name: string, listener: ResourceListener, options: ResourceSubscriptionOptions) => () => void): ReturnType<typeof createBundleSubscription> {
        return createBundleSubscription({
            module: MODULE,
            bundle: definition,
            handlers,
            signal,
            createAbortError,
            safeCall: (callback: StreamSafeCallback | null | undefined, ...inputArguments: StreamSafeCallbackArgument[]) => this.safe(callback, ...inputArguments),
            ensureBundleResources: ensureResources,
            getCachedState: (stateKey) => this.#stateService.getTabState(stateKey),
            isResourceSnapshot,
            subscribeResourceState,
            cacheSnapshot: (bundle, resourceName, snapshot) => cacheBundleSnapshotInState(this.#stateService, bundle, resourceName, snapshot),
            deliverSnapshot: (bundle, alias, resourceName, snapshot, bundleHandlers) => deliverBundleSnapshot(bundle, alias, resourceName, snapshot, bundleHandlers, (callback, ...inputArguments) => this.safe(callback, ...inputArguments))
        });
    }

    enterMaintenance(reason: string | null): void {
        if (this.#maintenance.active) return;
        this.#maintenance = enterMaintenanceMode({
            reason,
            resources: this.#resources
        });
    }

    beginMaintenanceExit(): string[] | null {
        if (!this.#maintenance.active) return null;
        const resources = this.#maintenance.resources.slice();
        this.#maintenance = { active: false, reason: null, resources: [] };
        this.#resources.forEach((resource) => {
            resource.reconciler.exitMaintenance();
        });
        return resources;
    }

    diagnostics(ready: boolean): DiagnosticsSnapshot {
        return buildDiagnosticsSnapshot({ resources: this.#resources, bundles: this.#bundles, ready });
    }

    unsubscribe(target: UnsubscribeTarget): void {
        runUnsubscribeTarget(target, (error) => errorHandler.debug(MODULE, 'Unsubscribe callback failed', error));
    }

    resetRuntime(clearValues: boolean, clearListeners = false): void {
        this.#runtimeGeneration += 1;
        if (clearValues) this.#maintenance = { active: false, reason: null, resources: [] };
        resetResourceRuntime(this.#resources, clearValues, clearListeners);
    }
}

export { StreamResourceStore };
