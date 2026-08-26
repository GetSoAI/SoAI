/* SoAI - Plugins page service [frontend/assets/ts/pages/plugins/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { shouldPreventDefaultExceptFileActionElement } from '@core/dom/dataAction.ts';
import { PLUGINS } from '@core/realtime/streammanager/resources/ids.ts';
import { buildRouteWithoutQueryParameters } from '@core/routing/router/events.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import type { SortDirection } from '@core/ui/tables/sortableTable.ts';
import type { CatalogSubscriptionManager } from '@features/catalog/public.ts';
import type { PluginActionHost } from '@features/plugins/public.ts';
import { createPluginsActionHost } from '@pages/plugins/controllers/hosts.ts';
import { PluginsInteractionController } from '@pages/plugins/controllers/interactionController.ts';
import { PluginsLifecycleController } from '@pages/plugins/controllers/lifecycleController.ts';
import { PluginsOperationsController } from '@pages/plugins/controllers/operationsController.ts';
import { sortPluginsListFromHeader, type PluginsListSortHost } from '@pages/plugins/controllers/page/listSortingController.ts';
import { createPluginsPagePrimaryRuntime, type CreatePluginsPageRuntimeDependencies } from '@pages/plugins/controllers/page/runtime.ts';
import { createPluginsRootEventController, type PluginsRootEventController } from '@pages/plugins/controllers/pluginsRootEventController.ts';
import { PluginsProgressController } from '@pages/plugins/controllers/progressController.ts';
import { PluginsStateActionsController } from '@pages/plugins/controllers/stateActionsController.ts';
import type { PluginsActionId } from '@pages/plugins/actions.ts';
import type { PluginCardRenderer } from '@pages/plugins/rendering/cardrenderer/service.ts';
import { PluginsCollectionPresentationController } from '@pages/plugins/controllers/page/PluginsCollectionPresentationController.ts';

interface PluginsPageRuntimeBundle {
    coreControllers: ReturnType<typeof createPluginsPagePrimaryRuntime>['coreControllers'];
    modalManagers: ReturnType<typeof createPluginsPagePrimaryRuntime>['modalManagers'];
    progressController: PluginsProgressController;
    operationsController: PluginsOperationsController;
    stateActionsController: PluginsStateActionsController;
    lifecycleController: PluginsLifecycleController;
    interactionController: PluginsInteractionController;
    rootEventController: PluginsRootEventController;
    pluginActionHost: PluginActionHost;
    catalogSubscriptions: CatalogSubscriptionManager;
    cardRenderer: PluginCardRenderer;
    cardController: CardPageController;
    presentationController: PluginsCollectionPresentationController;
}

const createPluginsPageRuntime = (dependencies: CreatePluginsPageRuntimeDependencies): PluginsPageRuntimeBundle => {
    const { session, infrastructure, collection, filters, pageDependencies, runBoundary } = dependencies;
    const showNotification = (message: string, type?: Parameters<typeof infrastructure.feedback.show>[1], duration?: number): void => infrastructure.feedback.show(message, type, duration);
    let operationsController: PluginsOperationsController | null = null;
    let lifecycleController: PluginsLifecycleController | null = null;

    const primaryRuntime = createPluginsPagePrimaryRuntime(dependencies, {
        getOperationsController: (): PluginsOperationsController | null => operationsController,
        getLifecycleController: (): PluginsLifecycleController | null => lifecycleController
    });
    session.cardRenderer = primaryRuntime.cardRenderer;
    session.cardController = primaryRuntime.cardController;

    const listSortHost: PluginsListSortHost = {
        services: infrastructure.services,
        pageElements: infrastructure.pageElements,
        pageDom: infrastructure.pageDom,
        storage: pageDependencies.storage,
        get sortBy(): string | null {
            return filters.getSortBy();
        },
        set sortBy(value: string | null) {
            filters.setSortBy(value);
        },
        get sortOrder(): SortDirection | null {
            return filters.getSortOrder();
        },
        set sortOrder(value: SortDirection | null) {
            filters.setSortOrder(value);
        }
    };

    const presentationController = new PluginsCollectionPresentationController({
        session,
        collections: collection.collections,
        pageDom: infrastructure.pageDom,
        services: infrastructure.services,
        pageElements: infrastructure.pageElements,
        router: infrastructure.router,
        layout: infrastructure.layout,
        filters,
        dataController: primaryRuntime.coreControllers.dataController,
        storage: pageDependencies.storage
    });

    operationsController = new PluginsOperationsController({
        page: {
            pageDom: infrastructure.pageDom,
            feedback: infrastructure.feedback
        },
        collection: {
            deletingItems: session.deletingItems,
            getCollectionRuntime: () => collection.collections.runtime,
            getCatalogPlugin: (identifier: string): PluginRecord | null => session.catalogStore.getPlugin(identifier),
            beginOptimisticOperation: (operation): void => session.catalogStore.beginOptimisticOperation(operation),
            sanitizeText: (value: JsonValue | null | undefined): string => infrastructure.services.sanitizeText(value === null || value === undefined ? value : String(value)),
            renderItems: () => presentationController.renderItems(),
            removeItemById: (identifier: string): void => collection.removeItemById(identifier),
            streams: infrastructure.streaming.pageTracker
        },
        resolvePluginRecord: (plugin) => primaryRuntime.coreControllers.dataController.resolvePluginRecord(plugin),
        canExecutePluginAction: (plugin, options) => primaryRuntime.coreControllers.dataController.canExecutePluginAction(plugin, options),
        isPluginIncompatible: (plugin) => primaryRuntime.coreControllers.dataController.isPluginIncompatible(plugin),
        notifyPluginIncompatible: (plugin): void => primaryRuntime.coreControllers.compatibilityController.notifyPluginIncompatible(plugin),
        getPluginStatus: (plugin) => primaryRuntime.coreControllers.dataController.getPluginStatus(plugin),
        formatPluginName: (name: string): string => primaryRuntime.coreControllers.dataController.formatPluginName(name),
        navigateToModels: (action: string, plugin: PluginRecord | string | null | undefined) => presentationController.navigateToModels(action, plugin),
        startTaskAction: (endpoint, options, runtimeOptions) => infrastructure.streaming.taskAction(endpoint, options, runtimeOptions),
        isPluginStoppable: (plugin) => primaryRuntime.coreControllers.dataController.isPluginStoppable(plugin),
        updateStopAllButtonVisibility: (): void => primaryRuntime.coreControllers.statsController.updateStopAllButtonVisibility(),
        runPageTask: (taskKey, task, options) => infrastructure.streaming.runTask(taskKey, task, options),
        post: (path, body) => infrastructure.api.post(path, body)
    });

    const stateActionsController = new PluginsStateActionsController({
        activeToggles: session.activeToggles,
        pendingToggleTargets: session.pendingToggleTargets,
        api: infrastructure.api,
        catalogStore: session.catalogStore,
        runWithBoundary: <T>(scope: string, task: () => Promise<T>): Promise<T> => runBoundary(scope, task),
        runPageTask: (taskKey, task, options) => infrastructure.streaming.runTask(taskKey, task, options),
        runPluginTaskAction: (taskKey, endpoint, options) => primaryRuntime.coreControllers.taskActionController.runPluginTaskAction(taskKey, endpoint, options),
        commitCatalogPlugin: (plugin: ResourceIncomingValue) => primaryRuntime.coreControllers.collectionController.commitCatalogPlugin(plugin),
        rerenderPlugin: (pluginName: string): void => {
            if (!session.catalogStore.getPlugin(pluginName)) {
                return;
            }
            presentationController.renderItems();
        },
        feedback: infrastructure.feedback,
        isHardwareIncompatible: (plugin) => primaryRuntime.coreControllers.dataController.isHardwareIncompatible(plugin),
        canExecutePluginAction: (plugin, options) => primaryRuntime.coreControllers.dataController.canExecutePluginAction(plugin, options),
        getPluginStatus: (plugin) => primaryRuntime.coreControllers.dataController.getPluginStatus(plugin),
        isPluginPermanentlyDisabled: (plugin) => primaryRuntime.coreControllers.dataController.isPluginPermanentlyDisabled(plugin),
        notifyPluginIncompatible: (plugin): void => primaryRuntime.coreControllers.compatibilityController.notifyPluginIncompatible(plugin),
        isPluginStoppable: (plugin) => primaryRuntime.coreControllers.dataController.isPluginStoppable(plugin)
    });

    lifecycleController = new PluginsLifecycleController({
        pageDom: infrastructure.pageDom,
        configuration: {
            getApi: () => ({ configs: infrastructure.api.configs }),
            getCoreConfigCache: () => session.coreConfigCache,
            setCoreConfigCache: (value): void => {
                session.coreConfigCache = value;
            },
            getCoreConfigPromise: (): Promise<void> | null => session.coreConfigPromise,
            setCoreConfigPromise: (value: Promise<void> | null): void => {
                session.coreConfigPromise = value;
            },
            isDestroyed: () => collection.isDestroyed(),
            setMaxConcurrentPlugins: (value: number | null): void => {
                session.maxConcurrentPlugins = value;
            },
            resolveMaxConcurrentPlugins: (config) => primaryRuntime.coreControllers.dataController.resolveMaxConcurrentPlugins(config),
            runWithBoundary: <T>(scope: string, task: () => Promise<T>): Promise<T> => runBoundary(scope, task),
            updateStats: (): void => primaryRuntime.coreControllers.statsController.updateStats()
        },
        filters: {
            setFilterProvider: (value: string) => filters.setFilterProvider(value),
            setFilterStatus: (value: string) => filters.setFilterStatus(value),
            getFilterProvider: () => filters.getFilterProvider(),
            getFilterStatus: () => filters.getFilterStatus(),
            setSearchQuery: (value: string) => filters.setSearchQuery(value)
        },
        realtime: {
            ensureCollectionStream: async (options: { allowDiscovery: boolean; signal?: AbortSignal | undefined }): Promise<void> => {
                await collection.collections.ensureStream(options);
            },
            ensureDataSubscriptions: async (options: { signal?: AbortSignal } = {}): Promise<void> => {
                await infrastructure.streaming.ensureSubscriptions(options);
            },
            refreshCollectionStream: async (): Promise<void> => {
                await infrastructure.streaming.runtime().resources.refresh(PLUGINS, { allowDiscovery: true });
            },
            reapplyCollection: (options): void => collection.collections.reapply(options)
        },
        services: {
            getCatalogStore: () => ({
                ensureLoaded: (options: { force: boolean }): Promise<ReadonlyArray<PluginRecord>> => session.catalogStore.ensureLoaded(options)
            }),
            getCatalogSubscriptionManager: () => primaryRuntime.catalogSubscriptions,
            getFirstRunModals: () => pageDependencies.firstRunModals,
            openDownloadPluginModal: (): void => primaryRuntime.modalManagers.downloadModalManager.openDownloadPluginModal(),
            clearInitialQuery: (keys): void => {
                infrastructure.router.replaceCurrentRoute(buildRouteWithoutQueryParameters('plugins', infrastructure.router.getRouteParameters(), keys));
            }
        }
    });

    const pluginActionHost = createPluginsActionHost({
        callbacks: primaryRuntime.managerHostCallbacks,
        dataController: primaryRuntime.coreControllers.dataController,
        compatibilityController: primaryRuntime.coreControllers.compatibilityController,
        operationsController,
        stateActions: stateActionsController,
        prepareConfigModal: (plugin): void => primaryRuntime.modalManagers.configManager.prepareConfigModal(plugin),
        openInstallBackendModal: (plugin): void => primaryRuntime.modalManagers.manageBackendModalManager.openInstallBackendModal(plugin),
        openManageBackendModal: (plugin): void => primaryRuntime.modalManagers.manageBackendModalManager.openManageBackendModal(plugin),
        openCloneModal: (plugin): void => primaryRuntime.modalManagers.cloneManager.openCloneModal(plugin),
        openPluginInfoModal: (plugin): void => primaryRuntime.modalManagers.infoManager.openPluginInfoModal(plugin),
        navigateToModels: (action: string, plugin): boolean => presentationController.navigateToModels(action, plugin),
        dom: infrastructure.dom,
        showNotification
    });

    const interactionController = new PluginsInteractionController({
        pageDom: infrastructure.pageDom,
        feedback: infrastructure.feedback,
        getCardController: (): CardPageController | null => session.cardController,
        pluginActionHost,
        getRouter: () => infrastructure.router,
        getDownloadModalManager: () => primaryRuntime.modalManagers.downloadModalManager,
        getConcurrentManager: () => primaryRuntime.modalManagers.concurrentManager,
        getConfigManager: () => primaryRuntime.modalManagers.configManager,
        copyPluginInfo: (): Promise<void> => primaryRuntime.modalManagers.infoManager.copyPluginInfo(),
        getManageBackendModalManager: () => primaryRuntime.modalManagers.manageBackendModalManager,
        getCloneManager: () => primaryRuntime.modalManagers.cloneManager,
        handleStopAllPlugins: (): Promise<void> => operationsController.handleStopAllPlugins(),
        handleToggleViewMode: (): void => presentationController.toggleViewMode(),
        handleSortList: (actionElement: Element): void => {
            if (!(actionElement instanceof HTMLElement)) {
                throw new Error('Plugins list sort action requires an HTMLElement target');
            }
            sortPluginsListFromHeader(listSortHost, actionElement, (options) => collection.collections.reapply(options));
        }
    });

    const rootEventController = createPluginsRootEventController({
        host: {
            handleCardActionClick: (event: Event, actionElement: Element, action): void => interactionController.handleCardActionClick(event, actionElement, action),
            handlePageActionEvent: (event: Event, action: PluginsActionId, actionElement: Element): boolean => interactionController.handlePageActionEvent(event, action, actionElement),
            handleMetricBadgeClick: (event: Event, target: Element, badgeElement: Element): void => interactionController.handleMetricBadgeClick(event, target, badgeElement),
            handleActionError: (error: Error, message: string): void => infrastructure.feedback.handle(error, message, { notify: true })
        },
        shouldPreventDefaultForActionElement: shouldPreventDefaultExceptFileActionElement
    });

    return {
        coreControllers: primaryRuntime.coreControllers,
        modalManagers: primaryRuntime.modalManagers,
        progressController: primaryRuntime.progressController,
        operationsController,
        stateActionsController,
        lifecycleController,
        interactionController,
        rootEventController,
        pluginActionHost,
        catalogSubscriptions: primaryRuntime.catalogSubscriptions,
        cardRenderer: primaryRuntime.cardRenderer,
        cardController: primaryRuntime.cardController,
        presentationController
    };
};

export { createPluginsPageRuntime };
export type { PluginsPageRuntimeBundle };
