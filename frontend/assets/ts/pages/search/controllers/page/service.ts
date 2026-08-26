/* SoAI - Search page service [frontend/assets/ts/pages/search/controllers/page/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import { openFileExplorerContentPreview } from '@core/fileexplorerbrowser/contentPreview.ts';
import { i18n } from '@core/i18n/index.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { normalizeSearchFilter, resolveSearchTabLabel, SEARCH_VISIBLE_TAB_IDS } from '@core/search/searchCategory.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import type { StateManager } from '@core/state/StateManager.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { requireRecentSearchStorage } from '@core/storage/guards.ts';
import { isFunction } from '@core/typeGuards.ts';
import { showOperationFailureNotification } from '@core/ui/notifications/operationFailure.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { renderSearchNoResultsIcon, createSearchRenderControllerDependencies, createSearchViewDependencies, type SearchPageAdapterDependencies } from '@pages/search/adapters/adapters.ts';
import { isStatusIndicatorFactory, type SearchComponentContract } from '@pages/search/contracts/contracts.ts';
import { SearchDataController } from '@pages/search/controllers/dataController.ts';
import { SearchRenderController } from '@pages/search/controllers/renderController.ts';
import { requireSearchUi } from '@pages/search/dom.ts';
import { SearchPageService } from '@pages/search/services/service.ts';
import type { SearchUiRefs } from '@pages/search/types.ts';
import type { StandardSearchResult } from '@core/routing/pages/pagetypes/public.ts';

const logger = createModuleLogger('SearchPage', { defaultLevel: 'warn' });

interface SearchPageRuntimeOwners {
    api: ApiClient;
    stateManager: StateManager;
    pageContext: PageContext;
    pageDom: PageDom;
    feedback: PageFeedback;
    services: PageServices;
    pageElements: PageUi;
    layout: PageLayout;
    storage: StorageService;
    router: Router;
}

class SearchPageRuntime {
    readonly service: SearchPageService;
    readonly searchAdapter: SearchPageAdapterDependencies;
    readonly #component: SearchComponentContract;
    readonly #owners: SearchPageRuntimeOwners;
    #searchBar: StandardSearchResult | null = null;
    #ui: SearchUiRefs | null = null;

    constructor(searchComponent: SearchComponentContract, owners: SearchPageRuntimeOwners) {
        this.#component = searchComponent;
        this.#owners = owners;
        const recentSearches = requireRecentSearchStorage(owners.storage);
        const dataController = new SearchDataController({ searchComponent });
        this.searchAdapter = {
            searchComponent,
            getRecentSearchIconMarkup: () => owners.services.getIconSync('recent', { size: 16, strokeWidth: 1.5 }),
            statusIndicatorFactory: () => {
                const status = owners.stateManager.status;
                return isStatusIndicatorFactory(status) ? status : null;
            },
            getIconSync: (iconName, options) => owners.services.getIconSync(iconName, options),
            sanitizer: {
                html: (value) => owners.pageContext.sanitizer.html(value),
                attribute: (value) => owners.pageContext.sanitizer.attribute(value)
            },
            getUiRefs: () => this.#requireUi(),
            setLoadingState: (element, isLoading, statusMessage) => owners.pageElements.setLoadingState(element, isLoading, statusMessage),
            updateHTML: (element, html, options) => owners.pageDom.updateHtml(element, html, options),
            updateText: (element, text) => owners.pageDom.updateText(element, text),
            addClassName: (element, className) => owners.pageDom.addClass(element, className),
            removeClassName: (element, className) => owners.pageDom.removeClass(element, className),
            getTabsComponent: () => owners.layout.getTabs(),
            setSearchValue: (value) => this.#searchBar?.setValue(value),
            setTabNotifyBadge: (tab, count) => owners.layout.getTabs()?.updateTabNotifyBadge?.(tab, count)
        };
        const renderController = new SearchRenderController(createSearchRenderControllerDependencies(this.searchAdapter));
        this.service = new SearchPageService({
            dataController,
            renderController,
            searchHistory: recentSearches,
            view: createSearchViewDependencies(this.searchAdapter),
            navigation: {
                navigate: (path) => owners.router.navigate(path),
                navigateWithQuery: (path, query) => {
                    if (!isFunction(owners.router.navigateWithQuery)) {
                        this.#reportError(new Error('Router navigateWithQuery is unavailable'), { context: 'navigation', userMessage: i18n.t('search.errors.genericError') });
                        return;
                    }
                    owners.router.navigateWithQuery(path, query);
                },
                openFilePreview: async (path) => await openFileExplorerContentPreview(owners.api, path),
                openPromptPreview: async (promptId) => await searchComponent.openPromptPreview(promptId)
            },
            errors: { reportError: (error, options) => this.#reportError(error, options) }
        });
    }

    async initializeShell(query: string, signal: AbortSignal | null = null): Promise<void> {
        const normalizedQuery = normalizeSearchDisplayQuery(query);
        if (!this.#component.isInitialized) await this.#component.initialize();
        throwIfAborted(signal);
        this.#ui = requireSearchUi({ pageDom: this.#owners.pageDom });
        renderSearchNoResultsIcon(this.searchAdapter);
        this.#owners.layout.initializeTabs('search-tabs-container', {
            tabs: SEARCH_VISIBLE_TAB_IDS.map((id) => ({ id, label: resolveSearchTabLabel(id) })),
            activeTab: 'all',
            className: 'tabs'
        });
        this.#owners.layout.setupResponsive();
        this.#setupSearchHandlers();
        throwIfAborted(signal);
        if (normalizedQuery) {
            this.#searchBar?.setValue(normalizedQuery);
            await this.service.search(normalizedQuery);
            return;
        }
        this.service.clearSearch();
    }

    onTabChange(tab: string): void {
        const normalized = normalizeSearchFilter(tab);
        if (normalized === null) throw new Error('SearchPage received invalid tab id');
        this.service.setSearchFilter(normalized);
    }

    destroy(): void {
        this.service.resetState();
        this.#searchBar = null;
        this.#ui = null;
    }

    #setupSearchHandlers(): void {
        const container = this.#owners.pageDom.requireHTMLElement('#search-search-container');
        this.#searchBar = this.#owners.layout.createSearch(container, {
            placeholder: i18n.t('search.searchPlaceholder'),
            onSearch: (query) => {
                this.service.search(query).catch((error) => this.#reportError(error, { context: 'search' }));
            },
            onClear: () => this.service.clearSearch()
        });
        this.#searchBar?.setValue(this.service.searchQuery);
    }

    #requireUi(): SearchUiRefs {
        if (!this.#ui) throw new Error('Search page UI has not been initialized');
        return this.#ui;
    }

    #reportError(error: Error, options: { context?: string; userMessage?: string } = {}): void {
        logger('error', options.context || 'SearchPage', error);
        showOperationFailureNotification({
            error,
            fallbackMessage: i18n.t('common.errors.unknownError'),
            notificationMessage: options.userMessage,
            showNotification: (message, level) => this.#owners.feedback.show(message, level)
        });
    }
}

export { SearchPageRuntime };
export type { SearchPageRuntimeOwners };
