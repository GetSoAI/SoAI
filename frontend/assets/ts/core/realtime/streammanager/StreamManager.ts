/* SoAI - Frontend realtime resource orchestration composition root [frontend/assets/ts/core/realtime/streammanager/StreamManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getEventHub } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { LifecycleCancellationError, isLifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { getMaintenanceCoordinator } from '@core/maintenanceCoordinator.ts';
import { StreamTaskRuntime } from '@core/realtime/streammanager/actions/service.ts';
import { reconcilePluginMutationTerminal } from '@core/realtime/streammanager/actions/mutationTerminalReconciliation.ts';
import { isStreamManagerDependencies } from '@core/realtime/streammanager/internals.ts';
import { StreamResourceLoader } from '@core/realtime/streammanager/resourceLoader.ts';
import { StreamReadiness } from '@core/realtime/streammanager/streamReadiness.ts';
import { registerDefaultResources } from '@core/realtime/streammanager/resources/registerDefaultResources.ts';
import { StreamResourceStore } from '@core/realtime/streammanager/resourceStore.ts';
import { DEFAULT_BUNDLES } from '@core/realtime/streammanager/subscriptions/defaultResourceGroups.ts';
import { StreamTransport } from '@core/realtime/streammanager/streamTransport.ts';
import { StreamSubscriptions } from '@core/realtime/streammanager/streamSubscriptions.ts';
import type { StreamManagerDependencies } from '@core/realtime/streammanager/types.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { ConnectionService, ConnectionStatusEvent } from '@core/types/streamTypes.ts';

const MODULE = 'StreamManager';

class StreamManager {
    #document = dom.getDocument();
    #connectionState: StreamManagerDependencies['connectionState'];
    #auth: StreamManagerDependencies['auth'];
    #tracker = new ResourceTracker();
    #store: StreamResourceStore;
    #loader: StreamResourceLoader;
    #tasks: StreamTaskRuntime;
    #transport: StreamTransport;
    #maintenanceUnsubscribe: (() => void) | null = null;
    #disposed = false;
    #generation = 0;
    readonly resources: StreamResourceLoader;
    readonly subscriptions: StreamSubscriptions;
    readonly tasks: StreamTaskRuntime;
    readonly connection: StreamTransport;

    constructor(dependencies: StreamManagerDependencies) {
        if (!isStreamManagerDependencies(dependencies)) throw new Error('StreamManager requires initialized core dependencies');
        this.#connectionState = dependencies.connectionState;
        this.#auth = dependencies.auth;
        this.#store = new StreamResourceStore(dependencies.state);
        this.#transport = new StreamTransport({
            auth: dependencies.auth,
            onInterestRejected: (resources) => {
                for (const resourceName of resources) this.#store.get(resourceName)?.reconciler.markUnavailable('resource-interest-rejected');
            }
        });
        const readiness = new StreamReadiness({ auth: dependencies.auth, tracker: this.#tracker, initializeTransport: () => this.#transport.ensureInitialized() });
        this.#loader = new StreamResourceLoader(dependencies.apiClient, this.#store, readiness, this.#transport);
        this.#tasks = new StreamTaskRuntime({
            module: MODULE,
            eventTarget: this.#store.eventTarget,
            apiClient: dependencies.apiClient,
            request: (endpoint, options) => this.#loader.request(endpoint, options),
            getWebSocket: () => this.#transport.webSocket,
            safe: (callback, ...inputArguments) => this.#store.safe(callback, ...inputArguments)
        });
        this.resources = this.#loader;
        this.subscriptions = new StreamSubscriptions(this.#store, this.#loader, this.#transport);
        this.tasks = this.#tasks;
        this.connection = this.#transport;
        this.#tracker.track(
            this.#transport.subscribeEvents((eventType, data, context) => {
                this.#store.handleWebSocketEvent(
                    eventType,
                    data,
                    context,
                    (type, payload) => this.#tasks.handleTaskWebSocketEvent(type, payload),
                    (name, options) => this.#loader.startResource(name, options)
                );
            })
        );
        this.#tracker.track(this.#transport.subscribeConnected(() => this.#handleConnected()));
        this.#tracker.track(
            this.#tasks.subscribeTerminalTasks((event) => {
                void reconcilePluginMutationTerminal(event, (resourceName) => this.#loader.refresh(resourceName, { allowDiscovery: true })).catch((error) => {
                    errorHandler.warn(MODULE, 'Plugin mutation terminal refresh failed', ensureError(error));
                });
            })
        );
        this.#registerDefaults();
        this.#bindLifecycle();
        this.#transport.initialize();
    }

    #registerDefaults(): void {
        registerDefaultResources({
            registerResource: (name, config) => {
                this.#loader.registerResource(name, config);
            },
            createApiFetcher: (endpoint) => this.#loader.createApiFetcher(endpoint),
            createGpuSlotsResource: () => this.#loader.createGpuSlotsResource()
        });
        DEFAULT_BUNDLES.forEach(([name, config]) => this.#store.defineBundle(name, config));
    }

    async #handleConnected(): Promise<void> {
        const generation = this.#generation;
        if (this.#disposed) return;
        try {
            await this.#transport.syncInterests();
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!isLifecycleCancellationError(runtimeError) && !isAbortError(runtimeError)) errorHandler.warn(MODULE, 'Live resource interest sync failed', runtimeError);
        }
        if (!this.#isCurrent(generation)) return;
        const refreshes = this.#store.activeReconnectResources().map((name) =>
            this.#loader.startResource(name, { forceRefresh: true }).catch((error) => {
                const runtimeError = ensureError(error);
                if (runtimeError.message !== 'Maintenance' && !isLifecycleCancellationError(runtimeError) && !isAbortError(runtimeError)) errorHandler.warn(MODULE, `Auto-refresh failed for ${name}`, runtimeError);
            })
        );
        await Promise.all(refreshes);
        if (!this.#isCurrent(generation)) return;
        try {
            await this.#tasks.reconnectOperations();
        } catch (error) {
            errorHandler.debug(MODULE, 'Operation reconnect on websocket connect failed', ensureError(error));
        }
    }

    #bindLifecycle(): void {
        this.#tracker.addEventListener(
            this.#document,
            'visibilitychange',
            () => {
                if (!this.#document.hidden && this.ready) this.#loader.startAutoOwned('Visibility auto-resource start');
            },
            { passive: true }
        );
        this.#tracker.track(
            this.#connectionState.onChange(
                (url) => {
                    if (url && this.ready) this.#loader.startAutoOwned('Connection auto-resource start');
                },
                { immediate: false }
            )
        );
        this.#tracker.addEventListener(
            getEventHub(),
            'soai:wizard:completed',
            () => {
                if (!this.ready && !this.#loader.shouldDeferInitialization()) this.#loader.settleDeferredReady();
            },
            { passive: true }
        );
        if (this.#auth) {
            const unsubscribe = this.#auth.onLogin(() => this.#loader.settleDeferredReady());
            if (isFunction(unsubscribe)) this.#tracker.track(unsubscribe);
        }
        this.#maintenanceUnsubscribe = getMaintenanceCoordinator().subscribe((state) => {
            if (state.pausesTransport) {
                this.#loader.enterMaintenance(state.reason ?? null);
                return;
            }
            this.#loader.exitMaintenance().catch((error) => errorHandler.error(MODULE, 'Maint exit failed', ensureError(error)));
        });
    }

    reset(): void {
        if (this.#disposed) return;
        this.#generation += 1;
        this.#loader.reset(true);
        this.#tasks.reset();
    }

    resetAllResourceRuntimeState(): void {
        if (this.#disposed) return;
        this.#generation += 1;
        this.#loader.reset(false);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#generation += 1;
        this.#maintenanceUnsubscribe?.();
        this.#maintenanceUnsubscribe = null;
        this.subscriptions.dispose();
        this.#loader.dispose();
        this.#tasks.reset();
        this.#transport.dispose();
        this.#tracker.cleanup();
    }

    attachConnectionStatus(manager: ConnectionService | null | undefined): () => void {
        if (this.#disposed) throw new LifecycleCancellationError('Stream manager is disposed', 'stream-manager-disposed');
        if (!isFunction(manager?.subscribe)) return () => {};
        return manager.subscribe((event: ConnectionStatusEvent) => {
            if (!this.#disposed && event?.eventType === 'connected' && event.connected && this.ready) {
                this.#transport.ensureInitialized();
                this.#loader.startAutoOwned('Connection status auto-resource start');
            }
        });
    }

    get ready(): boolean {
        return this.#loader.ready;
    }

    #isCurrent(generation: number): boolean {
        return !this.#disposed && generation === this.#generation;
    }
}

export { StreamManager };
