/* SoAI - Plugins page collection and controller aggregate [frontend/assets/ts/pages/plugins/controllers/page/PluginsPageDomain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionDataRuntime } from '@core/collectionpage/CollectionDataRuntime.ts';
import { CollectionPageState } from '@core/collectionpage/CollectionPageState.ts';
import { consumeRepeatableDropdownSelection } from '@core/ui/dropdown/selectControl.ts';
import { armCollectionCardRevealTargetsForCommit } from '@core/collectionpage/cardReveal.ts';
import { composeCollectionRuntime, type CollectionCompositionBehavior } from '@core/collectionpage/composeCollectionRuntime.ts';
import type { ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import type { RefreshContext } from '@core/data/collectionview/service.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import { applyPluginsSortSelection, getPluginsListSortValue, hydratePluginsPageControls, persistPluginsFilter, type PluginsListSortHost } from '@pages/plugins/controllers/page/listSortingController.ts';
import { createPluginsGroupingController } from '@pages/plugins/controllers/page/pluginsGroupingController.ts';
import { createPluginsCollectionPageConfig } from '@pages/plugins/controllers/page/pageConfig.ts';
import { createPluginsPageRuntime, type PluginsPageRuntimeBundle } from '@pages/plugins/controllers/page/service.ts';
import { PluginsPageSession } from '@pages/plugins/controllers/page/PluginsPageSession.ts';
import type { PluginsInfrastructure } from '@pages/plugins/controllers/page/contracts.ts';
import type { PluginsPageDependencies } from '@pages/plugins/types.ts';
import { buildPluginsLayout } from '@pages/plugins/view.ts';
import { PLUGINS_LAST_USED } from '@core/realtime/streammanager/resources/ids.ts';
import { requireLatestUsageResourceValue } from '@core/realtime/streammanager/resources/latestUsageResource.ts';

interface PluginsPageDomainOptions {
    pageDependencies: PluginsPageDependencies;
    infrastructure: PluginsInfrastructure;
    storage: StorageService;
    pageHost: PageHost;
    pageLifecycle: PageLifecycle;
    collectionOwners: { layout: PageLayout; streaming: PageStreaming };
}

class PluginsPageDomain {
    readonly session: PluginsPageSession;
    readonly state: CollectionPageState;
    readonly collections: PageCollections;
    readonly data: CollectionDataRuntime;
    readonly layout: CollectionLayoutRuntime;
    readonly lifecycle: CollectionPageLifecycle;
    readonly runtime: PluginsPageRuntimeBundle;
    readonly #infrastructure: PluginsInfrastructure;
    readonly #storage: StorageService;
    readonly #behavior: CollectionCompositionBehavior;
    readonly #groupingController: ReturnType<typeof createPluginsGroupingController>;
    #controlsHydrated = false;

    constructor({ pageDependencies, infrastructure, storage, pageHost, pageLifecycle, collectionOwners }: PluginsPageDomainOptions) {
        this.#infrastructure = infrastructure;
        this.#storage = storage;
        this.session = new PluginsPageSession(pageDependencies.catalogStore);
        const config = createPluginsCollectionPageConfig();
        this.state = new CollectionPageState({ pageId: 'plugins', collectionKey: config.collectionKey, collectionOptions: config.collectionOptions, defaultSort: config.defaultSort });
        this.#groupingController = createPluginsGroupingController({
            grouping: this.session.grouping,
            getSortBy: () => this.state.getSortBy() ?? 'none',
            getItemCardId: (plugin) => this.runtime.coreControllers.dataController.getItemCardId(plugin),
            getPluginStatus: (plugin) => this.runtime.coreControllers.dataController.getPluginStatus(plugin),
            getStatusDescription: (status) => this.#infrastructure.stateManager.status.getDescription(status)
        });
        this.#behavior = this.#createBehavior();
        const collection = composeCollectionRuntime({
            pageId: 'plugins',
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
        this.runtime = createPluginsPageRuntime({
            session: this.session,
            pageDependencies,
            infrastructure,
            collection: {
                collections: this.collections,
                collectionLifecycle: this.lifecycle,
                cancelDownload: (key) => this.data.cancelDownload(key),
                removeItemById: (identifier) => {
                    this.data.removeItemById(identifier);
                },
                setItemsFromList: (items) => this.data.setItemsFromList(items),
                setItemsWithoutEmit: (items) => this.data.setItemsFromList(items, { emit: false }),
                upsertItemWithoutEmit: (item) => this.data.upsertItem(item, { emit: false }),
                isDestroyed: () => pageLifecycle.isDestroyed
            },
            filters: this.state,
            runBoundary: (scope, task) => pageLifecycle.run(scope, task)
        });
    }

    #createBehavior(): CollectionCompositionBehavior {
        return {
            defineLayout: () => {
                this.#hydrateControls();
                const builder = this.layout.getLayoutBuilder();
                return buildPluginsLayout({
                    getIconSync: (iconName, options) => this.#infrastructure.services.getIconSync(iconName, options),
                    buildLayout: (config) => builder.build(config),
                    sortBy: this.state.getSortBy() ?? 'none',
                    sortOrder: this.state.getSortOrder() ?? 'asc',
                    onSortChange: (event) => this.#handleSortChange(event)
                });
            },
            onSnapshot: (snapshot: ResourceSnapshot) => {
                this.runtime.presentationController.consumeSnapshot(snapshot);
                return null;
            },
            preparePresentation: (context) => {
                const plugins = context.filtered.map((item) => {
                    const record = this.runtime.coreControllers.dataController.resolvePluginRecord(item);
                    if (!record) throw new Error('Plugins collection contains an invalid normalized item');
                    return record;
                });
                return this.#groupingController.preparePresentation(plugins);
            },
            onRefresh: (_summary: RefreshContext) => {
                this.runtime.presentationController.renderItems();
                this.runtime.presentationController.revealRecentItem();
            },
            onCommit: (context) => {
                armCollectionCardRevealTargetsForCommit(context.enteringElements);
                this.#infrastructure.pageElements.enableCheckerboard(context.container, '.plugin-card, .plugins-list-row', context.rangeStart);
                this.#infrastructure.layout.queueResponsive();
            },
            renderItemCard: (plugin: ResourceItem) => this.runtime.presentationController.renderItem(plugin),
            getItemSearchFields: (plugin: ResourceItem) => this.runtime.coreControllers.dataController.getItemSearchFields(plugin),
            applyCustomFilters: (plugin, filters) => this.runtime.coreControllers.dataController.applyCustomFilters(plugin, filters),
            getSortValue: (plugin, field) => {
                const record = this.runtime.coreControllers.dataController.resolvePluginRecord(plugin);
                return record ? getPluginsListSortValue(record, field, (item) => this.runtime.coreControllers.dataController.getPluginStatus(item)) : '';
            },
            isValidItem: (candidate): candidate is ResourceItem => this.runtime.coreControllers.dataController.isValidItem(candidate),
            normalizeItem: (plugin) => this.runtime.coreControllers.collectionController.normalizeItem(plugin),
            getItemCardId: (item) => this.runtime.coreControllers.dataController.getItemCardId(item),
            renderItems: () => this.runtime.presentationController.renderItems(),
            updateStats: () => this.runtime.coreControllers.statsController.updateStats(),
            updateFilters: () => {},
            onFilterChange: (property, value) => {
                if (property !== 'filterProvider' && property !== 'filterStatus') throw new Error(`Plugins collection filter property is unsupported: ${property}`);
                persistPluginsFilter(this.#storage, property, value);
            }
        };
    }

    #hydrateControls(): void {
        if (this.#controlsHydrated) return;
        const state = this.state;
        hydratePluginsPageControls({
            storage: this.#storage,
            get filterProvider() {
                return state.filterProvider;
            },
            set filterProvider(value) {
                state.filterProvider = value;
            },
            get filterStatus() {
                return state.filterStatus;
            },
            set filterStatus(value) {
                state.filterStatus = value;
            },
            get sortBy() {
                return state.sortBy;
            },
            set sortBy(value) {
                state.sortBy = value;
            },
            get sortOrder() {
                return state.sortOrder;
            },
            set sortOrder(value) {
                state.sortOrder = value;
            },
            get searchQuery() {
                return state.searchQuery;
            },
            set searchQuery(value) {
                state.searchQuery = value;
            }
        });
        this.#controlsHydrated = true;
    }

    #sortHost(): PluginsListSortHost {
        const state = this.state;
        return {
            services: this.#infrastructure.services,
            pageElements: this.#infrastructure.pageElements,
            pageDom: this.#infrastructure.pageDom,
            storage: this.#storage,
            get sortBy() {
                return state.getSortBy();
            },
            set sortBy(value) {
                state.setSortBy(value);
            },
            get sortOrder() {
                return state.getSortOrder();
            },
            set sortOrder(value) {
                state.setSortOrder(value);
            }
        };
    }

    #handleSortChange(event: Event): void {
        const target = event.target;
        if (!(target instanceof HTMLSelectElement)) throw new TypeError('Plugins sort change requires an HTMLSelectElement');
        applyPluginsSortSelection(this.#sortHost(), consumeRepeatableDropdownSelection(target), (options) => this.collections.reapply(options));
    }

    initializeView(): void {
        this.state.initializeView(this.collections, this.runtime.presentationController.collectionViewOverrides());
    }

    setupLastUsed(): void {
        this.#infrastructure.pageResources.track(
            this.#infrastructure.streaming.subscribeResourceValue(PLUGINS_LAST_USED, (value) => {
                this.runtime.coreControllers.statsController.updateLastUsedStat(requireLatestUsageResourceValue(value));
            })
        );
    }

    dispose(): void {
        this.lifecycle.dispose();
        this.data.destroy();
    }
}

export { PluginsPageDomain };
export type { PluginsPageDomainOptions };
