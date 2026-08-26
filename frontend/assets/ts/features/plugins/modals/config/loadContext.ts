/* SoAI - Plugins feature load context [frontend/assets/ts/features/plugins/modals/config/loadContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { buildPluginGpuBindingSelectorState, pluginSupportsGpuBinding } from '@features/plugins/modals/config/gpuBindingData.ts';
import { createPluginGpuBindingConfigValue, PLUGIN_GPU_BINDING_KEY, type PluginGpuBindingSelectorState } from '@features/plugins/modals/config/gpuBindingTypes.ts';
import { loadPluginConfig } from '@features/plugins/modals/config/operations.ts';
import type { ConfigManagerHost } from '@features/plugins/modals/config/types.ts';

interface PluginConfigModalLoadContext {
    config: JsonObject | null;
    gpuBindingState: PluginGpuBindingSelectorState | null;
    hideGpuBindingField: boolean;
}

interface LoadPluginConfigModalContextOptions {
    host: ConfigManagerHost;
    plugin: PluginRecord;
}

const configWithBindingValue = (config: JsonObject, gpuBindingState: PluginGpuBindingSelectorState | null): JsonObject => {
    const resolved = Object.fromEntries(Object.entries(config));
    if (gpuBindingState) {
        resolved[PLUGIN_GPU_BINDING_KEY] = createPluginGpuBindingConfigValue(new Set(gpuBindingState.selectedIds));
    }
    return resolved;
};

const loadGpuBindingState = async (host: ConfigManagerHost, plugin: PluginRecord, config: JsonObject): Promise<PluginGpuBindingSelectorState | null> => {
    if (!pluginSupportsGpuBinding(plugin)) {
        return null;
    }
    try {
        const snapshot = await host.api.hardware.snapshot({
            components: ['gpu'],
            useCache: false
        });
        return buildPluginGpuBindingSelectorState(plugin, config, snapshot);
    } catch (error) {
        errorHandler.warn('ConfigManager', 'Failed to load plugin GPU binding hardware snapshot', ensureError(error));
        return null;
    }
};

const loadPluginConfigModalContext = async (options: LoadPluginConfigModalContextOptions): Promise<PluginConfigModalLoadContext> => {
    const pluginName = options.plugin.name;
    if (!pluginName) {
        throw new Error('Plugin config modal requires a plugin name');
    }
    const config = await loadPluginConfig({
        host: options.host,
        pluginName: pluginName
    });
    const hideGpuBindingField = pluginSupportsGpuBinding(options.plugin);
    if (!config) {
        return { config: null, gpuBindingState: null, hideGpuBindingField };
    }
    const gpuBindingState = await loadGpuBindingState(options.host, options.plugin, config);
    return {
        config: hideGpuBindingField ? configWithBindingValue(config, gpuBindingState) : config,
        gpuBindingState,
        hideGpuBindingField
    };
};

export { loadPluginConfigModalContext };
export type { PluginConfigModalLoadContext };
