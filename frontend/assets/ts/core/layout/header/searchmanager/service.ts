/* SoAI - Shared layout search manager service [frontend/assets/ts/core/layout/header/searchmanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getStatusManager } from '@core/state/public.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { initializeSearchManager, performSearch, scheduleSearch, handleButtonClick, handleInput, handleKeyDown, handleSearchResize } from '@core/layout/header/searchmanager/events.ts';
import { collapseSearchManager, expandSearchManager, getSearchItemStatus, handleSearchItemNavigation, isMobileMode, localizeSearchManager, navigateSearchItem, onSearchNavigation, renderSearchButton, renderSearchError, renderSearchInitializing, renderSearchNoResults, renderSearchResults, renderSearchResultsWithCategoryState, resetSearchDropdown, showSearchMessage, updateSearchSelectedItems } from '@core/layout/header/searchmanager/effects.ts';
import { isSearchManagerHost, isStatusManagerInterface } from '@core/layout/header/searchmanager/guards.ts';
import { collectSearchItems, requireSearchDom } from '@core/layout/header/searchmanager/dom.ts';
import type { SearchManagerCollapseOptions, SearchManagerHost, SearchPanelInterface, SearchManagerOptions, SearchManagerRefs, StatusManagerInterface } from '@core/layout/header/searchmanager/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';

export class HeaderSearchManager {
    header: SearchManagerHost;
    expanded: boolean;
    selectedIndex: number;
    timeoutId: number | null;
    blurTimeoutId: number | null;
    panel: SearchPanelInterface | null;
    container: SearchManagerRefs['container'] | null;
    input: SearchManagerRefs['input'] | null;
    button: SearchManagerRefs['button'] | null;
    dropdown: SearchManagerRefs['dropdown'] | null;
    searchToken: number;
    searchAbortController: AbortController | null;
    statusManager: StatusManagerInterface;

    constructor({ header }: SearchManagerOptions) {
        this.header = header;
        if (!isSearchManagerHost(header)) {
            throw new Error('HeaderSearchManager requires a header with event binding support');
        }
        const statusManagerCandidate = getStatusManager();
        if (!isStatusManagerInterface(statusManagerCandidate)) {
            throw new Error('Status manager must expose createIndicator before initializing HeaderSearchManager');
        }
        this.statusManager = statusManagerCandidate;
        this.expanded = false;
        this.selectedIndex = -1;
        this.timeoutId = null;
        this.blurTimeoutId = null;
        this.panel = null;
        this.container = null;
        this.input = null;
        this.button = null;
        this.dropdown = null;
        this.searchToken = 0;
        this.searchAbortController = null;
    }

    async initialize(): Promise<void> {
        await initializeSearchManager(this);
    }

    isMobileMode(): boolean {
        return isMobileMode();
    }

    handleResize(): void {
        handleSearchResize(this);
    }

    destroy(): void {
        this.cancelScheduledSearch();
        this.cancelBlurTimer();
        this.abortSearchRequest();
        this.panel = null;
        this.container = null;
        this.input = null;
        this.button = null;
        this.dropdown = null;
        this.expanded = false;
        this.selectedIndex = -1;
        this.searchToken = 0;
    }

    advanceSearchToken(): number {
        this.searchToken += 1;
        return this.searchToken;
    }

    startSearchRequest(): AbortController {
        this.abortSearchRequest();
        const controller = new AbortController();
        this.searchAbortController = controller;
        return controller;
    }

    abortSearchRequest(): void {
        this.searchAbortController?.abort();
        this.searchAbortController = null;
    }

    cancelScheduledSearch(): void {
        this.header.clearTimer(this.timeoutId);
        this.timeoutId = null;
    }

    cancelBlurTimer(): void {
        this.header.clearTimer(this.blurTimeoutId);
        this.blurTimeoutId = null;
    }

    isSessionActive(token: number): boolean {
        return this.expanded && token === this.searchToken;
    }

    resetResults(): void {
        this.cancelScheduledSearch();
        this.abortSearchRequest();
        this.advanceSearchToken();
        this.resetDropdown();
    }

    hideDropdown(): void {
        this.resetResults();
    }

    collapse(options: SearchManagerCollapseOptions = {}): void {
        collapseSearchManager(this, options);
    }

    onNavigation(component: string | null): void {
        onSearchNavigation(this, component);
    }

    localize(): void {
        localizeSearchManager(this);
    }

    expand(): void {
        expandSearchManager(this);
    }

    updateButtonIcon(): void {
        renderSearchButton(this);
    }

    resetDropdown(): void {
        resetSearchDropdown(this);
    }

    showMessage(markup: TrustedHtml): void {
        showSearchMessage(this, markup);
    }

    getSearchItemStatus(item: SearchItem): string {
        return getSearchItemStatus(this, item);
    }

    updateSelectedItems(nodes: HTMLElement[], options: { scroll?: boolean } = {}): void {
        updateSearchSelectedItems(this, nodes, options);
    }

    navigateSearchItem(nodes: HTMLElement[], delta: number): void {
        navigateSearchItem(this, nodes, delta);
    }

    handleSearchItemClick(node: HTMLElement): void {
        terminateHandledPromise(handleSearchItemNavigation(this, node));
    }

    displayResults(results: SearchItem[]): void {
        renderSearchResults(this, results);
    }

    displayResultsWithCategoryState(results: SearchItem[], state: { category: string; type: 'loading' | 'empty' | 'error'; message: string }): void {
        renderSearchResultsWithCategoryState(this, results, state);
    }

    displayNoResults(query: string): void {
        renderSearchNoResults(this, query);
    }

    displaySearchInitializing(): void {
        renderSearchInitializing(this);
    }

    displaySearchError(): void {
        renderSearchError(this);
    }

    async performSearch(query: string, token: number = this.searchToken): Promise<void> {
        await performSearch(this, query, token);
    }

    scheduleSearch(query: string, token: number = this.searchToken): void {
        scheduleSearch(this, query, token);
    }

    handleInput(): void {
        handleInput(this);
    }

    handleKeyDown(event: KeyboardEvent): void {
        handleKeyDown(this, event);
    }

    handleButtonClick(event: Event): void {
        handleButtonClick(this, event);
    }

    requireDom(): SearchManagerRefs {
        return requireSearchDom(this.header);
    }

    requireDropdownItems(): HTMLElement[] {
        const { dropdown } = this.requireDom();
        return collectSearchItems(dropdown);
    }
}
