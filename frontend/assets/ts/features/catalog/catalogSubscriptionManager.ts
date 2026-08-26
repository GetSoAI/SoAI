/* SoAI - Catalog feature subscription manager [frontend/assets/ts/features/catalog/catalogSubscriptionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFunction } from '@core/typeGuards.ts';
import type { CircuitBreakerInfo, CompatibilityInfo, NormalizedPlugin, Plugin } from '@core/types/catalogPluginTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';

interface CatalogStore {
    subscribe: (callback: (plugins: ReadonlyArray<PluginRecord>) => void, options?: { emitInitial?: boolean }) => () => void;
    subscribeCapabilityManifest: (callback: (manifest: JsonObject | null) => void, options?: { emitCurrent?: boolean }) => () => void;
    ensureLoaded: (options?: { force?: boolean }) => Promise<ReadonlyArray<PluginRecord>>;
    refresh: () => Promise<ReadonlyArray<PluginRecord>>;
    getPlugins: () => ReadonlyArray<PluginRecord>;
    getPlugin: (name: string) => PluginRecord | null;
    getCapabilityManifest: () => JsonObject | null;
    upsertPlugin: (plugin: JsonObject | PluginRecord) => PluginRecord | null;
    removePlugin: (name: string) => boolean;
    beginOptimisticOperation: (operation: OptimisticOperation) => void;
    hasPendingOptimisticOperation: (pluginName: string) => boolean;
    updateRuntimeState: (name: string, state: string) => PluginRecord | null;
    updateCircuitBreakerState: (name: string, breaker: JsonObject) => PluginRecord | null;
    getDownloadCapable: () => ReadonlyArray<PluginRecord>;
    getProviderCapable: () => ReadonlyArray<PluginRecord>;
    ensureCapabilityManifestReady: () => Promise<JsonObject | null>;
    normalizePlugin: (plugin: Plugin | null | undefined) => Readonly<NormalizedPlugin> | null | undefined;
    getCircuitBreakerInfo: (plugin: Plugin | null | undefined) => CircuitBreakerInfo | null;
    isPluginPermanentlyDisabled: (plugin: Plugin | null | undefined) => boolean;
    isCircuitBreakerActive: (plugin: Plugin | null | undefined) => boolean;
    getPluginCompatibility: (plugin: Plugin | null | undefined) => CompatibilityInfo;
    isProviderPluginOperational: (plugin: PluginRecord | null | undefined) => boolean;
}

interface CatalogSubscriptionManagerOptions {
    getStore?: (() => CatalogStore | null) | CatalogStore | null;
    requireMessage?: string;
}

interface SubscribeToCatalogOptions {
    onChange?: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>) => void;
    emitInitial?: boolean;
    onInitialize?: (store: CatalogStore) => void;
}

interface SubscribeToCapabilityManifestOptions {
    onChange?: (store: CatalogStore) => void;
    emitCurrent?: boolean;
}

interface CatalogSubscriptionManager {
    requireStore: () => CatalogStore;
    subscribeToCatalog: (options?: SubscribeToCatalogOptions) => () => void;
    subscribeToCapabilityManifest: (options?: SubscribeToCapabilityManifestOptions) => () => void;
    cleanup: () => void;
}

interface SubscribeCollectionWithCatalogOptions<C> {
    manager: CatalogSubscriptionManager;
    onCatalogChange: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>) => void;
    onCatalogInitialize: (store: CatalogStore) => void;
    getCollection: (store: CatalogStore) => C;
    reapplyCollection: (store: CatalogStore) => void;
}

const createCatalogSubscriptionManager = ({ getStore, requireMessage = 'Catalog store is required' }: CatalogSubscriptionManagerOptions = {}): CatalogSubscriptionManager => {
    let catalogUnsubscribe: (() => void) | null = null;
    let capabilityUnsubscribe: (() => void) | null = null;

    const requireStore = (): CatalogStore => {
        const store = isFunction(getStore) ? getStore() : getStore;
        if (!store) throw new Error(requireMessage);
        return store;
    };

    const subscribeToCatalog = ({ onChange, emitInitial = false, onInitialize }: SubscribeToCatalogOptions = {}): (() => void) => {
        const store = requireStore();
        if (!isFunction(store.subscribe)) throw new Error('Catalog store subscribe is unavailable');
        if (!isFunction(onChange)) throw new Error('Catalog subscription requires a change handler');
        catalogUnsubscribe?.();
        catalogUnsubscribe = store.subscribe((plugins: ReadonlyArray<PluginRecord>) => onChange(store, plugins), {
            emitInitial
        });
        if (isFunction(onInitialize)) onInitialize(store);
        return catalogUnsubscribe;
    };

    const subscribeToCapabilityManifest = ({ onChange, emitCurrent = false }: SubscribeToCapabilityManifestOptions = {}): (() => void) => {
        const store = requireStore();
        if (!isFunction(store.subscribeCapabilityManifest)) throw new Error('Catalog store capability manifest subscribe is unavailable');
        if (!isFunction(onChange)) throw new Error('Catalog capability subscription requires a change handler');
        capabilityUnsubscribe?.();
        capabilityUnsubscribe = store.subscribeCapabilityManifest(() => onChange(store), { emitCurrent });
        return capabilityUnsubscribe;
    };

    const cleanup = (): void => {
        catalogUnsubscribe?.();
        capabilityUnsubscribe?.();
        catalogUnsubscribe = null;
        capabilityUnsubscribe = null;
    };

    return Object.freeze({
        requireStore,
        subscribeToCatalog,
        subscribeToCapabilityManifest,
        cleanup
    });
};

const subscribeCollectionWithCatalog = <C>({ manager, onCatalogChange, onCatalogInitialize, getCollection, reapplyCollection }: SubscribeCollectionWithCatalogOptions<C>): void => {
    if (!manager || !isFunction(manager.subscribeToCatalog) || !isFunction(manager.subscribeToCapabilityManifest)) {
        throw new Error('Catalog subscription manager must provide subscription support APIs');
    }
    if (!isFunction(onCatalogChange) || !isFunction(onCatalogInitialize)) {
        throw new Error('Catalog collection subscription requires catalog callbacks');
    }
    if (!isFunction(getCollection) || !isFunction(reapplyCollection)) {
        throw new Error('Catalog collection subscription requires collection callbacks');
    }

    manager.subscribeToCatalog({
        onChange: (store: CatalogStore, plugins: ReadonlyArray<PluginRecord>) => onCatalogChange(store, plugins),
        emitInitial: false,
        onInitialize: (store: CatalogStore) => onCatalogInitialize(store)
    });

    manager.subscribeToCapabilityManifest({
        onChange: (store: CatalogStore) => {
            const collection = getCollection(store);
            if (!collection) return;
            reapplyCollection(store);
        },
        emitCurrent: false
    });
};

export { createCatalogSubscriptionManager, subscribeCollectionWithCatalog };
export type { CatalogStore, CatalogSubscriptionManager, CatalogSubscriptionManagerOptions, SubscribeToCatalogOptions, SubscribeToCapabilityManifestOptions, SubscribeCollectionWithCatalogOptions };
