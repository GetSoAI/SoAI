/* SoAI - Models page events [frontend/assets/ts/pages/models/controllers/page/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getHistory } from '@core/environment/public.ts';
import { resolveModelRequestCount } from '@core/models/usageMetrics.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { ModelsActionHost } from '@pages/models/contracts/ModelPageSupport.ts';
import { createModelsGroupingController } from '@pages/models/controllers/modelsGroupingController.ts';
import { isModelRecord, resolveModelsItemCardId, type ModelPropertyInput } from '@pages/models/controllers/modelsModelProperties.ts';
import { createModelsOperationsController } from '@pages/models/controllers/modelsOperationsController.ts';
import type { ModelsInitialActionHost } from '@pages/models/controllers/modelsPageInitialActions.ts';
import { createModelsStatsController } from '@pages/models/controllers/modelsStatsController.ts';
import type { ModelsControllerRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import { getPluginByName } from '@pages/models/controllers/page/effects.ts';
import { createModelsDeleteDependencies } from '@pages/models/controllers/page/modelsDeletionController.ts';
import { getAllModels } from '@pages/models/controllers/page/state.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import { navigateToModelDetail } from '@pages/models/controllers/page/clickDispatch.ts';
import { createModelsItemDeletionHost, executeModelsItemDeletion } from '@pages/models/controllers/page/service.ts';
import { persistModelsProviderFilter } from '@pages/models/controllers/page/listSortingController.ts';

interface ModelsControllerInitializationDependencies {
    modelProperties: {
        getModelPlugin(model: ModelPropertyInput): string;
        getModelProvider(model: ModelPropertyInput): string;
        getModelOriginId(model: ModelPropertyInput): string;
        getModelDisplayName(model: ModelPropertyInput): string;
        getModelStatus(statusManager: { normalizeStatus(status: JsonValue | null | undefined): string }, model: ModelPropertyInput): string;
        isExternalProviderModel(model: ModelPropertyInput): boolean;
    };
    downloadModalManager: {
        open(event?: Event): void;
    };
    providersManager: {
        openProvidersModal(event?: Event): Promise<void>;
        updateProviderButtonVisibility(): void;
    };
    editModelModalManager: {
        showEditModelModal(model: ModelRecord): Promise<void>;
    };
    virtualModelsManager: {
        openVirtualModelsModal(event?: Event): void;
        openVirtualModelEditForm(vmName: string): Promise<void>;
        showEditVirtualModelForm(vmName?: string | null): void;
        deleteVirtualModel(vmName: string): Promise<void>;
    };
    enabledToggleState: {
        setPendingToggleTarget(targetKey: string, enabled: boolean): void;
        clearPendingToggleTarget(targetKey: string): void;
    };
}

interface ModelsControllerInitializationResult {
    modelProperties: ModelsControllerInitializationDependencies['modelProperties'];
    groupingController: ReturnType<typeof createModelsGroupingController>;
    statsController: ReturnType<typeof createModelsStatsController>;
    initialActionHost: ModelsInitialActionHost;
    modelsActionHost: ModelsActionHost;
}

const createModelsControllerBundle = (runtime: ModelsControllerRuntimeDependencies, dependencies: ModelsControllerInitializationDependencies): ModelsControllerInitializationResult => {
    const { infrastructure, collection, filters, session } = runtime;
    const modelProperties = dependencies.modelProperties;
    const requireCollection = (): CollectionRuntime => {
        const current = collection.collections.runtime;
        if (!current) throw new Error('ModelsPage requires collection to be initialized');
        return current;
    };
    const statsController = createModelsStatsController({
        optionalUI: (selector) => infrastructure.pageDom.optional(selector),
        updateText: (target, text) => infrastructure.pageDom.updateText(target, text),
        toggleClassName: (target, className, enabled) => infrastructure.pageDom.toggleClass(target, className, enabled),
        updateHeaderStat: (id, key, count) => infrastructure.layout.updateHeaderStat(id, key, count),
        queueResponsiveLayoutUpdate: () => infrastructure.layout.queueResponsive(),
        getCatalogPlugins: () => session.allPlugins,
        getModelStatus: (model) => dependencies.modelProperties.getModelStatus(infrastructure.stateManager.status, model),
        isExternalProviderModel: (model) => dependencies.modelProperties.isExternalProviderModel(model),
        getModelPlugin: (model) => dependencies.modelProperties.getModelPlugin(model),
        models: {
            getAll: () => getAllModels(requireCollection()),
            find: (universalId) => {
                const model = collection.collections.runtime?.find(universalId) ?? null;
                return isModelRecord(model) ? model : null;
            }
        },
        getModelDisplayName: (model) => dependencies.modelProperties.getModelDisplayName(model),
        getCollectionAllRaw: () => (collection.collections.runtime ? collection.collections.runtime.getAll() : []),
        resolveModelRequestCount: (model) => resolveModelRequestCount(session.currentMetrics, model),
        getAvailablePluginsCount: () => session.availablePlugins.length,
        getFilterProvider: () => filters.getFilterProvider(),
        setFilterProvider: (value: string) => filters.setFilterProvider(value),
        persistFilterProvider: (value: string) => persistModelsProviderFilter(infrastructure.storage, value),
        reapplyCollection: () => collection.collections.reapply({ shouldRender: true, updateStats: false, updateFilters: false }),
        updateProviderButtonVisibility: () => dependencies.providersManager.updateProviderButtonVisibility()
    });

    const groupingController = createModelsGroupingController({
        grouping: session.grouping,
        getSortBy: () => filters.getSortBy(),
        getItemCardId: (item) => resolveModelsItemCardId(item),
        getPluginByName: (name) => getPluginByName(session, name),
        statusManager: infrastructure.stateManager.status,
        getModelPlugin: (model) => dependencies.modelProperties.getModelPlugin(model),
        getModelProvider: (model) => dependencies.modelProperties.getModelProvider(model),
        getModelStatus: (model) => dependencies.modelProperties.getModelStatus(infrastructure.stateManager.status, model),
        getModelDisplayName: (model) => dependencies.modelProperties.getModelDisplayName(model)
    });

    const getCurrentModel = (cardId: string): ModelRecord | null => {
        const current = collection.collections.runtime?.find(cardId) ?? null;
        return isModelRecord(current) ? current : null;
    };

    const commitEnabledState = (cardId: string, enabled: boolean): ModelRecord | null => {
        const currentCollection = collection.collections.runtime;
        if (!currentCollection) {
            return null;
        }
        const updated = currentCollection.update(cardId, (item) => {
            if (!isModelRecord(item)) {
                return null;
            }
            const next: ModelRecord = {
                ...item,
                isEnabled: enabled
            };
            if (!enabled) {
                next.isAvailable = false;
            }
            return next;
        });
        return isModelRecord(updated) ? updated : null;
    };

    const rerenderModel = (cardId: string): void => {
        if (!cardId) {
            return;
        }
        collection.collections.view?.markDirty?.([cardId]);
    };

    const operationsController = createModelsOperationsController({
        stop: {
            runWithBoundary: (name, task) => infrastructure.pageLifecycle.run(name, task),
            showNotification: (message, type) => infrastructure.feedback.show(message, type),
            getModelPlugin: (model) => dependencies.modelProperties.getModelPlugin(model),
            getModelStatus: (model) => dependencies.modelProperties.getModelStatus(infrastructure.stateManager.status, model),
            getStreamTracker: (scope) => infrastructure.streaming.tracker(scope),
            runPageTask: (taskName, task, options) => infrastructure.streaming.runTask(taskName, task, options),
            startTaskAction: (path, initialize) => infrastructure.streaming.taskAction(path, initialize)
        },
        del: createModelsDeleteDependencies(
            {
                collections: collection.collections,
                pageDom: infrastructure.pageDom,
                modelActions: runtime.modelActions,
                getCardModelId: (element) => infrastructure.dom.getData(element, 'model'),
                executeItemDeletion: (config) =>
                    executeModelsItemDeletion(
                        createModelsItemDeletionHost({
                            deletingItems: session.deletingItems,
                            streams: infrastructure.streaming.pageTracker,
                            pageDom: infrastructure.pageDom,
                            feedback: infrastructure.feedback,
                            renderItems: collection.renderItems,
                            removeItemById: (id) => collection.removeItemById(id)
                        }),
                        config
                    )
            },
            dependencies.modelProperties,
            dependencies.virtualModelsManager
        ),
        enabled: {
            runWithBoundary: (name, task) => infrastructure.pageLifecycle.run(name, task),
            updateEnabled: (modelId, payload) => infrastructure.api.models.updateEnabled(modelId, payload),
            updateVirtualEnabled: (vmName, payload) => infrastructure.api.routing.virtualModels.setEnabled(vmName, payload),
            getCurrentModel,
            commitEnabledState,
            setPendingToggleTarget: (targetKey, enabled) => dependencies.enabledToggleState.setPendingToggleTarget(targetKey, enabled),
            clearPendingToggleTarget: (targetKey) => dependencies.enabledToggleState.clearPendingToggleTarget(targetKey),
            rerenderModel,
            showNotification: (message, type) => infrastructure.feedback.show(message, type),
            updateStats: () => statsController.updateStats()
        }
    });

    const initialActionHost: ModelsInitialActionHost = {
        getInitialActionContext: () => session.initialActionContext,
        setInitialActionContext: (context) => {
            session.initialActionContext = context;
        },
        router: infrastructure.router,
        replaceHashRoute: (route) => getHistory().replaceState({ route }, infrastructure.dom.getDocument().title, `#${route}`),
        log: runtime.log,
        openDownloadModelModal: () => dependencies.downloadModalManager.open(),
        openProvidersModal: () => dependencies.providersManager.openProvidersModal(),
        openVirtualModelsModal: () => dependencies.virtualModelsManager.openVirtualModelsModal(),
        showEditVirtualModelForm: (vmName) => dependencies.virtualModelsManager.showEditVirtualModelForm(vmName)
    };

    const modelsActionHost: ModelsActionHost = {
        getItemCardId: (model) => resolveModelsItemCardId(model),
        showEditVirtualModelForm: (vmName) => dependencies.virtualModelsManager.openVirtualModelEditForm(vmName),
        showEditModelModal: (model) => dependencies.editModelModalManager.showEditModelModal(model),
        deleteModel: (identifier) => operationsController.deleteModel(identifier),
        stopModel: (model) => operationsController.stopModel(model),
        toggleModelEnabled: (model, event) => operationsController.toggleModelEnabled(model, event),
        navigateToModelDetail: (model, options) => navigateToModelDetail(model, options, { router: infrastructure.router, onInvalidModel: (invalidModel) => runtime.log('error', `Invalid model or router unavailable: ${String(invalidModel.id ?? '')}`) })
    };

    return {
        modelProperties,
        groupingController,
        statsController,
        initialActionHost,
        modelsActionHost
    };
};

export { createModelsControllerBundle };
export type { ModelsControllerInitializationDependencies, ModelsControllerInitializationResult };
