/* SoAI - Plugins page lifecycle controller [frontend/assets/ts/pages/plugins/controllers/lifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { getPageControlSelectOptionValues, syncPageControlSelectValue } from '@core/pagecontrols/selectController.ts';
import { isObject } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { CatalogSubscriptionManager } from '@features/catalog/public.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

interface PluginsLifecycleConfigurationPort {
    getApi(): {
        configs: {
            get(name: string): Promise<JsonObject>;
        };
    };
    getCoreConfigCache(): JsonObject | null;
    setCoreConfigCache(value: JsonObject | null): void;
    getCoreConfigPromise(): Promise<void> | null;
    setCoreConfigPromise(value: Promise<void> | null): void;
    setMaxConcurrentPlugins(value: number | null): void;
    isDestroyed(): boolean;
    resolveMaxConcurrentPlugins(config: JsonObject | null): number | null;
    runWithBoundary<T>(scope: string, task: () => Promise<T>): Promise<T>;
    updateStats(): void;
}

interface PluginsLifecycleFilterPort {
    setFilterProvider(value: string): void;
    setFilterStatus(value: string): void;
    getFilterProvider(): string;
    getFilterStatus(): string;
    setSearchQuery(value: string): void;
}

interface PluginsLifecycleRealtimePort {
    ensureCollectionStream(options: { allowDiscovery: boolean; signal?: AbortSignal | undefined }): Promise<void>;
    ensureDataSubscriptions(options?: { signal?: AbortSignal }): Promise<void>;
    refreshCollectionStream(): Promise<void>;
    reapplyCollection(options: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean }): void;
}

interface PluginsLifecycleServicePort {
    getCatalogStore(): {
        ensureLoaded(options: { force: boolean }): Promise<ReadonlyArray<PluginRecord>>;
    };
    getCatalogSubscriptionManager(): CatalogSubscriptionManager;
    getFirstRunModals(): FirstRunModalService;
    openDownloadPluginModal(): void;
    clearInitialQuery(keys: readonly string[]): void;
}

interface PluginsLifecycleControllerDependencies extends PageDomOwnerHost {
    configuration: PluginsLifecycleConfigurationPort;
    filters: PluginsLifecycleFilterPort;
    realtime: PluginsLifecycleRealtimePort;
    services: PluginsLifecycleServicePort;
}

const buildLifecycleSignalOptions = (signal?: AbortSignal | undefined): { signal?: AbortSignal } => (signal ? { signal } : {});

class PluginsLifecycleController {
    readonly #dependencies: PluginsLifecycleControllerDependencies;
    #initialModal: string | null = null;

    constructor(dependencies: PluginsLifecycleControllerDependencies) {
        this.#dependencies = dependencies;
    }

    async #syncVisibleState({ shouldRender = false, updateFilters = false, signal }: { shouldRender?: boolean; updateFilters?: boolean; signal?: AbortSignal | undefined } = {}): Promise<void> {
        await this.#dependencies.realtime.ensureCollectionStream({ allowDiscovery: true, signal });
        await this.#dependencies.realtime.ensureDataSubscriptions(buildLifecycleSignalOptions(signal));
        if (signalAborted(signal)) {
            return;
        }
        this.#dependencies.realtime.reapplyCollection({ shouldRender, updateStats: true, updateFilters });
    }

    async #refreshRealtimeState({ updateFilters = false, forceCoreConfig = false, signal }: { updateFilters?: boolean; forceCoreConfig?: boolean; signal?: AbortSignal | undefined } = {}): Promise<void> {
        await this.#dependencies.realtime.ensureCollectionStream({ allowDiscovery: true, signal });
        await this.#dependencies.realtime.ensureDataSubscriptions(buildLifecycleSignalOptions(signal));
        if (signalAborted(signal)) {
            return;
        }
        await this.#dependencies.realtime.refreshCollectionStream();
        if (signalAborted(signal)) {
            return;
        }
        this.#dependencies.realtime.reapplyCollection({ shouldRender: false, updateStats: true, updateFilters });
        if (forceCoreConfig) {
            await this.loadCoreConfig({ force: true });
        }
    }

    async loadCoreConfig({ force = false }: { force?: boolean } = {}): Promise<void> {
        return this.#dependencies.configuration.runWithBoundary('plugins:loadCoreConfig', async (): Promise<void> => {
            if (!force && this.#dependencies.configuration.getCoreConfigCache()) return;
            const currentPromise = this.#dependencies.configuration.getCoreConfigPromise();
            if (currentPromise) return currentPromise;
            const nextPromise = (async (): Promise<void> => {
                try {
                    const configCandidate = await this.#dependencies.configuration.getApi().configs.get('core');
                    if (this.#dependencies.configuration.isDestroyed()) {
                        return;
                    }
                    this.#dependencies.configuration.setCoreConfigCache(configCandidate);
                } catch (error) {
                    if (this.#dependencies.configuration.isDestroyed()) {
                        return;
                    }
                    this.#dependencies.configuration.setCoreConfigCache(null);
                    throw error;
                } finally {
                    if (this.#dependencies.configuration.isDestroyed()) {
                        return;
                    }
                    this.#dependencies.configuration.setMaxConcurrentPlugins(this.#dependencies.configuration.resolveMaxConcurrentPlugins(this.#dependencies.configuration.getCoreConfigCache()));
                    this.#dependencies.configuration.updateStats();
                }
            })();
            this.#dependencies.configuration.setCoreConfigPromise(nextPromise);
            try {
                await nextPromise;
            } finally {
                this.#dependencies.configuration.setCoreConfigPromise(null);
            }
        });
    }

    async beforePageInitialize(parameters: JsonValue): Promise<void> {
        this.#dependencies.filters.setSearchQuery('');
        this.#initialModal = isObject(parameters) ? toTrimmedString(parameters['modal']) : null;
    }

    async loadInitialData(): Promise<void> {
        await Promise.all([this.#dependencies.services.getCatalogStore().ensureLoaded({ force: false }), this.loadCoreConfig()]);
    }

    async onRefresh(): Promise<void> {
        await this.#refreshRealtimeState({ forceCoreConfig: true });
    }

    async prepareInitialContent(options: { signal?: AbortSignal | undefined } = {}): Promise<void> {
        await this.#syncVisibleState({ shouldRender: true, updateFilters: true, signal: options.signal });
    }

    async startLiveUpdates(): Promise<void> {
        await this.#dependencies.services.getFirstRunModals().handlePageShow('plugins');
        if (this.#initialModal === 'add-plugin') {
            this.#initialModal = null;
            this.#dependencies.services.openDownloadPluginModal();
            this.#dependencies.services.clearInitialQuery(['modal']);
        }
    }

    async onCollectionShellReady(): Promise<void> {
        const providerFilter = this.#dependencies.pageDom.optional('provider-filter');
        const statusFilter = this.#dependencies.pageDom.optional('status-filter');
        if (providerFilter instanceof HTMLSelectElement) {
            const selection = syncPageControlSelectValue(providerFilter, this.#dependencies.filters.getFilterProvider(), getPageControlSelectOptionValues(providerFilter), 'all');
            this.#dependencies.filters.setFilterProvider(selection.visibleValue);
        }
        if (statusFilter instanceof HTMLSelectElement) {
            const selection = syncPageControlSelectValue(statusFilter, this.#dependencies.filters.getFilterStatus(), getPageControlSelectOptionValues(statusFilter), 'all');
            this.#dependencies.filters.setFilterStatus(selection.visibleValue);
        }
        this.#dependencies.services.getCatalogSubscriptionManager().subscribeToCapabilityManifest({
            onChange: (): void => this.#dependencies.realtime.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: true }),
            emitCurrent: true
        });
    }
}

export { PluginsLifecycleController };
export type { PluginsLifecycleControllerDependencies };
