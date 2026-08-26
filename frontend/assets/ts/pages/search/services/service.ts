/* SoAI - Search page services service [frontend/assets/ts/pages/search/services/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { LatestRequestController, type LatestRequestRun } from '@core/concurrency/latestRequest.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError, isErrorHttpStatus } from '@core/errors/coerce.ts';
import { cancelFileExplorerContentPreviewRequest } from '@core/fileexplorerbrowser/contentPreview.ts';
import { i18n } from '@core/i18n/index.ts';
import { queryReferencesConversationOnly } from '@core/search/directReference.ts';
import { normalizeSearchCategory, type SearchFilter } from '@core/search/searchCategory.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { readSearchItemDataset, resolveSearchResultNavigation, type SearchItemDataset } from '@core/search/searchResultActivation.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import type { SearchPageServiceDependencies } from '@pages/search/services/contracts.ts';
import { SearchPageResultPresenter, resolveSearchFailureStatusCopy, type FileSearchStatus } from '@pages/search/services/resultPresenterController.ts';

type SearchResultsViewOptions = { clearBadgesWhenEmpty: boolean; updateBadges: boolean };

const isFilePreviewDataset = (dataset: SearchItemDataset): boolean => normalizeSearchCategory(dataset.type ?? '') === 'files' && dataset.fileEntryType === 'file' && Boolean(dataset.filePath);
const isPromptPreviewDataset = (dataset: SearchItemDataset): boolean => normalizeSearchCategory(dataset.type ?? '') === 'prompt' && Boolean(dataset.id);

class SearchPageService {
    readonly #dependencies: SearchPageServiceDependencies;
    readonly #requests = new LatestRequestController();
    readonly #presenter: SearchPageResultPresenter;
    #currentFilter: SearchFilter = 'all';
    #isPreparingSearch = false;
    #isSearching = false;
    #searchQuery = '';
    #primaryResults: SearchItem[] | null = null;
    #fileResults: SearchItem[] = [];
    #fileStatus: FileSearchStatus = 'idle';

    constructor(dependencies: SearchPageServiceDependencies) {
        this.#dependencies = dependencies;
        this.#presenter = new SearchPageResultPresenter(dependencies);
    }

    get searchQuery(): string {
        return this.#searchQuery;
    }

    resetState(): void {
        cancelFileExplorerContentPreviewRequest();
        this.#requests.invalidate();
        this.#searchQuery = '';
        this.#currentFilter = 'all';
        this.#isPreparingSearch = false;
        this.#isSearching = false;
        this.#primaryResults = null;
        this.#fileResults = [];
        this.#fileStatus = 'idle';
        this.#presenter.dispose();
        this.#dependencies.view.clearTabNotifyBadges();
    }

    setSearchFilter(newFilter: SearchFilter): void {
        this.#currentFilter = newFilter;
        if (newFilter === 'recent') {
            this.#renderRecentSearches();
            return;
        }
        if (this.#primaryResults !== null) {
            this.#renderResultsView({ clearBadgesWhenEmpty: false, updateBadges: false });
            return;
        }
        if (this.#isPreparingSearch) {
            this.#dependencies.view.showInitializingMessage();
            return;
        }
        if (this.#isSearching) {
            this.#presenter.showSearchingState();
            return;
        }
        if (this.#searchQuery && this.#presenter.currentStatus) {
            this.#presenter.showStatusCopy(this.#presenter.currentStatus, false);
            return;
        }
        this.#presenter.showStatus('emptyQuery', this.#searchQuery, false);
    }

    async search(query: string): Promise<void> {
        const normalizedQuery = normalizeSearchDisplayQuery(query);
        if (!normalizedQuery) {
            this.clearSearch();
            return;
        }
        this.#activateResultsFilter();

        await this.#requests.runLatest(async (request) => {
            this.#beginSearch(normalizedQuery);
            try {
                const { items, searchReady } = await this.#dependencies.dataController.executeSearch(normalizedQuery, { signal: request.signal });
                if (request.isStale()) {
                    return null;
                }
                if (!searchReady && !items.length) {
                    this.#showPreparingState();
                    return null;
                }
                const conversationReferenceOnly = queryReferencesConversationOnly(normalizedQuery);
                this.#applyPrimaryResults(normalizedQuery, items, !conversationReferenceOnly);
                if (!conversationReferenceOnly) {
                    await this.#searchFiles(normalizedQuery, request);
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                if (request.isStale()) {
                    return null;
                }
                this.#handleSearchError(runtimeError);
            } finally {
                if (request.isCurrent()) {
                    this.#isSearching = false;
                    this.#dependencies.view.setLoadingState(this.#dependencies.view.getUiRefs().resultsContainer, false);
                }
            }
            return null;
        });
    }

    clearSearch(): void {
        cancelFileExplorerContentPreviewRequest();
        this.#searchQuery = '';
        this.#isPreparingSearch = false;
        this.#isSearching = false;
        this.#primaryResults = null;
        this.#fileResults = [];
        this.#fileStatus = 'idle';
        this.#presenter.clearStatus();
        this.#requests.invalidate();
        const ui = this.#dependencies.view.getUiRefs();
        this.#dependencies.view.setLoadingState(ui.resultsContainer, false);
        if (this.#currentFilter === 'recent') {
            this.#renderRecentSearches();
            return;
        }
        this.#presenter.showStatus('emptyQuery', this.#searchQuery, true);
    }

    handleRecentSearchSelection(item: HTMLElement): void {
        const query = item.dataset['search'];
        if (!query) {
            throw new Error('Recent search item is missing its search query');
        }
        this.#searchQuery = query;
        this.#dependencies.view.setSearchValue(query);
        this.#activateResultsFilter();
        terminateHandledPromise(this.search(query));
    }

    clearRecentSearches(): void {
        this.#dependencies.searchHistory.clearRecentSearches();
        this.#dependencies.view.setTabNotifyBadge('recent', 0);
        if (this.#currentFilter === 'recent') {
            this.#renderRecentSearches();
        } else if (this.#primaryResults !== null) {
            this.#renderResultsView({ clearBadgesWhenEmpty: false, updateBadges: false });
        }
    }

    handleSearchItemClick(itemElement: HTMLElement): void {
        terminateHandledPromise(this.#activateSearchItem(itemElement));
    }

    async #activateSearchItem(itemElement: HTMLElement): Promise<void> {
        try {
            const dataset = readSearchItemDataset(itemElement);
            const navigation = resolveSearchResultNavigation(dataset);
            if (isFilePreviewDataset(dataset) && dataset.filePath) {
                const opened = await this.#dependencies.navigation.openFilePreview(dataset.filePath);
                if (opened) {
                    return;
                }
            } else if (isPromptPreviewDataset(dataset) && dataset.id) {
                cancelFileExplorerContentPreviewRequest();
                const opened = await this.#dependencies.navigation.openPromptPreview(dataset.id);
                if (opened) {
                    return;
                }
            } else {
                cancelFileExplorerContentPreviewRequest();
            }
            if (navigation.query) {
                this.#dependencies.navigation.navigateWithQuery(navigation.route, navigation.query, { force: navigation.route === 'fileExplorer' });
                return;
            }
            this.#dependencies.navigation.navigate(navigation.route);
        } catch (error) {
            this.#dependencies.errors.reportError(ensureError(error), {
                context: 'search-result-activation',
                userMessage: i18n.t('search.errors.genericError')
            });
        }
    }

    #beginSearch(normalizedQuery: string): void {
        cancelFileExplorerContentPreviewRequest();
        this.#searchQuery = normalizedQuery;
        this.#isPreparingSearch = false;
        this.#isSearching = true;
        this.#primaryResults = null;
        this.#fileResults = [];
        this.#fileStatus = 'idle';
        this.#presenter.clearStatus();
        this.#presenter.showSearchingState();
    }

    #showPreparingState(): void {
        this.#isPreparingSearch = true;
        this.#primaryResults = null;
        if (this.#currentFilter === 'recent') {
            this.#renderRecentSearches();
            return;
        }
        this.#dependencies.view.showInitializingMessage();
    }

    #applyPrimaryResults(normalizedQuery: string, items: SearchItem[], fileSearchPlanned: boolean): void {
        this.#dependencies.searchHistory.addRecentSearch(normalizedQuery);
        this.#dependencies.view.setTabNotifyBadge('recent', this.#dependencies.searchHistory.getRecentSearches().length);
        this.#isPreparingSearch = false;
        this.#primaryResults = items;
        this.#fileStatus = fileSearchPlanned ? 'loading' : 'idle';
        if (this.#currentFilter === 'recent') {
            this.#renderRecentSearches();
            return;
        }
        this.#renderResultsView({ clearBadgesWhenEmpty: true, updateBadges: true });
    }

    async #searchFiles(normalizedQuery: string, request: LatestRequestRun): Promise<void> {
        try {
            const fileResults = await this.#dependencies.dataController.executeFileSearch(normalizedQuery, { signal: request.signal });
            if (request.isStale()) {
                return;
            }
            this.#fileResults = fileResults;
            this.#fileStatus = fileResults.length ? 'idle' : 'empty';
        } catch (error) {
            const runtimeError = ensureError(error);
            if (request.isStale() || isAbortError(runtimeError)) {
                return;
            }
            this.#dependencies.errors.reportError(runtimeError, {
                context: 'perform-file-search',
                userMessage: i18n.t('search.errors.fileSearchFailed')
            });
            this.#fileResults = [];
            this.#fileStatus = 'error';
        }
        if (this.#currentFilter !== 'recent') {
            this.#renderResultsView({ clearBadgesWhenEmpty: true, updateBadges: true });
        }
    }

    #renderResultsView(options: SearchResultsViewOptions): void {
        this.#presenter.renderResultsState(
            {
                primaryResults: this.#primaryResults ?? [],
                fileResults: this.#fileResults,
                fileStatus: this.#fileStatus,
                currentFilter: this.#currentFilter,
                query: this.#searchQuery
            },
            options
        );
    }

    #renderRecentSearches(): void {
        this.#presenter.renderRecentSearches(this.#dependencies.searchHistory.getRecentSearches());
    }

    #activateResultsFilter(): void {
        if (this.#currentFilter === 'recent') {
            this.#currentFilter = 'all';
            this.#dependencies.view.setActiveTab('all');
        }
    }

    #handleSearchError(error: Error): void {
        const runtimeError = ensureError(error);
        const status = resolveSearchFailureStatusCopy(isErrorHttpStatus(runtimeError, 422));
        this.#dependencies.errors.reportError(runtimeError, {
            context: 'perform-search',
            userMessage: status.title
        });
        this.#presenter.showStatusCopy(status, true);
    }
}

export { SearchPageService };
