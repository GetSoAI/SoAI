/* SoAI - Models page runtime [frontend/assets/ts/pages/models/controllers/page/runtime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import { modelsPageConfig } from '@core/routing/pages/collections/collectionPageConfig.ts';
import { MODELS_ACTION_ADD_PROVIDER } from '@core/models/pageActions.ts';
import { setModelsInitialActionContext } from '@pages/models/controllers/modelsPageInitialActions.ts';
import { createModelsManagerBundle } from '@pages/models/controllers/page/adapters.ts';
import { createRootClickHandler, type ModelsActionClickDependencies } from '@pages/models/controllers/page/clickDispatch.ts';
import type { ModelsRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import type { ModelsPageSession } from '@pages/models/controllers/page/ModelsPageSession.ts';
import { createModelEnabledToggleState } from '@pages/models/controllers/page/modelEnabledToggleController.ts';
import { createModelsControllerBundle } from '@pages/models/controllers/page/events.ts';
import { applyModelsSortSelection, sortModelsListFromHeader, type ModelsListSortHost } from '@pages/models/controllers/page/listSortingController.ts';
import type { ModelsViewModeHost } from '@pages/models/controllers/page/viewModeController.ts';
import type { ModelsDataActionId } from '@pages/models/actions.ts';
import { resolveModelsItemCardId } from '@pages/models/controllers/modelsModelProperties.ts';
import type { ModelsFilterStateHost } from '@pages/models/widgets/modelsPageFilterControls.ts';

interface ModelsPageRuntimeBindings {
    managerBundle: ReturnType<typeof createModelsManagerBundle>;
    controllerBundle: ReturnType<typeof createModelsControllerBundle>;
    rootClickHandler: (event: Event, action: ModelsDataActionId, actionElement?: HTMLElement | null) => void;
    viewModeHost: ModelsViewModeHost;
    filterStateHost: ModelsFilterStateHost;
    applySortSelection: (column: string) => void;
}

const createModelsFilterStateHost = (runtime: ModelsRuntimeDependencies): ModelsFilterStateHost => {
    const { filters, infrastructure } = runtime;
    return {
        storage: infrastructure.storage,
        get filterProvider() {
            return filters.getFilterProvider();
        },
        set filterProvider(value) {
            filters.setFilterProvider(value);
        },
        get filterStatus() {
            return filters.getFilterStatus();
        },
        set filterStatus(value) {
            filters.setFilterStatus(value);
        },
        get sortBy() {
            return filters.getSortBy();
        },
        set sortBy(value) {
            filters.setSortBy(value);
        },
        get sortOrder() {
            return filters.getSortOrder();
        },
        set sortOrder(value) {
            filters.setSortOrder(value);
        },
        get searchQuery() {
            return filters.getSearchQuery();
        },
        set searchQuery(value) {
            filters.setSearchQuery(value);
        }
    };
};

const createModelsListSortHost = (runtime: ModelsRuntimeDependencies): ModelsListSortHost => {
    const { infrastructure } = runtime;
    return Object.assign(createModelsFilterStateHost(runtime), {
        services: infrastructure.services,
        pageElements: infrastructure.pageElements,
        pageDom: infrastructure.pageDom
    });
};

const toggleCurrentModelsViewMode = (session: Pick<ModelsPageSession, 'viewModeController'>): void => {
    const controller = session.viewModeController;
    if (!controller) throw new Error('Models view mode controller is unavailable');
    controller.toggle();
};

const createModelsViewModeHost = (runtime: ModelsRuntimeDependencies): ModelsViewModeHost => {
    const { session, infrastructure, collection } = runtime;
    if (!session.cardRenderer || !session.cardController) throw new Error('Models view mode requires initialized card owners');
    return {
        storage: infrastructure.storage,
        services: infrastructure.services,
        pageElements: infrastructure.pageElements,
        pageDom: infrastructure.pageDom,
        layout: infrastructure.layout,
        collections: collection.collections,
        cardRenderer: session.cardRenderer,
        grouping: session.grouping,
        getItemCardId: resolveModelsItemCardId,
        get viewMode() {
            return session.viewMode;
        },
        set viewMode(value) {
            session.viewMode = value;
        },
        get viewModeController() {
            return session.viewModeController;
        },
        set viewModeController(value) {
            session.viewModeController = value;
        },
        get filterProvider() {
            return runtime.filters.getFilterProvider();
        },
        set filterProvider(value) {
            runtime.filters.setFilterProvider(value);
        },
        get sortBy() {
            return runtime.filters.getSortBy();
        },
        set sortBy(value) {
            runtime.filters.setSortBy(value);
        },
        get sortOrder() {
            return runtime.filters.getSortOrder();
        },
        set sortOrder(value) {
            runtime.filters.setSortOrder(value);
        }
    };
};

const handleModelsMetricBadgeNavigation = (runtime: ModelsRuntimeDependencies, providersManager: { openProvidersModal(): Promise<void> }, element: Element, model: Parameters<ModelsRuntimeDependencies['collection']['handleMetricBadgeNavigation']>[1]): boolean => {
    if (runtime.collection.getMetricBadgeType(element) === 'PROVIDER') {
        terminateHandledPromise(providersManager.openProvidersModal());
        return true;
    }
    return runtime.collection.handleMetricBadgeNavigation(element, model, {
        navigate: (route, options) => {
            terminateHandledPromise(runtime.infrastructure.router.navigate(route, options ?? undefined));
            return null;
        }
    });
};

const createModelsPageRuntimeBindings = (
    runtime: ModelsRuntimeDependencies,
    dependencies: {
        logInvalidActionModel: (action: string, model: ResourceIncomingValue | null | undefined) => void;
        handleActionError: (error: Error) => void;
        shouldShowNormalEmptyState: (modelCount: number) => boolean;
    }
): ModelsPageRuntimeBindings => {
    const enabledToggleState = createModelEnabledToggleState();
    const managerBundle = createModelsManagerBundle(runtime, {
        getPendingToggleTarget: enabledToggleState.getPendingToggleTarget,
        shouldShowNormalEmptyState: dependencies.shouldShowNormalEmptyState
    });
    const controllerBundle = createModelsControllerBundle(runtime, {
        modelProperties: managerBundle.modelProperties,
        downloadModalManager: managerBundle.downloadModalManager,
        editModelModalManager: managerBundle.editModelModalManager,
        providersManager: managerBundle.providersManager,
        virtualModelsManager: managerBundle.virtualModelsManager,
        enabledToggleState
    });
    runtime.catalog.attachUi({
        updateProviderButtonVisibility: () => managerBundle.providersManager.updateProviderButtonVisibility(),
        updateVirtualModelsButtonVisibility: () => controllerBundle.statsController.updateVirtualModelsButtonVisibility()
    });
    const actionDependencies: ModelsActionClickDependencies = {
        cardSelector: `${modelsPageConfig.grid.cardSelector}, .models-list-row`,
        getModelsActionHost: () => controllerBundle.modelsActionHost,
        getItemFromCard: (card) => managerBundle.cardController.getItemFromCard(card),
        openDownloadModelModal: () => managerBundle.downloadModalManager.open(),
        openAddProviderTab: () => {
            setModelsInitialActionContext(controllerBundle.initialActionHost, { action: MODELS_ACTION_ADD_PROVIDER });
            managerBundle.providersManager.closeProvidersModal();
            managerBundle.downloadModalManager.open();
        },
        openProviderTab: (event) => {
            setModelsInitialActionContext(controllerBundle.initialActionHost, { action: MODELS_ACTION_ADD_PROVIDER });
            managerBundle.downloadModalManager.openProviderTab(event);
        },
        navigateToMetrics: () => {
            terminateHandledPromise(runtime.infrastructure.router.navigate('metrics', { force: true }));
        },
        openVirtualModelsModal: () => managerBundle.virtualModelsManager.openVirtualModelsModal(),
        openProvidersModal: () => managerBundle.providersManager.openProvidersModal(),
        toggleViewMode: () => toggleCurrentModelsViewMode(runtime.session),
        sortList: (actionElement) => sortModelsListFromHeader(createModelsListSortHost(runtime), actionElement, (options) => runtime.collection.collections.reapply(options)),
        handleMetricBadgeNavigation: (badge, model) => handleModelsMetricBadgeNavigation(runtime, managerBundle.providersManager, badge, model),
        logInvalidActionModel: dependencies.logInvalidActionModel,
        handleActionError: dependencies.handleActionError
    };
    return {
        managerBundle,
        controllerBundle,
        rootClickHandler: createRootClickHandler(actionDependencies),
        viewModeHost: createModelsViewModeHost(runtime),
        filterStateHost: createModelsFilterStateHost(runtime),
        applySortSelection: (column) => applyModelsSortSelection(createModelsListSortHost(runtime), column, (options) => runtime.collection.collections.reapply(options))
    };
};

export { createModelsPageRuntimeBindings, createModelsViewModeHost, toggleCurrentModelsViewMode };
