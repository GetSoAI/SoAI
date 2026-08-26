/* SoAI - Plugins collection rendering, display mode, navigation, and recent-item ownership [frontend/assets/ts/pages/plugins/controllers/page/PluginsCollectionPresentationController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { renderCollectionGroupEntry } from '@core/collectionpage/collectionGroupEntry.ts';
import { i18n } from '@core/i18n/index.ts';
import type { PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayoutContract } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import type { PluginRecord } from '@core/types/pluginTypes.ts';
import { createCollectionDisplayModeOverrides, initializeCollectionDisplayModeControllerWithList, renderCollectionDisplayModeElement } from '@core/uiprimitives/viewmode/public.ts';
import { revealRecentCollectionItem } from '@core/collectionpage/recentItemReveal.ts';
import type { PluginsDataController } from '@pages/plugins/controllers/dataController.ts';
import type { PluginsFilterBindings } from '@pages/plugins/controllers/page/contracts.ts';
import type { PluginsPageSession } from '@pages/plugins/controllers/page/PluginsPageSession.ts';
import { syncPluginsListSortIndicators, type PluginsListSortHost } from '@pages/plugins/controllers/page/listSortingController.ts';
import type { PluginsUi } from '@pages/plugins/dom.ts';

const PLUGINS_VIEW_MODE_STORAGE_KEY = 'soai.plugins.viewMode';
const PLUGINS_CARD_IDENTITY_ATTRIBUTE = 'data-plugin';
interface PluginsCollectionPresentationDependencies {
    session: PluginsPageSession;
    collections: PageCollections;
    pageDom: PageDom;
    services: PageServices;
    pageElements: PageUi;
    router: Router;
    layout: PageLayoutContract;
    filters: PluginsFilterBindings;
    dataController: PluginsDataController;
    storage: PageControlsStorageInput;
}

class PluginsCollectionPresentationController {
    readonly #dependencies: PluginsCollectionPresentationDependencies;

    constructor(dependencies: PluginsCollectionPresentationDependencies) {
        this.#dependencies = dependencies;
    }

    initializeViewMode(ui: PluginsUi): void {
        initializeCollectionDisplayModeControllerWithList(this.#viewModeHost(), ui, {
            storageKey: PLUGINS_VIEW_MODE_STORAGE_KEY,
            context: 'Plugins',
            prepareCollectionViewModeChange: () => {
                const collection = this.#dependencies.collections.runtime;
                if (!collection) throw new Error('Plugins collection is unavailable for view mode preparation');
                collection.prepareForViewModeChange();
            },
            reapplyCollection: () => {
                const collection = this.#dependencies.collections.runtime;
                if (!collection) throw new Error('Plugins collection is unavailable for view mode rebuild');
                collection.rebuildForViewMode();
            },
            syncSortIndicators: (table) => syncPluginsListSortIndicators(this.#listSortHost(), table)
        });
    }

    collectionViewOverrides(): Partial<CollectionConfigurationOptions> {
        const dependencies = this.#dependencies;
        return {
            ...createCollectionDisplayModeOverrides(
                {
                    pageDom: dependencies.pageDom,
                    get viewMode() {
                        return dependencies.session.viewMode;
                    }
                },
                {
                    gridSelector: '#plugins-grid',
                    listSelector: '#plugins-list-body',
                    itemDataKey: 'plugin'
                }
            ),
            loadingLabel: () => i18n.t('plugins.loading.morePlugins')
        };
    }

    renderItems(): void {
        const runtime = this.#dependencies.collections.runtime;
        const controller = this.#dependencies.session.cardController;
        if (!runtime || !controller) return;
        controller.renderCollection({ filteredItems: runtime.getFiltered(), allItems: runtime.getAll() });
    }

    renderItem(plugin: ResourceItem): HTMLElement {
        const renderer = this.#dependencies.session.cardRenderer;
        if (!renderer) throw new Error('PluginsPage requires renderers before rendering collection items');
        const record = this.#dependencies.dataController.resolvePluginRecord(plugin);
        if (!record) throw new Error('PluginsPage received an invalid plugin collection item');
        const element = renderCollectionDisplayModeElement({
            viewMode: this.#dependencies.session.viewMode,
            item: record,
            context: 'Plugins',
            renderCard: (item) => renderer.render(item),
            renderListRow: (item) => renderer.renderListRow(item)
        });
        if (!(element instanceof HTMLElement)) throw new Error('Plugins rendered element must be an HTMLElement');
        if (this.#dependencies.session.viewMode === 'list') return element;
        const pluginId = this.#dependencies.dataController.getItemCardId(record);
        return renderCollectionGroupEntry({ card: element, heading: pluginId ? this.#dependencies.session.grouping.headingFor(pluginId) : null, identityAttribute: PLUGINS_CARD_IDENTITY_ATTRIBUTE });
    }

    toggleViewMode(): void {
        const controller = this.#dependencies.session.viewModeController;
        if (!controller) throw new Error('Plugins view mode controller is unavailable');
        controller.toggle();
    }

    navigateToModels(action: string, plugin: PluginRecord | string | null | undefined, parameters: Record<string, string> = {}): boolean {
        const actionName = typeof action === 'string' ? action.trim() : '';
        const pluginName = this.#dependencies.dataController.resolvePluginRecord(plugin)?.name;
        if (!actionName || !pluginName) return false;
        this.#dependencies.router.navigateWithQuery('models', { ...parameters, action: actionName, plugin: pluginName });
        return true;
    }

    consumeSnapshot(snapshot: ResourceSnapshot): void {
        const value = toJsonCompatibleValue(snapshot);
        this.#dependencies.session.recentItems.consumeSnapshot(isJsonObject(value) ? value : null);
    }

    revealRecentItem(): void {
        const runtime = this.#dependencies.collections.runtime;
        if (!runtime) return;
        const identifiers: string[] = [];
        for (const value of runtime.getFiltered()) {
            const record = this.#dependencies.dataController.resolvePluginRecord(value);
            if (!record) continue;
            const identifier = this.#dependencies.dataController.getItemCardId(value);
            if (identifier !== null) identifiers.push(String(identifier));
        }
        revealRecentCollectionItem({ recentItems: this.#dependencies.session.recentItems, collectionView: this.#dependencies.collections.view, identifiers });
    }

    #viewModeHost(): Parameters<typeof initializeCollectionDisplayModeControllerWithList>[0] {
        const dependencies = this.#dependencies;
        return {
            services: dependencies.services,
            get viewMode() {
                return dependencies.session.viewMode;
            },
            set viewMode(value) {
                dependencies.session.viewMode = value;
            },
            get viewModeController() {
                return dependencies.session.viewModeController;
            },
            set viewModeController(value) {
                dependencies.session.viewModeController = value;
            }
        };
    }

    #listSortHost(): PluginsListSortHost {
        const { filters } = this.#dependencies;
        return {
            services: this.#dependencies.services,
            pageElements: this.#dependencies.pageElements,
            pageDom: this.#dependencies.pageDom,
            storage: this.#dependencies.storage,
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
            }
        };
    }
}

export { PluginsCollectionPresentationController };
