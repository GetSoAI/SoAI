/* SoAI - Search page result presenter controller [frontend/assets/ts/pages/search/services/resultPresenterController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { checkerboardService, dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderSearchCategoryStateMarkup } from '@core/search/searchCategoryStateMarkup.ts';
import type { SearchFilter } from '@core/search/searchCategory.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { SearchResultsRenderInput, SearchResultsRenderOutput } from '@pages/search/controllers/renderController.ts';
import type { SearchPageServiceDependencies } from '@pages/search/services/contracts.ts';

type SearchResultsViewOptions = { clearBadgesWhenEmpty: boolean; updateBadges: boolean };
type SearchStatusType = 'emptyQuery' | 'notFound' | 'recentEmpty';
type SearchStatusCopy = { title: string; message: string };
type FileSearchStatus = 'idle' | 'loading' | 'empty' | 'error';

interface SearchPageResultsState {
    primaryResults: SearchItem[];
    fileResults: SearchItem[];
    fileStatus: FileSearchStatus;
    currentFilter: SearchFilter;
    query: string;
}

const resolveSearchStatusCopy = (statusType: SearchStatusType, query: string): SearchStatusCopy => {
    if (statusType === 'emptyQuery') {
        return {
            title: i18n.t('search.noResults.emptyTitle'),
            message: i18n.t('search.noResults.emptyMessage')
        };
    }
    if (statusType === 'notFound') {
        return {
            title: i18n.t('search.noResults.title'),
            message: i18n.t('search.noResults.notFound', { query })
        };
    }
    return {
        title: i18n.t('search.recent.emptyTitle'),
        message: i18n.t('search.recent.noSearches')
    };
};

const resolveSearchFailureStatusCopy = (serviceUnavailable: boolean): SearchStatusCopy => ({
    title: i18n.t('search.errors.searchFailed'),
    message: serviceUnavailable ? i18n.t('search.errors.serviceUnavailable') : i18n.t('search.errors.genericError')
});

const renderFileStateMarkup = (fileStatus: FileSearchStatus, query: string): TrustedHtml => {
    if (fileStatus === 'loading') {
        return renderSearchCategoryStateMarkup({
            category: 'files',
            type: 'loading',
            message: i18n.t('search.status.searchingFiles')
        });
    }
    if (fileStatus === 'error') {
        return renderSearchCategoryStateMarkup({
            category: 'files',
            type: 'error',
            message: i18n.t('search.errors.fileSearchFailed')
        });
    }
    return renderSearchCategoryStateMarkup({
        category: 'files',
        type: 'empty',
        message: i18n.t('search.noResults.filesNotFound', { query })
    });
};

class SearchPageResultPresenter {
    readonly #dependencies: SearchPageServiceDependencies;
    readonly #checkerboardContainerIds = new Set<string>();
    #currentStatus: SearchStatusCopy | null = null;

    constructor(dependencies: SearchPageServiceDependencies) {
        this.#dependencies = dependencies;
    }

    get currentStatus(): SearchStatusCopy | null {
        return this.#currentStatus;
    }

    clearStatus(): void {
        this.#currentStatus = null;
    }

    dispose(): void {
        this.#disconnectCheckerboards();
        this.#currentStatus = null;
    }

    showStatus(statusType: SearchStatusType, query: string, clearBadges: boolean): void {
        this.showStatusCopy(resolveSearchStatusCopy(statusType, query), clearBadges);
    }

    showStatusCopy(status: SearchStatusCopy, clearBadges: boolean): void {
        this.#disconnectCheckerboards();
        this.#currentStatus = status;
        this.#dependencies.view.showStatusMessage(status.title, status.message, clearBadges);
    }

    showSearchingState(): void {
        const ui = this.#dependencies.view.getUiRefs();
        this.#disconnectCheckerboards();
        this.#dependencies.view.updateHTML(ui.resultsContainer, EMPTY_UI_HTML);
        this.#dependencies.view.setLoadingState(ui.resultsContainer, true, i18n.t('search.status.searching'));
        this.#dependencies.view.toggleResultsVisibility(true);
    }

    renderRecentSearches(recentSearches: string[]): void {
        if (recentSearches.length === 0) {
            this.showStatus('recentEmpty', '', false);
            this.#dependencies.view.setTabNotifyBadge('recent', 0);
            return;
        }
        this.#renderResultsMarkup(this.#dependencies.renderController.renderRecentSearchesMarkup(recentSearches));
        this.#currentStatus = null;
        this.#dependencies.view.setTabNotifyBadge('recent', recentSearches.length);
        this.#dependencies.view.toggleResultsVisibility(true);
    }

    renderResultsState(state: SearchPageResultsState, options: SearchResultsViewOptions): void {
        if (state.currentFilter === 'files') {
            this.#renderFilesFilter(state, options);
            return;
        }
        const aggregateResults = [...state.primaryResults, ...state.fileResults];
        const output = this.#renderSearchResults(aggregateResults, state.currentFilter);
        if (options.updateBadges) {
            this.#updateAggregateBadges(state);
        }
        if (!output.hasVisibleResults && state.currentFilter === 'all' && (state.fileStatus === 'loading' || state.fileStatus === 'error')) {
            this.#renderStandaloneFileState(state, options);
            return;
        }
        if (!output.hasVisibleResults) {
            this.showStatus('notFound', state.query, aggregateResults.length === 0 ? options.clearBadgesWhenEmpty : false);
            return;
        }
        this.#renderResultsMarkup((state.fileStatus === 'loading' || state.fileStatus === 'error') && state.currentFilter === 'all' ? toTrustedUiHtml(`${output.html.html}${renderFileStateMarkup(state.fileStatus, state.query).html}`) : output.html);
    }

    #renderFilesFilter(state: SearchPageResultsState, options: SearchResultsViewOptions): void {
        if (state.fileStatus === 'loading' || state.fileStatus === 'error' || !state.fileResults.length) {
            this.#renderStandaloneFileState(state, options);
            return;
        }
        const output = this.#renderSearchResults(state.fileResults, 'files');
        if (options.updateBadges) {
            this.#updateAggregateBadges(state);
        }
        this.#renderResultsMarkup(output.html);
    }

    #renderStandaloneFileState(state: SearchPageResultsState, options: SearchResultsViewOptions): void {
        if (options.updateBadges && state.currentFilter === 'files') {
            this.#updateAggregateBadges(state);
        }
        if (state.fileStatus === 'empty' && state.currentFilter === 'all' && !state.primaryResults.length) {
            this.showStatus('notFound', state.query, options.clearBadgesWhenEmpty);
            return;
        }
        this.#renderResultsMarkup(renderFileStateMarkup(state.fileStatus === 'idle' ? 'empty' : state.fileStatus, state.query));
    }

    #renderSearchResults(results: SearchItem[], currentFilter: SearchFilter): SearchResultsRenderOutput {
        const renderInput: SearchResultsRenderInput = {
            results,
            currentFilter,
            recentCount: this.#dependencies.searchHistory.getRecentSearches().length
        };
        return this.#dependencies.renderController.renderSearchResults(renderInput);
    }

    #updateAggregateBadges(state: SearchPageResultsState): void {
        this.#dependencies.view.updateTabNotifyBadges(this.#renderSearchResults([...state.primaryResults, ...state.fileResults], 'all').counts);
    }

    #renderResultsMarkup(markup: TrustedHtml): void {
        const ui = this.#dependencies.view.getUiRefs();
        this.#disconnectCheckerboards();
        this.#dependencies.view.updateHTML(ui.resultsContainer, markup);
        for (const container of dom.resolveAll('.search-category-content', ui.resultsContainer)) {
            checkerboardService.applyCheckerboard(container, '.search-item--card');
            this.#checkerboardContainerIds.add(checkerboardService.getContainerId(container));
        }
        this.#currentStatus = null;
        this.#dependencies.view.toggleResultsVisibility(true);
    }

    #disconnectCheckerboards(): void {
        for (const containerId of this.#checkerboardContainerIds) checkerboardService.disconnect(containerId);
        this.#checkerboardContainerIds.clear();
    }
}

export { SearchPageResultPresenter, resolveSearchFailureStatusCopy };
export type { FileSearchStatus, SearchPageResultsState, SearchStatusCopy };
