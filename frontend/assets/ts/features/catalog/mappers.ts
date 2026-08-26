/* SoAI - Catalog feature mappers [frontend/assets/ts/features/catalog/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toUpperCase } from '@core/normalize.ts';
import { parsePluginsCollectionState, type PluginCollectionEntry } from '@core/plugins/collectionSnapshot.ts';
import { PLUGIN_STATUS_INCOMPATIBLE, isPluginInstallUnavailableStatus, isPluginModelUnavailableStatus } from '@core/state/pluginStatus.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { CompatibilityInfo, Plugin } from '@core/types/catalogPluginTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { getPluginCompatibility, PROVIDER_MODE, resolveProviderMode } from '@features/catalog/pluginNormalization.ts';
import type { StoredPlugin } from '@features/catalog/types.ts';

const isRuntimeStateUnavailable = (state: string, compatibility: CompatibilityInfo): boolean => {
    return Boolean(state && isPluginModelUnavailableStatus(state) && !(state === PLUGIN_STATUS_INCOMPATIBLE && compatibility.isOverridden));
};

const isProviderRuntimeStateUnavailable = (state: string, compatibility: CompatibilityInfo): boolean => {
    return isRuntimeStateUnavailable(state, compatibility) && !isPluginInstallUnavailableStatus(state);
};

const extractPluginArray = (payload: JsonValue): PluginCollectionEntry[] => parsePluginsCollectionState(payload);

const toCatalogPlugin = (plugin: StoredPlugin): Plugin => {
    const result: Plugin = { compatibility: plugin.compatibility };
    if (plugin.name !== undefined) result.name = plugin.name;
    const displayName = plugin.displayName;
    if (displayName !== undefined) {
        if (!isString(displayName)) {
            throw new Error('Stored plugin displayName must be a string');
        }
        result.displayName = displayName;
    }
    if (plugin.state !== undefined) result.state = plugin.state;
    if (plugin.isEnabled !== undefined) result.isEnabled = plugin.isEnabled;
    if (plugin.isAvailable !== undefined) result.isAvailable = plugin.isAvailable;
    if (plugin.permanentlyDisabled !== undefined) result.permanentlyDisabled = plugin.permanentlyDisabled;
    if (plugin.isPersistent !== undefined) result.isPersistent = plugin.isPersistent;
    if (plugin.isBuiltin !== undefined) result.isBuiltin = plugin.isBuiltin;
    if (plugin.circuitBreakerWasEnabled !== undefined) result.circuitBreakerWasEnabled = plugin.circuitBreakerWasEnabled;
    if (plugin.incompatibility !== undefined) result.incompatibility = plugin.incompatibility;
    if (plugin.capabilities !== undefined) result.capabilities = plugin.capabilities;
    if (plugin.circuitBreaker) result.circuitBreaker = plugin.circuitBreaker;
    return result;
};

const hasUserManagedProviders = (plugin: Plugin | null | undefined): boolean => resolveProviderMode(plugin) === PROVIDER_MODE.USER_MANAGED;

const isProviderPluginOperational = (plugin: PluginRecord | null | undefined): boolean => {
    if (!hasUserManagedProviders(plugin)) return false;
    if (!plugin || !isObject(plugin)) return false;
    const candidateObject = plugin;
    if (candidateObject.isEnabled === false || candidateObject.isAvailable === false || candidateObject.disabledReason) {
        return false;
    }
    const state = toUpperCase(candidateObject['state']);
    const compatibility = getPluginCompatibility(candidateObject);
    if (compatibility.permanentlyDisabled || !compatibility.isCompatible) return false;
    if (isProviderRuntimeStateUnavailable(state, compatibility)) return false;
    return true;
};

export { extractPluginArray, hasUserManagedProviders, isProviderPluginOperational, toCatalogPlugin };
