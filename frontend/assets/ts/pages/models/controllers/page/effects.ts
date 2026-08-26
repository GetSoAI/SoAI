/* SoAI - Models page effects [frontend/assets/ts/pages/models/controllers/page/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { normalizeStatusValue } from '@core/models/modelRecordNormalization.ts';
import { PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, isPluginModelUnavailableStatus } from '@core/state/pluginStatus.ts';
import { isObject } from '@core/typeGuards.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import type { WithLoadingOptions } from '@core/routing/pages/collections/resource/types.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { setupCatalogBackedCollection, type CatalogStore, type CatalogSubscriptionManager } from '@features/catalog/public.ts';
import { requireModelsUi } from '@pages/models/dom.ts';
import type { ModelsUiRefs } from '@pages/models/types.ts';
import type { PageCollectionsHost } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';

interface ModelsPluginState {
    allPlugins: PluginRecord[];
    availablePlugins: PluginRecord[];
    providerPlugins: PluginRecord[];
    downloadPlugins: PluginRecord[];
    pluginLookup: Map<string, PluginRecord>;
}

interface ModelsPluginUiDependencies {
    updateProviderButtonVisibility: () => void;
    updateVirtualModelsButtonVisibility: () => void;
}

interface ModelsCatalogSubscriptionDependencies {
    catalogSubscriptions: CatalogSubscriptionManager;
    collection: CollectionRuntime | null;
    reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean }) => void;
    applyPluginSnapshot: (store: CatalogStore, options?: { plugins?: ReadonlyArray<PluginRecord> | null; updateUI?: boolean; reapply?: boolean }) => void;
}

interface ModelsPagePluginSnapshotHost extends ModelsPluginState, PageCollectionsHost {}

interface ModelsPagePluginSnapshotDependencies {
    providersManager: { updateProviderButtonVisibility(): void };
    updateVirtualModelsButtonVisibility: () => void;
}

interface ModelsPageLoadDataHost {
    cardController: { showLoading(): void; setDataInitialized(): void };
    loadBaseData: (parameters: JsonObject | undefined, context: { signal?: AbortSignal }) => Promise<void>;
    collectionLifecycle: {
        withLoading: <T extends JsonValue | null>(task: () => Promise<T>, options: WithLoadingOptions<T>) => Promise<T>;
    };
    ensureCollectionStream: (options: { allowDiscovery: boolean; signal?: AbortSignal }) => Promise<void>;
    catalogStore: {
        ensureLoaded: (options: { force: boolean }) => Promise<ReadonlyArray<PluginRecord>>;
        ensureCapabilityManifestReady: () => Promise<JsonObject | null>;
    };
    ensureDataSubscriptions: () => Promise<void>;
    setupCatalogSubscription: () => void;
    populateProviderFilter: () => void;
    updateStats: () => void;
    beginRecentItemsSync: () => number;
    armRecentItems: (syncSequence: number) => void;
}

interface ModelsRealtimeRefreshHost {
    refreshModelsCollection: () => Promise<void>;
    refreshPluginCatalog: () => Promise<void>;
    ensureDataSubscriptions: () => Promise<void>;
    reapplyCollection: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean }) => void;
}

type ModelsShellHost = PageDomOwnerHost;

const normalizeCatalogPlugins = (catalogStore: CatalogStore, plugins: ReadonlyArray<PluginRecord>): PluginRecord[] => {
    const normalizedPlugins: PluginRecord[] = [];
    for (const plugin of plugins) {
        const normalized = catalogStore.normalizePlugin(plugin);
        if (normalized) {
            normalizedPlugins.push(normalized);
        }
    }
    return normalizedPlugins;
};

const refreshPluginCaches = (state: ModelsPluginState, catalogStore: CatalogStore, plugins?: ReadonlyArray<PluginRecord> | null): void => {
    const snapshot = plugins ? normalizeCatalogPlugins(catalogStore, plugins) : normalizeCatalogPlugins(catalogStore, catalogStore.getPlugins());
    const available = normalizeCatalogPlugins(catalogStore, catalogStore.getDownloadCapable());
    const providerCapable = normalizeCatalogPlugins(catalogStore, catalogStore.getProviderCapable());

    state.allPlugins.splice(0, state.allPlugins.length, ...snapshot);
    state.availablePlugins.splice(0, state.availablePlugins.length, ...available);
    state.downloadPlugins.splice(0, state.downloadPlugins.length, ...state.availablePlugins.filter((plugin) => plugin?.capabilities?.supportsModelDownload === true));
    state.providerPlugins.splice(0, state.providerPlugins.length, ...providerCapable);

    state.pluginLookup.clear();
    for (const plugin of state.allPlugins) {
        if (!plugin?.name) {
            throw new Error('Catalog store returned plugin without name');
        }
        state.pluginLookup.set(plugin.name, plugin);
        state.pluginLookup.set(plugin.name.toLowerCase(), plugin);
    }
};

const applyPluginSnapshot = (
    state: ModelsPluginState,
    catalogStore: CatalogStore,
    uiDependencies: ModelsPluginUiDependencies,
    {
        plugins,
        updateUI = true,
        reapply = false
    }: {
        plugins?: ReadonlyArray<PluginRecord> | null;
        updateUI?: boolean;
        reapply?: boolean;
    } = {},
    reapplyCollection?: (options: { shouldRender: boolean; updateStats: boolean; updateFilters: boolean }) => void
): void => {
    refreshPluginCaches(state, catalogStore, plugins ?? null);
    if (reapply && reapplyCollection) {
        reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: true });
    }
    if (updateUI) {
        uiDependencies.updateProviderButtonVisibility();
        uiDependencies.updateVirtualModelsButtonVisibility();
    }
};

const setupCatalogSubscription = (dependencies: ModelsCatalogSubscriptionDependencies): void => {
    setupCatalogBackedCollection({
        manager: dependencies.catalogSubscriptions,
        applySnapshot: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>, { reapply }: { reapply: boolean }) => dependencies.applyPluginSnapshot(store, { plugins, updateUI: true, reapply }),
        getCollection: () => dependencies.collection,
        reapplyCollection: () => dependencies.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: true }),
        reapplyOnInitialize: true
    });
};

const applyModelsPagePluginSnapshot = (host: ModelsPagePluginSnapshotHost, store: CatalogStore, dependencies: ModelsPagePluginSnapshotDependencies, { plugins, updateUI = true, reapply = false }: { plugins?: ReadonlyArray<PluginRecord> | null; updateUI?: boolean; reapply?: boolean } = {}): void => {
    const snapshotOptions = typeof plugins === 'undefined' ? { updateUI, reapply } : { plugins, updateUI, reapply };
    applyPluginSnapshot(
        host,
        store,
        {
            updateProviderButtonVisibility: () => dependencies.providersManager.updateProviderButtonVisibility(),
            updateVirtualModelsButtonVisibility: () => dependencies.updateVirtualModelsButtonVisibility()
        },
        snapshotOptions,
        (options) => host.collections.reapply(options)
    );
};

const loadModelsPageData = async (host: ModelsPageLoadDataHost, parameters: JsonObject | undefined, context: { signal?: AbortSignal }): Promise<void> => {
    const recentItemsSync = host.beginRecentItemsSync();
    host.cardController.showLoading();
    await host.loadBaseData(parameters, context);
    if (signalAborted(context.signal ?? null)) return;
    await host.collectionLifecycle.withLoading(
        async () => {
            const streamOptions = context.signal ? { allowDiscovery: true, signal: context.signal } : { allowDiscovery: true };
            await Promise.all([host.ensureCollectionStream(streamOptions), host.catalogStore.ensureLoaded({ force: false }), host.catalogStore.ensureCapabilityManifestReady()]);
            return true;
        },
        context.signal ? { loadingText: i18n.t('models.loading.models'), signal: context.signal } : { loadingText: i18n.t('models.loading.models') }
    );
    if (signalAborted(context.signal ?? null)) return;
    host.cardController.setDataInitialized();
    await host.ensureDataSubscriptions();
    if (signalAborted(context.signal ?? null)) return;
    host.setupCatalogSubscription();
    host.populateProviderFilter();
    host.updateStats();
    host.armRecentItems(recentItemsSync);
};

const refreshModelsPageRealtimeData = async (host: ModelsRealtimeRefreshHost): Promise<void> => {
    await host.ensureDataSubscriptions();
    await Promise.all([host.refreshModelsCollection(), host.refreshPluginCatalog()]);
    host.reapplyCollection({ shouldRender: false, updateStats: true, updateFilters: true });
};

const initializeModelsPageShell = (host: ModelsShellHost): ModelsUiRefs => {
    const ui = requireModelsUi(host);
    const statsContainer = host.pageDom.optional('.ui-page-header-stats');
    if (statsContainer) {
        host.pageDom.setDataAttribute(statsContainer, 'stats-models', 'true');
    }
    return ui;
};

const isDownloadPluginOperational = (catalogStore: CatalogStore, plugin: PluginRecord): boolean => {
    const normalizedCandidate = catalogStore.normalizePlugin(plugin);
    if (!normalizedCandidate) {
        return false;
    }
    const normalizedPlugin = normalizedCandidate;
    const capabilities = normalizedPlugin.capabilities ?? null;
    if (capabilities?.supportsModelDownload !== true || normalizedPlugin.isEnabled === false || normalizedPlugin.isAvailable === false || normalizedPlugin.disabledReason) {
        return false;
    }
    if (catalogStore.isPluginPermanentlyDisabled(normalizedPlugin) || catalogStore.isCircuitBreakerActive(normalizedPlugin)) {
        return false;
    }

    const runtimeStatus = normalizeStatusValue(normalizedPlugin.state);
    if (isPluginModelUnavailableStatus(runtimeStatus)) {
        return false;
    }

    const fileStatus = normalizeStatusValue(normalizedPlugin.fileStatus);
    if (fileStatus === PLUGIN_STATUS_INCOMPATIBLE || fileStatus.includes(PLUGIN_STATUS_DISABLED)) {
        return false;
    }

    const compatibilityFromStore = catalogStore.getPluginCompatibility(normalizedPlugin);
    if (isObject(compatibilityFromStore) && compatibilityFromStore.isCompatible === false) {
        return false;
    }
    return normalizedPlugin.compatibility.isCompatible !== false;
};

const getPluginByName = (state: ModelsPluginState, name: string): PluginRecord | null => {
    const key = String(name);
    return state.pluginLookup.get(key) ?? state.pluginLookup.get(key.toLowerCase()) ?? null;
};

export { applyModelsPagePluginSnapshot, applyPluginSnapshot, getPluginByName, isDownloadPluginOperational, initializeModelsPageShell, loadModelsPageData, normalizeCatalogPlugins, refreshModelsPageRealtimeData, refreshPluginCaches, setupCatalogSubscription };
export type { ModelsCatalogSubscriptionDependencies, ModelsPageLoadDataHost, ModelsPluginState, ModelsPluginUiDependencies, ModelsRealtimeRefreshHost };
