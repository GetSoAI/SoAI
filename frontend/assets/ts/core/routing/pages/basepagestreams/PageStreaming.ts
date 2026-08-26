/* SoAI - Routed page streaming, subscriptions, task actions, and tracker ownership [frontend/assets/ts/core/routing/pages/basepagestreams/PageStreaming.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiRequestBody } from '@core/api/types/request.ts';
import { operationProgress } from '@core/operationprogress/public.ts';
import type { OperationProgressOptions, OperationProgressReporter } from '@core/operationprogress/types.ts';
import type { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import type { StreamRuntimeOwners } from '@core/realtime/streammanager/public.ts';
import { ensureStreamManagerReady } from '@core/realtime/streammanager/readiness.ts';
import type { AutoResourceState, OperationEvent } from '@core/realtime/streammanager/types.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { createStreamHandlers } from '@core/routing/pages/basepagestreams/actions.ts';
import { runPageTask } from '@core/routing/pages/basepagestreams/effects.ts';
import { createBasePageStreamsTaskHost } from '@core/routing/pages/basepagestreams/hosts.ts';
import { evaluateAutoResourceBannerState } from '@core/routing/pages/basepagestreams/mappers.ts';
import { ensurePageDataSubscriptions, ensurePageStreamReady, subscribeToPageOperations, verifyPageSubscriptionsReady } from '@core/routing/pages/basepagestreams/operations.ts';
import { createBasePageStreamsState } from '@core/routing/pages/basepagestreams/state.ts';
import { cleanupPageStreamsState, getOrCreatePageStreamTracker, getOrCreatePageSubscriptionManager, resolvePageStreamRuntime } from '@core/routing/pages/basepagestreams/streams.ts';
import { StreamHandleTracker } from '@core/routing/pages/pageStreams.ts';
import type { RunPageTaskOptions, StreamActionHandle, StreamHandlerCallbacks, SubscriptionManager } from '@core/routing/pages/pagetypes/public.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { ResourceSubscriptionHandler } from '@core/subscriptionmanager/contracts.ts';

interface PageStreamingDependencies {
    pageId: string;
    pageContext: PageContext;
    pageElements: PageUi;
    resources: PageResources;
}

interface PageStreamingContract {
    readonly pageTracker: StreamHandleTracker;
    tracker(pageKey?: string): StreamHandleTracker;
    runtime(): StreamRuntimeOwners;
    ensureReady(resources: StreamResourceLoader, allowDiscovery?: boolean, signal?: AbortSignal): Promise<void>;
    ensureRuntime(): Promise<StreamRuntimeOwners>;
    taskAction(endpoint: string, options?: { method?: string; body?: ApiRequestBody; headers?: Record<string, string>; handlers?: StreamActionHandlers; operation?: JsonObject | null; timeoutMs?: number }, runtime?: { allowDiscovery?: boolean }): Promise<StreamActionHandle>;
    taskCommand(command: JsonObject | null, options?: { handlers?: StreamActionHandlers; operation?: JsonObject | null; timeoutMs?: number }, runtime?: { allowDiscovery?: boolean }): Promise<StreamActionHandle>;
    progressReporter(channel: HTMLElement | string, options?: OperationProgressOptions | null): OperationProgressReporter;
    handlers(callbacks?: StreamHandlerCallbacks): StreamActionHandlers;
    subscriptionManager(): SubscriptionManager;
    subscribeResourceState(key: string, handler: ResourceSubscriptionHandler): () => void;
    subscribeResourceValue(key: string, handler: (data: JsonValue | null) => void): () => void;
    subscribeOperations(handler: (event: OperationEvent) => void, options?: { allowDiscovery?: boolean; track?: boolean }): Promise<() => void>;
    unsubscribeResourceValue(key: string): void;
    subscribeWebSocket(eventName: string, handler: (data: JsonValue | null) => void): () => void;
    unsubscribeWebSocket(eventName: string): void;
    ensureSubscriptions(options?: { signal?: AbortSignal }): Promise<void>;
    verifySubscriptions(): Promise<void>;
    runTask<T>(name: string, operation: () => Promise<T>, options?: RunPageTaskOptions<T>): Promise<T | null>;
    resetManager(): void;
    cleanup(): Promise<void>;
    destroy(): void;
}

interface PageStreamingOwnerHost {
    streaming: PageStreamingContract;
}

class PageStreaming implements PageStreamingContract {
    readonly #dependencies: PageStreamingDependencies;
    readonly #state = createBasePageStreamsState();

    constructor(dependencies: PageStreamingDependencies) {
        this.#dependencies = dependencies;
        const runtime = resolvePageStreamRuntime(this.#state);
        if (isFunction(runtime.resources.subscribeAutoState)) {
            this.#state.autoResourceCleanup = runtime.resources.subscribeAutoState((value: AutoResourceState) => this.#handleAutoResourceState(value), { emitCurrent: true });
        }
    }

    get pageTracker(): StreamHandleTracker {
        return this.tracker(this.#dependencies.pageId);
    }

    #handleAutoResourceState(value: AutoResourceState): void {
        const result = evaluateAutoResourceBannerState(value, this.#state.autoResourceOfflineVisible);
        if (!result.state) return;
        if (result.shouldShowOfflineBanner && result.message) {
            this.#dependencies.pageContext.notifications.show(result.message, 'error', 6000);
            this.#state.autoResourceOfflineVisible = true;
        } else if (result.shouldClearOfflineBanner) {
            this.#state.autoResourceOfflineVisible = false;
        }
    }

    tracker(pageKey: string = 'default'): StreamHandleTracker {
        return getOrCreatePageStreamTracker(this.#state, pageKey);
    }

    runtime(): StreamRuntimeOwners {
        return resolvePageStreamRuntime(this.#state);
    }

    async ensureReady(resources: StreamResourceLoader, allowDiscovery = true, signal?: AbortSignal): Promise<void> {
        await ensurePageStreamReady(resources, allowDiscovery, signal);
    }

    async ensureRuntime(): Promise<StreamRuntimeOwners> {
        const runtime = this.runtime();
        await this.ensureReady(runtime.resources);
        return runtime;
    }

    async taskAction(endpoint: string, options: { method?: string; body?: ApiRequestBody; headers?: Record<string, string>; handlers?: StreamActionHandlers; operation?: JsonObject | null; timeoutMs?: number } = {}, runtime: { allowDiscovery?: boolean } = { allowDiscovery: true }): Promise<StreamActionHandle> {
        if (!endpoint) throw err('Endpoint required');
        const allowDiscovery = runtime.allowDiscovery !== false;
        const streamRuntime = this.runtime();
        await ensureStreamManagerReady(streamRuntime.resources, { allowDiscovery });
        return streamRuntime.tasks.taskAction(endpoint, { ...options, allowDiscovery });
    }

    async taskCommand(command: JsonObject | null, options: { handlers?: StreamActionHandlers; operation?: JsonObject | null; timeoutMs?: number } = {}, runtime: { allowDiscovery?: boolean } = { allowDiscovery: true }): Promise<StreamActionHandle> {
        if (!command) throw err('Command required');
        const allowDiscovery = runtime.allowDiscovery !== false;
        const streamRuntime = this.runtime();
        await ensureStreamManagerReady(streamRuntime.resources, { allowDiscovery });
        return streamRuntime.tasks.taskCommand(command, options);
    }

    progressReporter(channel: HTMLElement | string, options?: OperationProgressOptions | null): OperationProgressReporter {
        return operationProgress.createOperationProgressReporter(channel, options ?? null);
    }

    handlers(callbacks: StreamHandlerCallbacks = {}): StreamActionHandlers {
        return createStreamHandlers(callbacks);
    }

    subscriptionManager(): SubscriptionManager {
        return getOrCreatePageSubscriptionManager(this.#state, this.#dependencies.pageId);
    }

    subscribeResourceValue(key: string, handler: (data: JsonValue | null) => void): () => void {
        return this.subscriptionManager().subscribeResourceValue(key, handler);
    }

    subscribeResourceState(key: string, handler: ResourceSubscriptionHandler): () => void {
        return this.subscriptionManager().subscribeResourceState(key, handler);
    }

    async subscribeOperations(handler: (event: OperationEvent) => void, options: { allowDiscovery?: boolean; track?: boolean } = {}): Promise<() => void> {
        const runtime = await this.ensureRuntime();
        return subscribeToPageOperations(runtime.resources, runtime.tasks, handler, options, { trackDisposable: (dispose) => this.#dependencies.resources.track(dispose, (callback) => callback()) });
    }

    unsubscribeResourceValue(key: string): void {
        this.subscriptionManager().unsubscribeResource(key);
    }

    subscribeWebSocket(eventName: string, handler: (data: JsonValue | null) => void): () => void {
        return this.subscriptionManager().subscribeWebSocket(eventName, handler);
    }

    unsubscribeWebSocket(eventName: string): void {
        this.subscriptionManager().unsubscribeWebSocket(eventName);
    }

    async ensureSubscriptions(options: { signal?: AbortSignal } = {}): Promise<void> {
        await ensurePageDataSubscriptions(this.subscriptionManager(), options);
    }

    async verifySubscriptions(): Promise<void> {
        await verifyPageSubscriptionsReady(this.#state.subscriptionManager || this.subscriptionManager());
    }

    async runTask<T>(name: string, operation: () => Promise<T>, options: RunPageTaskOptions<T> = {}): Promise<T | null> {
        return runPageTask(createBasePageStreamsTaskHost({ pageId: this.#dependencies.pageId, setLoadingState: (element, loading, text) => this.#dependencies.pageElements.setLoadingState(element, loading, text), showNotification: (message, type) => this.#dependencies.pageContext.notifications.show(message, type), pageContext: this.#dependencies.pageContext }), name, operation, options);
    }

    async cleanup(): Promise<void> {
        await cleanupPageStreamsState(this.#state);
    }

    resetManager(): void {
        this.#state.coreStreamRuntime = null;
    }

    destroy(): void {
        this.#state.autoResourceCleanup?.();
        this.#state.autoResourceOfflineVisible = false;
        this.#state.autoResourceCleanup = null;
        this.resetManager();
    }
}

export { PageStreaming };
export type { PageStreamingContract, PageStreamingDependencies, PageStreamingOwnerHost };
