/* SoAI - Catalog queries over the canonical plugins collection [frontend/assets/ts/features/catalog/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ClientDataHub, ResourceItem } from '@core/data/ClientDataHub.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { toUpperCase } from '@core/normalize.ts';
import { isCircuitBreakerStateActive } from '@core/plugins/circuitBreaker.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import { PLUGIN_STATUS_DISABLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_QUARANTINED, PLUGIN_STATUS_STOPPED } from '@core/state/pluginStatus.ts';
import type { ResourceListener } from '@core/streamTypes.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { isPluginRecord } from '@core/types/pluginRecordGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { TAG } from '@features/catalog/constants.ts';
import { createCatalogCapabilityManifestController } from '@features/catalog/effects.ts';
import { hasUserManagedProviders, isProviderPluginOperational, toCatalogPlugin } from '@features/catalog/mappers.ts';
import { getCircuitBreakerInfo, getPluginCompatibility, isCircuitBreakerActive, isPluginPermanentlyDisabled, normalizePlugin } from '@features/catalog/pluginNormalization.ts';
import type { PluginStoreApi, StoredPlugin } from '@features/catalog/types.ts';
import { createCatalogOptimisticMutations } from '@features/catalog/optimisticMutations.ts';
import type { TaskTerminalListener } from '@core/realtime/streammanager/types.ts';

const toStoredPlugin = (item: ResourceItem): StoredPlugin | null => {
    if (!isPluginRecord(item)) return null;
    const normalized = normalizePlugin(item);
    if (!normalized) return null;
    return Object.freeze({ ...item, ...normalized });
};
const toResourceItem = (plugin: PluginRecord | StoredPlugin | JsonObject): ResourceItem => normalizeResourceItem(toJsonCompatibleValue(plugin), 'Catalog plugin');

const createCatalogStore = (hub: ClientDataHub, taskTerminals: { subscribeTerminalTasks(listener: TaskTerminalListener): () => void }): PluginStoreApi => {
    const listeners = new Set<ResourceListener<ReadonlyArray<StoredPlugin>>>();
    const capabilityManifest = createCatalogCapabilityManifestController();
    const optimisticMutations = createCatalogOptimisticMutations({
        hub,
        subscribeTerminalTasks: (listener) => taskTerminals.subscribeTerminalTasks(listener)
    });
    let initialized = false;

    const snapshot = (): ReadonlyArray<StoredPlugin> =>
        Object.freeze(
            hub
                .snapshot(PLUGINS)
                .items.map(toStoredPlugin)
                .filter((plugin): plugin is StoredPlugin => plugin !== null)
        );

    const notify = (): void => {
        const current = snapshot();
        for (const listener of [...listeners]) {
            try {
                listener(current);
            } catch (error) {
                errorHandler.warn(TAG, 'Listener execution failed', ensureError(error));
            }
        }
    };

    hub.subscribe(PLUGINS, (collectionSnapshot): void => {
        initialized = collectionSnapshot.hasAuthoritativeSnapshot;
        notify();
    });

    const ensureLoaded = async ({ force = false }: { force?: boolean } = {}): Promise<ReadonlyArray<StoredPlugin>> => {
        if (!force && initialized) return snapshot();
        await hub.ensureResource(PLUGINS, force);
        return snapshot();
    };

    const upsertPlugin = (plugin: JsonObject | PluginRecord): StoredPlugin | null => {
        if (!isPluginRecord(plugin)) return null;
        const normalized = normalizePlugin(plugin);
        if (!normalized) return null;
        const merged: StoredPlugin = Object.freeze({ ...plugin, ...normalized });
        hub.applyLocalOperation(PLUGINS, { type: 'upsert', item: toResourceItem(merged) });
        return merged;
    };

    const removePlugin = (nameOrPlugin: string | JsonObject | PluginRecord): boolean => {
        const objectValue = isObject(nameOrPlugin) ? nameOrPlugin : null;
        const key = isString(nameOrPlugin) ? nameOrPlugin : (objectValue?.['name'] ?? objectValue?.['id']);
        if (!isString(key) || !key.trim() || !snapshot().some((plugin) => plugin.name === key || plugin.id === key)) return false;
        hub.applyLocalOperation(PLUGINS, { type: 'remove', id: key });
        return true;
    };

    const updateRuntimeState = (pluginName: string, newState: string): StoredPlugin | null => {
        const current = snapshot().find((plugin) => plugin.name === pluginName) ?? null;
        if (!current || !newState) return null;
        const permanentlyDisabled = isPluginPermanentlyDisabled(toCatalogPlugin(current));
        const breakerActive = isCircuitBreakerActive(toCatalogPlugin(current));
        const state = permanentlyDisabled ? PLUGIN_STATUS_INCOMPATIBLE : breakerActive ? PLUGIN_STATUS_QUARANTINED : toUpperCase(newState);
        return upsertPlugin({ ...current, state, isEnabled: !permanentlyDisabled && !breakerActive && state !== PLUGIN_STATUS_DISABLED });
    };

    const updateCircuitBreakerState = (pluginName: string, breakerData: JsonObject): StoredPlugin | null => {
        const current = snapshot().find((plugin) => plugin.name === pluginName) ?? null;
        if (!current) return null;
        const currentBreaker = isObject(current.circuitBreaker) ? current.circuitBreaker : {};
        const circuitBreaker = getCircuitBreakerInfo({ ...toCatalogPlugin(current), circuitBreaker: { ...currentBreaker, ...breakerData }, circuitBreakerWasEnabled: current.circuitBreakerWasEnabled });
        const candidate = { ...current, circuitBreaker };
        const permanentlyDisabled = isPluginPermanentlyDisabled(toCatalogPlugin(candidate));
        const breakerActive = circuitBreaker !== null && isCircuitBreakerStateActive(circuitBreaker.state, circuitBreaker.isOpen);
        const state = permanentlyDisabled ? PLUGIN_STATUS_INCOMPATIBLE : breakerActive ? PLUGIN_STATUS_QUARANTINED : current.state === PLUGIN_STATUS_QUARANTINED ? PLUGIN_STATUS_STOPPED : current.state;
        return upsertPlugin({ ...candidate, state, isEnabled: !permanentlyDisabled && !breakerActive && circuitBreaker?.wasEnabled === true });
    };

    return Object.freeze({
        ensureLoaded,
        refresh: (): Promise<ReadonlyArray<StoredPlugin>> => ensureLoaded({ force: true }),
        subscribe: (listener: ResourceListener<ReadonlyArray<StoredPlugin>>, { emitInitial = true }: { emitInitial?: boolean } = {}): (() => void) => {
            listeners.add(listener);
            if (emitInitial) {
                try {
                    listener(snapshot());
                } catch (error) {
                    errorHandler.warn(TAG, 'Initial listener execution failed', ensureError(error));
                }
            }
            let active = true;
            return (): void => {
                if (!active) return;
                active = false;
                listeners.delete(listener);
            };
        },
        getPlugins: snapshot,
        getPlugin: (name: string): StoredPlugin | null => snapshot().find((plugin) => plugin.name === name) ?? null,
        upsertPlugin,
        removePlugin,
        beginOptimisticOperation: optimisticMutations.begin,
        hasPendingOptimisticOperation: (pluginName: string): boolean => hub.hasPendingOptimisticOperation(PLUGINS, pluginName),
        updateRuntimeState,
        updateCircuitBreakerState,
        getDownloadCapable: (): ReadonlyArray<StoredPlugin> => snapshot().filter((plugin) => plugin.capabilities?.supportsModelDownload === true || hasUserManagedProviders(toCatalogPlugin(plugin))),
        getProviderCapable: (): ReadonlyArray<StoredPlugin> => snapshot().filter((plugin) => hasUserManagedProviders(toCatalogPlugin(plugin))),
        isProviderPluginOperational,
        getPluginCompatibility,
        getCircuitBreakerInfo,
        isPluginPermanentlyDisabled,
        isCircuitBreakerActive,
        normalizePlugin,
        getCapabilityManifest: capabilityManifest.getSnapshot,
        subscribeCapabilityManifest: capabilityManifest.subscribe,
        ensureCapabilityManifestReady: capabilityManifest.ensureReady
    });
};

export { createCatalogStore };
