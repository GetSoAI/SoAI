/* SoAI - Plugins page collection controller [frontend/assets/ts/pages/plugins/controllers/pluginsCollectionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { normalizeResourceItem } from '@core/data/clientdatahub/guards.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';
import { isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isPluginRecord } from '@core/types/pluginRecordGuards.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { CatalogStore } from '@features/catalog/public.ts';

interface PluginsCollectionControllerOptions {
    catalogStore: CatalogStore;
}

class PluginsCollectionController {
    #catalogStore: CatalogStore;

    constructor(options: PluginsCollectionControllerOptions) {
        this.#catalogStore = options.catalogStore;
    }

    #toJsonPayload(payload: ResourceIncomingValue): JsonValue {
        return isJsonValue(payload) ? payload : toJsonCompatibleValue(payload);
    }

    #toResourceItem(plugin: ResourceIncomingValue | PluginRecord, context: string): ResourceItem {
        return normalizeResourceItem(isJsonValue(plugin) ? plugin : toJsonCompatibleValue(plugin), context);
    }

    updatePluginRuntimeState(pluginName: string, newState: string): PluginRecord | null {
        if (!pluginName || !newState) {
            return null;
        }
        return this.#catalogStore.updateRuntimeState(pluginName, newState);
    }

    updateCircuitBreakerState(pluginName: string, breakerData: JsonObject): PluginRecord | null {
        if (!pluginName || !breakerData || !isObject(breakerData)) {
            return null;
        }
        return this.#catalogStore.updateCircuitBreakerState(pluginName, breakerData);
    }

    updatePluginInstallationState(pluginName: string, newState: string, eventData: { context?: JsonValue } = {}): PluginRecord | null {
        if (!pluginName || !newState) {
            return null;
        }
        const plugin = this.#catalogStore.getPlugin(pluginName);
        if (!plugin) {
            return null;
        }
        return this.#catalogStore.upsertPlugin({
            ...plugin,
            state: newState,
            ...(eventData.context ? { context: eventData.context } : {})
        });
    }

    commitCatalogPlugin(plugin: ResourceIncomingValue): PluginRecord | null {
        const jsonPlugin = this.#toJsonPayload(plugin);
        return isPluginRecord(jsonPlugin) ? this.#catalogStore.upsertPlugin(jsonPlugin) : null;
    }

    removePluginRecord(identifier: JsonValue): boolean {
        const identifierObject = isObject(identifier) ? identifier : null;
        const key = isString(identifier) ? identifier : identifierObject?.['name'] || identifierObject?.['id'] || null;
        return key && isString(key) ? this.#catalogStore.removePlugin(key) : false;
    }

    normalizeItem(plugin: ResourceIncomingValue): ResourceItem {
        if (!isObject(plugin) || isArray(plugin)) {
            return normalizeResourceItem(plugin, 'Plugins collection item');
        }
        if (!isPluginRecord(plugin)) {
            return normalizeResourceItem(plugin, 'Plugins collection item');
        }
        const normalized = this.#catalogStore.normalizePlugin(plugin);
        return this.#toResourceItem(normalized ?? plugin, 'Plugins normalized collection item');
    }
}

export { PluginsCollectionController };
