/* SoAI - Plugins page runtime [frontend/assets/ts/pages/plugins/controllers/page/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem, ResourceOperation } from '@core/data/ClientDataHub.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { createCardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import { pluginsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { PLUGIN_STATUS_BACKEND_INSTALLING, PLUGIN_STATUS_BACKEND_NOT_INSTALLED, PLUGIN_STATUS_INCOMPATIBLE, PLUGIN_STATUS_QUARANTINED } from '@core/state/pluginStatus.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import { isObject } from '@core/typeGuards.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { createCatalogSubscriptionManager } from '@features/catalog/public.ts';
import { C_DISABLED } from '@features/plugins/public.ts';
import type { PluginsPageControllerSet } from '@pages/plugins/controllers/contracts.ts';
import { createPluginsPageModalRuntime } from '@pages/plugins/controllers/page/adapters.ts';
import type { CreatePluginsPageRuntimeDependencies, PluginsControllerResolvers, PluginsPagePrimaryRuntime } from '@pages/plugins/controllers/page/contracts.ts';
import { buildPluginsPageCardHost } from '@pages/plugins/controllers/pluginsPageHosts.ts';
import { PLUGIN_CARD_SELECTOR, PLUGIN_EMPTY_STATES, PLUGINS_GRID } from '@pages/plugins/controllers/pluginsPageRuntimeSupport.ts';
import { PluginsProgressController } from '@pages/plugins/controllers/progressController.ts';
import { createPluginsPageCoreControllersFromHost } from '@pages/plugins/controllers/service.ts';
import { PluginCardRenderer } from '@pages/plugins/rendering/cardrenderer/service.ts';

const createPluginsPagePrimaryRuntime = (dependencies: CreatePluginsPageRuntimeDependencies, resolvers: PluginsControllerResolvers): PluginsPagePrimaryRuntime => {
    const { session, infrastructure, collection } = dependencies;
    const showNotification = (message: string, type?: Parameters<typeof infrastructure.feedback.show>[1], duration?: number): void => infrastructure.feedback.show(message, type, duration);
    let compatibilityNotifier: PluginsPageControllerSet['compatibilityController'] | null = null;

    const coreControllers = createPluginsPageCoreControllersFromHost({
        catalogStore: session.catalogStore,
        host: {
            pendingToggleTargets: session.pendingToggleTargets,
            setItemsFromList: (items: ResourceItem[]): void => {
                collection.setItemsFromList(items);
            },
            reapplyCollection: (options: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean }): void => collection.collections.reapply(options),
            setItemsWithoutEmit: (items: ResourceIncomingValue[]): ResourceOperation[] => collection.setItemsWithoutEmit(items),
            upsertItemWithoutEmit: (item: ResourceItem): ResourceOperation[] => collection.upsertItemWithoutEmit(item),
            getCollectionRuntime: (): CollectionRuntime | null => collection.collections.runtime,
            getMaxConcurrentPlugins: (): number | null => session.maxConcurrentPlugins,
            updateHeaderStat: (id: string, key: string, value: number): void => infrastructure.layout.updateHeaderStat(id, key, value),
            pageDom: infrastructure.pageDom,
            feedback: infrastructure.feedback,
            queueResponsiveLayoutUpdate: (): void => infrastructure.layout.queueResponsive(),
            getStreamTracker: (scope: string) => infrastructure.streaming.tracker(scope),
            startTaskAction: (endpoint: string, options: { method: string }) => infrastructure.streaming.taskAction(endpoint, options),
            runPageTask: (taskKey: string, task: () => Promise<JsonValue | null>, options: { displayName: string; rethrow: boolean }): Promise<JsonValue | null> => infrastructure.streaming.runTask(taskKey, task, options),
            sanitizeText: (value: JsonValue | null | undefined, options?: Record<string, string | null>): string => infrastructure.services.sanitizeText(value === null || value === undefined ? value : String(value), options),
            sanitizeCompatibilityMessage: (value: JsonValue | null | undefined): string => infrastructure.sanitizer.text(value ?? '', { allowEmpty: true })
        },
        notifyPluginIncompatible: (plugin: PluginRecord): void => {
            if (!compatibilityNotifier) {
                throw new Error('Plugins compatibility controller is not initialized');
            }
            compatibilityNotifier.notifyPluginIncompatible(plugin);
        },
        notifyOverrideRequired: (plugin: PluginRecord): void => {
            if (!compatibilityNotifier) {
                throw new Error('Plugins compatibility controller is not initialized');
            }
            compatibilityNotifier.notifyOverrideRequired(plugin);
        },
        showNotification
    });
    compatibilityNotifier = coreControllers.compatibilityController;

    const progressController = new PluginsProgressController({
        pageDom: infrastructure.pageDom,
        pageResources: infrastructure.pageResources,
        progressMetadata: session.progressMetadata,
        modals: infrastructure.services.modals,
        getPluginStatus: (plugin: PluginRecord): string => coreControllers.dataController.getPluginStatus(plugin),
        getBackendStatus: (plugin: PluginRecord): string => coreControllers.dataController.getBackendStatus(plugin),
        getBackendVersion: (plugin: PluginRecord): string => {
            const resolved = coreControllers.dataController.resolvePluginRecord(plugin);
            return String(resolved?.backendVersion ?? '').trim();
        },
        getStatusManager: (): StatusManager => infrastructure.stateManager.status,
        getCurrentManagingPlugin: (): PluginRecord | null => session.currentManagingPlugin
    });

    const catalogSubscriptions = createCatalogSubscriptionManager({
        getStore: () => session.catalogStore,
        requireMessage: 'Plugins page requires an initialized catalog store'
    });

    const cardRenderer = new PluginCardRenderer({
        host: buildPluginsPageCardHost({
            createFragment: (markup: TrustedHtml): DocumentFragment => infrastructure.dom.createFragment(markup),
            sanitizeClassName: (className: string, type: string): string => infrastructure.services.sanitizeClassName(className, type),
            status: {
                presenter: infrastructure.stateManager.status,
                getPluginStatus: (plugin: PluginRecord): string => coreControllers.dataController.getPluginStatus(plugin),
                getBackendStatus: (plugin: PluginRecord): string => coreControllers.dataController.getBackendStatus(plugin),
                getBackendAvailableVariantCount: (plugin: PluginRecord): number | null => coreControllers.dataController.getBackendAvailableVariantCount(plugin)
            },
            compatibility: {
                isHardwareIncompatible: (plugin: PluginRecord): boolean => coreControllers.dataController.isHardwareIncompatible(plugin),
                isCircuitBreakerActive: (plugin: PluginRecord): boolean => coreControllers.dataController.isCircuitBreakerActive(plugin),
                getCircuitBreakerInfo: (plugin: PluginRecord): JsonObject | null => {
                    const info = coreControllers.dataController.getCircuitBreakerInfo(plugin);
                    if (!info) return null;
                    const value = toJsonCompatibleValue(info);
                    return isJsonObject(value) ? value : null;
                },
                requiresCompatibilityOverride: (plugin: PluginRecord): boolean => coreControllers.dataController.requiresCompatibilityOverride(plugin),
                isPluginPermanentlyDisabled: (plugin: PluginRecord): boolean => coreControllers.dataController.isPluginPermanentlyDisabled(plugin),
                getPluginCompatibility: (plugin: PluginRecord) => coreControllers.dataController.getPluginCompatibility(plugin)
            },
            presentation: {
                getPluginLogo: (plugin: PluginRecord): string => coreControllers.dataController.getPluginLogo(plugin),
                getPluginLogoFallback: (plugin: PluginRecord): string => coreControllers.dataController.getPluginLogoFallback(plugin),
                formatPluginName: (name: string | undefined): string => coreControllers.dataController.formatPluginName(name ?? ''),
                getCircuitBreakerNotice: (plugin: PluginRecord): string => coreControllers.compatibilityController.getCircuitBreakerNotice(plugin),
                getIncompatibleNotice: (plugin: PluginRecord): string => coreControllers.compatibilityController.getIncompatibleNotice(plugin),
                sanitizeText: (value: JsonValue | null | undefined, options?: Record<string, string | null>): string => infrastructure.services.sanitizeText(value === null || value === undefined ? value : String(value), options)
            },
            actions: {
                getPendingToggleTarget: (plugin: PluginRecord): boolean | null => {
                    const pluginName = plugin.name;
                    if (!pluginName) return null;
                    const localTarget = session.pendingToggleTargets.get(pluginName);
                    if (localTarget !== undefined) return localTarget;
                    return session.catalogStore.hasPendingOptimisticOperation(pluginName) ? plugin.isEnabled === true : null;
                },
                getItemCardId: (plugin: PluginRecord): string | null => coreControllers.dataController.getItemCardId(plugin),
                isNewItem: (plugin: PluginRecord): boolean => {
                    const identifier = coreControllers.dataController.getItemCardId(plugin);
                    return session.recentItems.isMarked(identifier === null ? null : String(identifier));
                },
                supportsPluginCloning: (plugin: PluginRecord): boolean => coreControllers.dataController.supportsPluginCloning(plugin),
                isPluginStoppable: (plugin: PluginRecord): boolean => coreControllers.dataController.isPluginStoppable(plugin)
            }
        }),
        constants: {
            classNames: { disabled: C_DISABLED },
            statuses: {
                backendNotInstalled: PLUGIN_STATUS_BACKEND_NOT_INSTALLED,
                backendInstalling: PLUGIN_STATUS_BACKEND_INSTALLING,
                incompatible: PLUGIN_STATUS_INCOMPATIBLE,
                quarantined: PLUGIN_STATUS_QUARANTINED
            }
        }
    });

    const cardController = createCardPageController(
        {
            dom: {
                getData: (element: Element, key: string): string | null => infrastructure.dom.getData(element, key),
                setData: (element: Element, key: string, value) => infrastructure.dom.setData(element, key, value)
            },
            optionalUI: (selector: string): Element | null => infrastructure.pageDom.optional(selector),
            toggleHidden: (element: Element | string, hidden: boolean): void => infrastructure.pageElements.toggleHidden(element, hidden),
            flushDOMUpdates: (): void => infrastructure.pageDom.flush(),
            queueResponsiveLayoutUpdate: (): void => infrastructure.layout.queueResponsive()
        },
        {
            dataKey: pluginsPageConfig.dataKey,
            itemLabel: pluginsPageConfig.itemLabel,
            collectionName: pluginsPageConfig.collectionName,
            cardSelector: PLUGIN_CARD_SELECTOR,
            gridSelector: PLUGINS_GRID.gridSelector,
            cacheKey: 'plugins',
            getItemId: (plugin: ResourceIncomingValue | null | undefined) => {
                if (!isObject(plugin)) return null;
                const id = coreControllers.dataController.getItemCardId(plugin);
                return id ? String(id) : null;
            },
            resolveCurrentItem: (identifier: string) => collection.collections.runtime?.find(identifier) ?? null,
            emptyStates: [
                {
                    selector: PLUGIN_EMPTY_STATES.empty,
                    visibleWhen: ({ filtered }) => filtered.length === 0
                }
            ]
        }
    );

    const { managerHostCallbacks, modalManagers } = createPluginsPageModalRuntime({
        dependencies,
        resolvers,
        coreControllers,
        progressController,
        showNotification
    });
    return {
        coreControllers,
        modalManagers,
        progressController,
        catalogSubscriptions,
        cardRenderer,
        cardController,
        managerHostCallbacks
    };
};

export { createPluginsPagePrimaryRuntime };
export type { CreatePluginsPageRuntimeDependencies, PluginsPagePrimaryRuntime };
