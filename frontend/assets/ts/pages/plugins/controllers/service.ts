/* SoAI - Plugins page controllers service [frontend/assets/ts/pages/plugins/controllers/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem, ResourceOperation } from '@core/data/ClientDataHub.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import { PLUGIN_ACTIVE_STATUSES } from '@core/state/pluginStatus.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { CatalogStore } from '@features/catalog/public.ts';
import { C_HIDDEN } from '@features/plugins/public.ts';
import type { PluginsPageControllerSet } from '@pages/plugins/controllers/contracts.ts';
import { PluginsDataController } from '@pages/plugins/controllers/dataController.ts';
import { PluginsCollectionController } from '@pages/plugins/controllers/pluginsCollectionController.ts';
import { PluginsCompatibilityController } from '@pages/plugins/controllers/pluginsCompatibilityController.ts';
import { createPluginsCompatibilityControllerHost, createPluginsStatsControllerHost, createPluginsTaskActionControllerHost } from '@pages/plugins/controllers/pluginsControllerHostFactories.ts';
import { PluginsStatsController } from '@pages/plugins/controllers/pluginsStatsController.ts';
import { PluginsTaskActionController, type PluginsTaskActionControllerHost } from '@pages/plugins/controllers/pluginsTaskActionController.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';

interface CreatePluginsPageCoreControllersDependencies {
    catalogStore: CatalogStore;
    host: PluginsPageCoreControllersHostBase;
    notifyPluginIncompatible(plugin: PluginRecord): void;
    notifyOverrideRequired(plugin: PluginRecord): void;
    showNotification(message: string, type?: NotificationType, duration?: number): void;
    sanitizeText(value: JsonValue | null | undefined, options?: Record<string, string | null>): string;
    sanitizeCompatibilityMessage(value: JsonValue | null | undefined): string;
}

interface PluginsPageCoreControllersHostBase extends PageDomOwnerHost, PageFeedbackOwnerHost {
    pendingToggleTargets: Map<string, boolean>;
    setItemsFromList(items: ResourceItem[]): void;
    reapplyCollection(options: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean }): void;
    setItemsWithoutEmit(items: ResourceIncomingValue[]): ResourceOperation[];
    upsertItemWithoutEmit(item: ResourceItem): ResourceOperation[];
    getCollectionRuntime(): CollectionRuntime | null;
    getMaxConcurrentPlugins(): number | null;
    updateHeaderStat(id: string, key: string, value: number | string): void;
    queueResponsiveLayoutUpdate(): void;
    getStreamTracker: PluginsTaskActionControllerHost['getStreamTracker'];
    startTaskAction: PluginsTaskActionControllerHost['startTaskAction'];
    runPageTask: PluginsTaskActionControllerHost['runPageTask'];
    sanitizeText(value: JsonValue | null | undefined, options?: Record<string, string | null>): string;
    sanitizeCompatibilityMessage(value: JsonValue | null | undefined): string;
}

const createPluginsPageCoreControllers = (dependencies: CreatePluginsPageCoreControllersDependencies): Pick<PluginsPageControllerSet, 'compatibilityController' | 'dataController' | 'collectionController' | 'statsController' | 'taskActionController'> => {
    const dataController = new PluginsDataController({
        catalogStore: dependencies.catalogStore,
        setItemsFromList: (items: ResourceItem[]): void => {
            dependencies.host.setItemsFromList(items);
        },
        reapplyCollection: (): void => dependencies.host.reapplyCollection({ shouldRender: true, updateStats: true, updateFilters: true }),
        notifyPluginIncompatible: (plugin: PluginRecord): void => dependencies.notifyPluginIncompatible(plugin),
        notifyOverrideRequired: (plugin: PluginRecord): void => dependencies.notifyOverrideRequired(plugin)
    });

    const compatibilityController = new PluginsCompatibilityController(
        createPluginsCompatibilityControllerHost({
            resolvePluginRecord: (plugin) => dataController.resolvePluginRecord(plugin),
            getPluginCompatibility: (plugin) => dataController.getPluginCompatibility(plugin),
            sanitizeText: (value: JsonValue | null | undefined, options?: Record<string, string | null>): string => dependencies.sanitizeText(value, options),
            sanitizeCompatibilityMessage: (value: JsonValue | null | undefined): string => dependencies.sanitizeCompatibilityMessage(value),
            feedback: dependencies.host.feedback,
            isCircuitBreakerActive: (plugin): boolean => dataController.isCircuitBreakerActive(plugin)
        })
    );

    const collectionController = new PluginsCollectionController({ catalogStore: dependencies.catalogStore });

    const statsController = new PluginsStatsController({
        host: createPluginsStatsControllerHost({
            getCollectionRuntime: (): CollectionRuntime | null => dependencies.host.getCollectionRuntime(),
            getPluginStatus: (plugin: PluginRecord): string => dataController.getPluginStatus(plugin),
            isPluginStoppable: (plugin: PluginRecord): boolean => dataController.isPluginStoppable(plugin),
            getMaxConcurrentPlugins: (): number | null => dependencies.host.getMaxConcurrentPlugins(),
            findPlugin: (pluginName: string): PluginRecord | null => {
                const plugin = dependencies.host.getCollectionRuntime()?.find(pluginName) ?? null;
                return dataController.resolvePluginRecord(plugin);
            },
            formatPluginName: (name: string): string => dataController.formatPluginName(name),
            updateHeaderStat: (id: string, key: string, value: number | string): void => dependencies.host.updateHeaderStat(id, key, value),
            pageDom: dependencies.host.pageDom,
            queueResponsiveLayoutUpdate: (): void => dependencies.host.queueResponsiveLayoutUpdate()
        }),
        classes: { hidden: C_HIDDEN },
        statuses: { activeStatusSet: PLUGIN_ACTIVE_STATUSES }
    });

    const taskActionController = new PluginsTaskActionController(
        createPluginsTaskActionControllerHost({
            getStreamTracker: (scope: string) => dependencies.host.getStreamTracker(scope),
            startTaskAction: (endpoint: string, options: { method: string }) => dependencies.host.startTaskAction(endpoint, options),
            runPageTask: (taskKey: string, task: () => Promise<JsonValue | null>, options: { displayName: string; rethrow: boolean }): Promise<JsonValue | null> => dependencies.host.runPageTask(taskKey, task, options)
        })
    );

    return {
        compatibilityController,
        dataController,
        collectionController,
        statsController,
        taskActionController
    };
};

const createPluginsPageCoreControllersFromHost = (dependencies: { catalogStore: CatalogStore; host: PluginsPageCoreControllersHostBase; notifyPluginIncompatible(plugin: PluginRecord): void; notifyOverrideRequired(plugin: PluginRecord): void; showNotification(message: string, type?: NotificationType, duration?: number): void }): Pick<PluginsPageControllerSet, 'compatibilityController' | 'dataController' | 'collectionController' | 'statsController' | 'taskActionController'> => {
    return createPluginsPageCoreControllers({
        catalogStore: dependencies.catalogStore,
        host: dependencies.host,
        notifyPluginIncompatible: (plugin: PluginRecord): void => dependencies.notifyPluginIncompatible(plugin),
        notifyOverrideRequired: (plugin: PluginRecord): void => dependencies.notifyOverrideRequired(plugin),
        showNotification: dependencies.showNotification,
        sanitizeText: (value: JsonValue | null | undefined, options?: Record<string, string | null>): string => dependencies.host.sanitizeText(value === null || value === undefined ? value : String(value), options),
        sanitizeCompatibilityMessage: (value: JsonValue | null | undefined): string => dependencies.host.sanitizeCompatibilityMessage(value)
    });
};

export { createPluginsPageCoreControllers, createPluginsPageCoreControllersFromHost };
export type { CreatePluginsPageCoreControllersDependencies, PluginsPageCoreControllersHostBase };
