/* SoAI - Catalog feature contracts [frontend/assets/ts/features/catalog/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CircuitBreakerInfo, CompatibilityInfo, NormalizedPlugin, Plugin } from '@core/types/catalogPluginTypes.ts';
import type { ResourceListener } from '@core/streamTypes.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { ResourceSnapshot } from '@core/realtime/streammanager/types.ts';
import type { OptimisticOperation } from '@core/data/clientdatahub/types.ts';

type StoredPlugin = Omit<PluginRecord, 'compatibility' | 'circuitBreaker'> & NormalizedPlugin;

interface CapabilityManifestState {
    data: JsonObject | null;
    error: Error | null;
}

interface CatalogStreamOptions {
    allowDiscovery?: boolean | undefined;
    immediate?: boolean | undefined;
}

interface StreamResourceApi {
    ensureReady: (options?: CatalogStreamOptions) => Promise<void>;
    ensureResourceStarted: (streamId: string) => Promise<JsonValue>;
    refreshResource: (streamId: string, options?: CatalogStreamOptions) => Promise<JsonValue>;
    subscribeResourceState: (streamId: string, callback: (snapshot: ResourceSnapshot) => void, options?: CatalogStreamOptions) => (() => void) | null;
}

interface CatalogStreamState {
    listeners: Set<(snapshot: JsonObject | null) => void>;
    waiters: Array<{
        resolve: (snapshot: JsonObject | null) => void;
    }>;
}

interface CatalogStreamController {
    getSnapshot: () => JsonObject | null;
    ensureReady: () => Promise<JsonObject | null>;
    subscribe: (listener: (snapshot: JsonObject | null) => void, options?: { emitCurrent?: boolean }) => () => void;
    bind: () => Promise<void>;
}

interface PluginStoreApi {
    ensureLoaded: (options?: { force?: boolean }) => Promise<ReadonlyArray<StoredPlugin>>;
    refresh: () => Promise<ReadonlyArray<StoredPlugin>>;
    subscribe: (callback: ResourceListener<ReadonlyArray<StoredPlugin>>, options?: { emitInitial?: boolean }) => () => void;
    getPlugins: () => ReadonlyArray<StoredPlugin>;
    getPlugin: (name: string) => StoredPlugin | null;
    upsertPlugin: (plugin: JsonObject | PluginRecord) => StoredPlugin | null;
    removePlugin: (name: string | JsonObject | PluginRecord) => boolean;
    beginOptimisticOperation: (operation: OptimisticOperation) => void;
    hasPendingOptimisticOperation: (pluginName: string) => boolean;
    updateRuntimeState: (name: string, newState: string) => StoredPlugin | null;
    updateCircuitBreakerState: (name: string, breakerData: JsonObject) => StoredPlugin | null;
    getDownloadCapable: () => ReadonlyArray<StoredPlugin>;
    getProviderCapable: () => ReadonlyArray<StoredPlugin>;
    isProviderPluginOperational: (plugin: PluginRecord | null | undefined) => boolean;
    getPluginCompatibility: (plugin: Plugin | null | undefined) => CompatibilityInfo;
    getCircuitBreakerInfo: (plugin: Plugin | null | undefined) => CircuitBreakerInfo | null;
    isPluginPermanentlyDisabled: (plugin: Plugin | null | undefined) => boolean;
    isCircuitBreakerActive: (plugin: Plugin | null | undefined) => boolean;
    normalizePlugin: (plugin: Plugin | null | undefined) => Readonly<NormalizedPlugin> | null | undefined;
    getCapabilityManifest: () => JsonObject | null;
    subscribeCapabilityManifest: (callback: (manifest: JsonObject | null) => void, options?: { emitCurrent?: boolean }) => () => void;
    ensureCapabilityManifestReady: () => Promise<JsonObject | null>;
}

export type { CatalogStreamController, CatalogStreamOptions, CatalogStreamState, CapabilityManifestState, PluginStoreApi, StreamResourceApi, StoredPlugin };
