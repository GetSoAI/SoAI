/* SoAI - Plugins page controller host factories [frontend/assets/ts/pages/plugins/controllers/pluginsControllerHostFactories.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { PluginsCompatibilityControllerHost } from '@pages/plugins/controllers/pluginsCompatibilityController.ts';
import { isPluginRecord } from '@core/types/pluginRecordGuards.ts';
import type { PluginsStatsControllerHost } from '@pages/plugins/controllers/pluginsStatsController.ts';
import type { PluginsTaskActionControllerHost } from '@pages/plugins/controllers/pluginsTaskActionController.ts';

interface PluginsCompatibilityControllerHostDependencies {
    resolvePluginRecord: PluginsCompatibilityControllerHost['resolvePluginRecord'];
    getPluginCompatibility: PluginsCompatibilityControllerHost['getPluginCompatibility'];
    sanitizeText: PluginsCompatibilityControllerHost['sanitizeText'];
    sanitizeCompatibilityMessage: PluginsCompatibilityControllerHost['sanitizeCompatibilityMessage'];
    feedback: PluginsCompatibilityControllerHost['feedback'];
    isCircuitBreakerActive: PluginsCompatibilityControllerHost['isCircuitBreakerActive'];
}

interface PluginsStatsControllerHostDependencies {
    getCollectionRuntime: () => CollectionRuntime | null;
    getPluginStatus: PluginsStatsControllerHost['getPluginStatus'];
    isPluginStoppable: PluginsStatsControllerHost['isPluginStoppable'];
    getMaxConcurrentPlugins: PluginsStatsControllerHost['getMaxConcurrentPlugins'];
    findPlugin: PluginsStatsControllerHost['findPlugin'];
    formatPluginName: PluginsStatsControllerHost['formatPluginName'];
    updateHeaderStat: PluginsStatsControllerHost['updateHeaderStat'];
    pageDom: PluginsStatsControllerHost['pageDom'];
    queueResponsiveLayoutUpdate: PluginsStatsControllerHost['queueResponsiveLayoutUpdate'];
}

interface PluginsTaskActionControllerHostDependencies {
    getStreamTracker: PluginsTaskActionControllerHost['getStreamTracker'];
    startTaskAction: PluginsTaskActionControllerHost['startTaskAction'];
    runPageTask: PluginsTaskActionControllerHost['runPageTask'];
}

function createPluginsCompatibilityControllerHost(dependencies: PluginsCompatibilityControllerHostDependencies): PluginsCompatibilityControllerHost {
    return {
        resolvePluginRecord: (plugin: PluginRecord | string | null | undefined): PluginRecord | null => dependencies.resolvePluginRecord(plugin),
        getPluginCompatibility: (plugin: PluginRecord | string | null | undefined) => dependencies.getPluginCompatibility(plugin),
        sanitizeText: (value: JsonValue, options?: Record<string, JsonValue>): string => dependencies.sanitizeText(value, options),
        sanitizeCompatibilityMessage: (value: JsonValue): string => dependencies.sanitizeCompatibilityMessage(value),
        feedback: dependencies.feedback,
        isCircuitBreakerActive: (plugin: PluginRecord | string | null | undefined): boolean => dependencies.isCircuitBreakerActive(plugin)
    };
}

function createPluginsStatsControllerHost(dependencies: PluginsStatsControllerHostDependencies): PluginsStatsControllerHost {
    return {
        getCollectionPlugins: (): PluginRecord[] | null => {
            const collection = dependencies.getCollectionRuntime();
            if (!collection) {
                return null;
            }
            return collection.getAll().filter(isPluginRecord);
        },
        getPluginStatus: (plugin: PluginRecord): string => dependencies.getPluginStatus(plugin),
        isPluginStoppable: (plugin: PluginRecord): boolean => dependencies.isPluginStoppable(plugin),
        getMaxConcurrentPlugins: (): number | null => dependencies.getMaxConcurrentPlugins(),
        findPlugin: (pluginName: string): PluginRecord | null => dependencies.findPlugin(pluginName),
        formatPluginName: (name: string): string => dependencies.formatPluginName(name),
        updateHeaderStat: (id: string, key: string, value: number | string): void => dependencies.updateHeaderStat(id, key, value),
        pageDom: dependencies.pageDom,
        queueResponsiveLayoutUpdate: (): void => dependencies.queueResponsiveLayoutUpdate()
    };
}

function createPluginsTaskActionControllerHost(dependencies: PluginsTaskActionControllerHostDependencies): PluginsTaskActionControllerHost {
    return {
        getStreamTracker: (scope: string) => dependencies.getStreamTracker(scope),
        startTaskAction: (endpoint: string, options: { method: string }) => dependencies.startTaskAction(endpoint, options),
        runPageTask: (taskKey: string, task: () => Promise<JsonValue>, options: { displayName: string; rethrow: boolean }) => dependencies.runPageTask(taskKey, task, options)
    };
}

export { createPluginsCompatibilityControllerHost, createPluginsStatsControllerHost, createPluginsTaskActionControllerHost };
