/* SoAI - Models page collection and controller aggregate [frontend/assets/ts/pages/models/controllers/page/ModelsPageDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionDataRuntime } from '@core/collectionpage/CollectionDataRuntime.ts';
import { CollectionPageState } from '@core/collectionpage/CollectionPageState.ts';
import { armCollectionCardRevealTargetsForCommit } from '@core/collectionpage/cardReveal.ts';
import { composeCollectionRuntime, type CollectionCompositionBehavior } from '@core/collectionpage/composeCollectionRuntime.ts';
import type { ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { modelActions } from '@core/modelactions/public.ts';
import { METRICS, MODELS_LAST_USED } from '@core/realtime/streammanager/resources/ids.ts';
import { requireLatestUsageResourceValue } from '@core/realtime/streammanager/resources/latestUsageResource.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';
import { speedTest } from '@core/speedTest.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { consumeRepeatableDropdownSelection } from '@core/ui/dropdown/selectControl.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { MODEL_SEARCH_FIELD_RESOLVERS, PAGE_ID, STR_ALL, STR_NONE } from '@pages/models/contracts/modelsPageConstants.ts';
import { getModelPlugin, resolveModelsItemCardId } from '@pages/models/controllers/modelsModelProperties.ts';
import { handleModelsInitialAction } from '@pages/models/controllers/modelsPageInitialActions.ts';
import { modelsLogger } from '@pages/models/controllers/ModelsPagePreClass.ts';
import type { ModelsInfrastructure, ModelsRuntimeDependencies } from '@pages/models/controllers/page/contracts.ts';
import { getModelsListSortValue, persistModelsProviderFilter } from '@pages/models/controllers/page/listSortingController.ts';
import { createModelsMetricsPatchScheduler, ModelsMetricsPatchController } from '@pages/models/controllers/page/metricsPatchController.ts';
import { ModelsPageLifecycleController } from '@pages/models/controllers/page/ModelsPageLifecycleController.ts';
import { ModelsPageSession } from '@pages/models/controllers/page/ModelsPageSession.ts';
import { ModelsPluginCatalogController } from '@pages/models/controllers/page/ModelsPluginCatalogController.ts';
import { createModelsPageCollectionConfig } from '@pages/models/controllers/page/pageConfig.ts';
import { handleModelsCollectionRefreshWithReveal } from '@pages/models/controllers/page/recentRevealController.ts';
import { createModelsPageRuntimeBindings } from '@pages/models/controllers/page/runtime.ts';
import { isValidModelItemForRuntime, renderModelsItemsForRuntime } from '@pages/models/controllers/page/runtimeMethods.ts';
import { destroyModelsPageFromRuntime, setupModelsMetricsSubscription, syncModelsMetricsSnapshot } from '@pages/models/controllers/page/service.ts';
import { getItemSearchFields, matchesProviderFilter, normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';
import { createModelsPageCollectionLayout } from '@pages/models/controllers/page/view.ts';
import { createModelsCollectionViewOverrides, renderModelsItemForViewMode } from '@pages/models/controllers/page/viewModeController.ts';
import type { ModelsPageDependencies } from '@pages/models/types.ts';
import { applySavedModelsFilters } from '@pages/models/widgets/modelsPageFilterControls.ts';

interface ModelsPageDomainOptions {
    pageDependencies: ModelsPageDependencies;
    infrastructure: ModelsInfrastructure;
    storage: StorageService;
    pageHost: PageHost;
    pageLifecycle: PageLifecycle;
    collectionOwners: { layout: PageLayout; streaming: PageStreaming };
}

class ModelsPageState extends CollectionPageState {
    override getSortBy(): string {
        return this.sortBy ?? STR_NONE;
    }
}

class ModelsPageDomain {
    readonly session: ModelsPageSession;
    readonly catalog: ModelsPluginCatalogController;
    readonly state: ModelsPageState;
    readonly collections: PageCollections;
    readonly data: CollectionDataRuntime;
    readonly layout: CollectionLayoutRuntime;
    readonly lifecycle: CollectionPageLifecycle;
    readonly dependencies: ModelsRuntimeDependencies;
    readonly bindings: ReturnType<typeof createModelsPageRuntimeBindings>;
    readonly pageLifecycleController: ModelsPageLifecycleController;
    readonly metricsPatchController: ModelsMetricsPatchController;
    readonly #infrastructure: ModelsInfrastructure;
    readonly #pageHost: PageHost;
    readonly #behavior: CollectionCompositionBehavior;
    #controlsHydrated = false;

    constructor({ pageDependencies, infrastructure, storage, pageHost, pageLifecycle, collectionOwners }: ModelsPageDomainOptions) {
        this.#infrastructure = infrastructure;
        this.#pageHost = pageHost;
        this.session = new ModelsPageSession(pageDependencies.catalogStore);
        const config = createModelsPageCollectionConfig();
        this.state = new ModelsPageState({ pageId: PAGE_ID, collectionKey: config.collectionKey, collectionOptions: config.collectionOptions, defaultSort: config.defaultSort });
        this.state.filterProvider = STR_ALL;
        this.state.filterStatus = STR_ALL;
        this.state.sortBy = STR_NONE;
        this.#behavior = this.#createBehavior();
        const collection = composeCollectionRuntime({
            pageId: PAGE_ID,
            config,
            state: this.state,
            owners: {
                pageDom: infrastructure.pageDom,
                pageResources: infrastructure.pageResources,
                streaming: collectionOwners.streaming,
                layout: collectionOwners.layout,
                services: infrastructure.services,
                pageElements: infrastructure.pageElements,
                feedback: infrastructure.feedback,
                storage,
                pageHost,
                pageLifecycle,
                createFragment: (markup) => infrastructure.dom.createFragment(markup)
            },
            behavior: this.#behavior
        });
        this.collections = collection.collections;
        this.data = collection.data;
        this.layout = collection.layout;
        this.lifecycle = collection.lifecycle;
        this.catalog = new ModelsPluginCatalogController(this.session, this.collections);
        this.dependencies = this.#createDependencies(pageLifecycle);
        this.bindings = createModelsPageRuntimeBindings(this.dependencies, {
            logInvalidActionModel: (action, model) => modelsLogger('error', 'Model action click missing model record', { action, model }),
            handleActionError: (error) => infrastructure.feedback.handle(error, 'Models click handler failed', { notify: true })
        });
        const managers = this.bindings.managerBundle;
        const controllers = this.bindings.controllerBundle;
        this.pageLifecycleController = new ModelsPageLifecycleController({
            runtime: this.dependencies,
            cardController: managers.cardController,
            initialActionHost: controllers.initialActionHost,
            viewModeHost: this.bindings.viewModeHost,
            populateProviderFilter: () => controllers.statsController.populateProviderFilter(),
            updateStats: () => controllers.statsController.updateStats()
        });
        this.metricsPatchController = new ModelsMetricsPatchController(
            {
                collections: this.collections,
                pageDom: infrastructure.pageDom,
                getContainer: () => pageHost.container,
                getCurrentMetrics: () => this.session.currentMetrics,
                cardRenderer: managers.cardRenderer,
                updateMetricsBackedStats: () => controllers.statsController.updateStats()
            },
            managers.modelCardHost,
            createModelsMetricsPatchScheduler(infrastructure.pageResources)
        );
    }

    #createDependencies(pageLifecycle: PageLifecycle): ModelsRuntimeDependencies {
        return {
            session: this.session,
            catalog: this.catalog,
            infrastructure: this.#infrastructure,
            collection: {
                collections: this.collections,
                collectionLifecycle: this.lifecycle,
                cancelDownload: (key) => this.data.cancelDownload(key),
                removeItemById: (identifier, options) => this.data.removeItemById(identifier, options),
                initializeCollectionView: () => this.initializeView(),
                setItemsFromList: (items) => this.data.setItemsFromList(items),
                setItemsWithoutEmit: (items) => this.data.setItemsFromList(items, { emit: false }),
                upsertItemWithoutEmit: (item) => this.data.upsertItem(item, { emit: false }),
                getContainer: () => this.#pageHost.container,
                isDestroyed: () => pageLifecycle.isDestroyed,
                renderItems: () => this.#renderItems(),
                getMetricBadgeType: (element) => this.layout.getMetricBadgeType(element),
                handleMetricBadgeNavigation: (element, item, options) => this.layout.handleMetricBadgeNavigation(element, item, options)
            },
            filters: this.state,
            modelActions,
            speedTest,
            log: (level, message, error) => modelsLogger(level, message, error)
        };
    }

    #createBehavior(): CollectionCompositionBehavior {
        return {
            defineLayout: () => {
                this.#hydrateControls();
                return createModelsPageCollectionLayout({
                    sortBy: this.state.sortBy ?? STR_NONE,
                    sortOrder: this.state.sortOrder ?? 'asc',
                    onSortChange: (event) => this.#handleSortChange(event),
                    createLayoutBuilder: () => this.layout.getLayoutBuilder(),
                    getIconSync: (iconName, options) => this.#infrastructure.services.getIconSync(iconName, options)
                });
            },
            onSnapshot: (snapshot: ResourceSnapshot) => {
                this.session.consumeModelsSnapshot(snapshot);
                return null;
            },
            preparePresentation: (context) => this.bindings.controllerBundle.groupingController.preparePresentation(context.filtered.map((model) => normalizeModelRecordStrict(model, 'ModelsPage.preparePresentation'))),
            onRefresh: (summary) => {
                this.bindings.controllerBundle.statsController.updateStats();
                handleModelsCollectionRefreshWithReveal({ collections: this.collections, getItemCardId: resolveModelsItemCardId }, this.session.recentItems, summary);
            },
            onCommit: (context) => {
                armCollectionCardRevealTargetsForCommit(context.enteringElements);
                this.#infrastructure.pageElements.enableCheckerboard(context.container, '.model-card, .models-list-row', context.rangeStart);
                this.#infrastructure.layout.queueResponsive();
                this.metricsPatchController.queue();
            },
            renderItemCard: (model) => renderModelsItemForViewMode(this.bindings.viewModeHost, model),
            getItemSearchFields: (model) => getItemSearchFields(model, MODEL_SEARCH_FIELD_RESOLVERS),
            applyCustomFilters: (model, { filterProvider }) => matchesProviderFilter(model, filterProvider, getModelPlugin),
            getSortValue: (model, field) => getModelsListSortValue({ stateManager: this.#infrastructure.stateManager }, model, field),
            isValidItem: (candidate): candidate is ResourceItem => isValidModelItemForRuntime(candidate),
            normalizeItem: (item) => item,
            getItemCardId: resolveModelsItemCardId,
            renderItems: () => this.#renderItems(),
            updateStats: () => this.bindings.controllerBundle.statsController.updateStats(),
            updateFilters: () => {},
            onFilterChange: (property, value) => {
                if (property !== 'filterProvider') throw new Error(`Models collection filter property is unsupported: ${property}`);
                persistModelsProviderFilter(this.#infrastructure.storage, value);
            }
        };
    }

    #renderItems(): void {
        const collection = this.collections.runtime;
        if (!collection) throw new Error('ModelsPage requires collection to be initialized');
        renderModelsItemsForRuntime({ getFilteredItems: () => collection.getFiltered(), getAllItems: () => collection.getAll(), renderCollection: (payload) => this.bindings.managerBundle.cardController.renderCollection(payload) });
    }

    initializeView(): void {
        this.state.initializeView(this.collections, createModelsCollectionViewOverrides(this.bindings.viewModeHost));
    }

    renderItems(): void {
        this.#renderItems();
    }

    async setupMetrics(): Promise<void> {
        await this.#infrastructure.streaming.runtime().resources.ensureResourceStarted(METRICS);
        const thisSession = this.session;
        const host = {
            collections: this.collections,
            streaming: this.#infrastructure.streaming,
            pageResources: this.#infrastructure.pageResources,
            get currentMetrics() {
                return thisSession.currentMetrics;
            },
            set currentMetrics(value: JsonObject | null) {
                thisSession.currentMetrics = value;
            },
            get metricsPresentationSignature() {
                return thisSession.metricsPresentationSignature;
            },
            set metricsPresentationSignature(value: string | null) {
                thisSession.metricsPresentationSignature = value;
            },
            metricsPatchController: this.metricsPatchController
        };
        setupModelsMetricsSubscription(host);
        syncModelsMetricsSnapshot(host);
    }

    setupLastUsed(): void {
        this.#infrastructure.pageResources.track(
            this.#infrastructure.streaming.subscribeResourceValue(MODELS_LAST_USED, (value) => {
                this.bindings.controllerBundle.statsController.updateLastUsedStat(requireLatestUsageResourceValue(value));
            })
        );
    }

    #hydrateControls(): void {
        if (this.#controlsHydrated) return;
        applySavedModelsFilters(this.bindings.filterStateHost);
        this.#controlsHydrated = true;
    }

    #handleSortChange(event: Event): void {
        const target = event.target;
        if (!(target instanceof HTMLSelectElement)) throw new TypeError('Models sort change requires an HTMLSelectElement');
        this.bindings.applySortSelection(consumeRepeatableDropdownSelection(target));
    }

    async handleInitialAction(parameters: JsonObject | null): Promise<void> {
        await handleModelsInitialAction(this.bindings.controllerBundle.initialActionHost, parameters);
    }

    async destroy(): Promise<void> {
        this.metricsPatchController.dispose();
        const managers = this.bindings.managerBundle;
        await destroyModelsPageFromRuntime({ downloadModalManager: managers.downloadModalManager, editModelModalManager: managers.editModelModalManager, renameModelModalManager: managers.renameModelModalManager, providersManager: managers.providersManager, virtualModelsManager: managers.virtualModelsManager, catalogSubscriptions: { cleanup: () => this.catalog.cleanup() }, pluginLookup: this.session.pluginLookup, grouping: this.session.grouping, deletingItems: this.session.deletingItems, cardController: managers.cardController });
        this.session.clear();
        this.lifecycle.dispose();
        this.data.destroy();
    }
}

export { ModelsPageDomain };
