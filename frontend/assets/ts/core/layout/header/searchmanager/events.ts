/* SoAI - Shared layout search manager events [frontend/assets/ts/core/layout/header/searchmanager/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { getPrompt, getWindow } from '@core/environment/public.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { cancelFileExplorerContentPreviewRequest } from '@core/fileexplorerbrowser/contentPreview.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { isFunction } from '@core/typeGuards.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { queryReferencesConversationOnly } from '@core/search/directReference.ts';
import { SEARCH_PANEL_SERVICE_ID } from '@core/search/protocols.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import { isRouterInterface, isSearchPanelInterface } from '@core/layout/header/searchmanager/guards.ts';
import { requireSearchDom } from '@core/layout/header/searchmanager/dom.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { isMobileMode } from '@core/layout/header/searchmanager/effects.ts';
import type { HeaderSearchManagerContract, SearchPanelInterface } from '@core/layout/header/searchmanager/types.ts';

type SearchInitializationRuntime = Pick<HeaderSearchManagerContract, 'blurTimeoutId' | 'button' | 'collapse' | 'container' | 'dropdown' | 'expand' | 'handleButtonClick' | 'handleInput' | 'handleKeyDown' | 'handleResize' | 'header' | 'input' | 'localize' | 'performSearch' | 'requireDom' | 'resetResults' | 'searchToken' | 'updateButtonIcon'>;
type SearchResizeRuntime = Pick<HeaderSearchManagerContract, 'collapse' | 'expanded'>;
type SearchExecutionRuntime = Pick<HeaderSearchManagerContract, 'displayNoResults' | 'displayResults' | 'displayResultsWithCategoryState' | 'displaySearchError' | 'displaySearchInitializing' | 'header' | 'isSessionActive' | 'panel' | 'searchToken' | 'showMessage' | 'startSearchRequest'>;
type SearchScheduleRuntime = SearchExecutionRuntime & Pick<HeaderSearchManagerContract, 'cancelScheduledSearch' | 'timeoutId'>;
type SearchInputRuntime = SearchScheduleRuntime & Pick<HeaderSearchManagerContract, 'hideDropdown' | 'requireDom' | 'resetResults' | 'scheduleSearch'>;
type SearchKeyboardRuntime = Pick<HeaderSearchManagerContract, 'collapse' | 'header' | 'navigateSearchItem' | 'requireDom' | 'requireDropdownItems' | 'selectedIndex'>;
type SearchButtonRuntime = Pick<HeaderSearchManagerContract, 'collapse' | 'expand' | 'expanded' | 'header' | 'requireDom'>;

const initializeSearchManager = async (manager: SearchInitializationRuntime): Promise<void> => {
    const { container, input, button, dropdown } = requireSearchDom(manager.header);
    manager.container = container;
    manager.input = input;
    manager.button = button;
    manager.dropdown = dropdown;
    if (!isFunction(manager.header.closeDropdowns)) {
        throw new Error('Header must expose dropdown coordination support APIs');
    }
    manager.collapse({ blur: false });
    manager.localize();
    manager.header.on(manager.input, 'input', () => {
        manager.handleInput();
        manager.updateButtonIcon();
    });
    manager.header.on(manager.input, 'keydown', (event: Event) => {
        if (event instanceof KeyboardEvent) {
            manager.handleKeyDown(event);
        }
    });
    manager.header.on(manager.input, 'focus', () => {
        manager.expand();
        const { input } = manager.requireDom();
        const query = normalizeSearchDisplayQuery(input.value);
        if (query && query.length >= 2) {
            manager.resetResults();
            const token = manager.searchToken;
            terminateHandledPromise(manager.performSearch(query, token));
        }
    });
    manager.header.on(manager.input, 'blur', () => {
        manager.blurTimeoutId = manager.header.setTimer(() => manager.collapse({ blur: false }), 200);
    });
    manager.header.on(manager.button, 'click', (event: Event) => manager.handleButtonClick(event));
    manager.header.on(getWindow(), 'resize', () => manager.handleResize());
    manager.header.on(getWindow(), INTERFACE_SCALE_CHANGED_EVENT, () => manager.handleResize());
};

const handleSearchResize = (manager: SearchResizeRuntime): void => {
    if (!manager.expanded) {
        return;
    }
    if (isMobileMode()) {
        manager.collapse({ blur: true });
    }
};

const ensureSearchPanel = async (manager: Pick<SearchExecutionRuntime, 'header' | 'panel'>): Promise<SearchPanelInterface> => {
    if (manager.panel) {
        if (!manager.panel.isInitialized) {
            await manager.panel.initialize();
        }
        return manager.panel;
    }
    const panel = manager.header.resolveService(SEARCH_PANEL_SERVICE_ID, isSearchPanelInterface, 'SearchPanel');
    if (!panel.isInitialized) {
        await panel.initialize();
    }
    manager.panel = panel;
    return panel;
};

const performSearch = async (manager: SearchExecutionRuntime, query: string, token: number = manager.searchToken): Promise<void> => {
    const normalizedQuery = normalizeSearchDisplayQuery(query);
    if (!normalizedQuery || normalizedQuery.length < 2) {
        return;
    }
    if (!manager.isSessionActive(token)) {
        return;
    }
    const conversationReferenceOnly = queryReferencesConversationOnly(normalizedQuery);
    const abortController = manager.startSearchRequest();
    try {
        const searchPanel = await ensureSearchPanel(manager);
        if (!manager.isSessionActive(token) || abortController.signal.aborted) {
            return;
        }
        manager.showMessage(uiHtml`<div class="search-loading">${i18n.t('search.status.searching')}</div>`);
        if (!manager.isSessionActive(token) || abortController.signal.aborted) {
            return;
        }
        const primaryResults: SearchItem[] = await searchPanel.search(normalizedQuery, 10, { immediate: true, signal: abortController.signal });
        if (!manager.isSessionActive(token) || abortController.signal.aborted) {
            return;
        }
        if (!conversationReferenceOnly) {
            manager.displayResultsWithCategoryState(primaryResults, {
                category: 'files',
                type: 'loading',
                message: i18n.t('search.status.searchingFiles')
            });
            try {
                const fileResults = await searchPanel.searchFiles(normalizedQuery, 10, { signal: abortController.signal });
                if (!manager.isSessionActive(token) || abortController.signal.aborted) {
                    return;
                }
                if (fileResults.length) {
                    manager.displayResults([...primaryResults, ...fileResults]);
                    return;
                }
                if (primaryResults.length) {
                    manager.displayResultsWithCategoryState(primaryResults, {
                        category: 'files',
                        type: 'empty',
                        message: i18n.t('search.noResults.filesNotFound', { query: normalizedQuery })
                    });
                    return;
                }
            } catch (error) {
                const runtimeError = ensureError(error);
                if (isAbortError(runtimeError) || !manager.isSessionActive(token) || abortController.signal.aborted) {
                    return;
                }
                errorHandler.warn('HeaderSearch', 'File search execution failed', runtimeError);
                manager.header.logger('warn', 'File search execution failed', runtimeError);
                manager.displayResultsWithCategoryState(primaryResults, {
                    category: 'files',
                    type: 'error',
                    message: i18n.t('search.errors.fileSearchFailed')
                });
                return;
            }
        } else if (primaryResults.length) {
            manager.displayResults(primaryResults);
            return;
        }
        if (isFunction(searchPanel.isSystemReady) && !searchPanel.isSystemReady()) {
            manager.displaySearchInitializing();
            return;
        }
        manager.displayNoResults(normalizedQuery);
    } catch (error) {
        const runtimeError = ensureError(error);
        if (isAbortError(runtimeError) || !manager.isSessionActive(token) || abortController.signal.aborted) {
            return;
        }
        manager.header.logger('warn', 'Search execution failed', runtimeError);
        manager.displaySearchError();
    }
};

const scheduleSearch = (manager: SearchScheduleRuntime, query: string, token: number = manager.searchToken): void => {
    manager.cancelScheduledSearch();
    manager.timeoutId = manager.header.setTimer(() => {
        terminateHandledPromise(performSearch(manager, query, token));
    }, 300);
};

const handleInput = (manager: SearchInputRuntime): void => {
    cancelFileExplorerContentPreviewRequest();
    const query = normalizeSearchDisplayQuery(manager.requireDom().input.value);
    if (!query || query.length < 2) {
        manager.hideDropdown();
        return;
    }
    manager.resetResults();
    manager.scheduleSearch(query, manager.searchToken);
};

const handleKeyDown = (manager: SearchKeyboardRuntime, event: KeyboardEvent): void => {
    const items = manager.requireDropdownItems();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        manager.navigateSearchItem(items, event.key === 'ArrowDown' ? 1 : -1);
        return;
    }
    if (event.key === 'Enter') {
        event.preventDefault();
        if (manager.selectedIndex >= 0 && items[manager.selectedIndex]) {
            const selected = items[manager.selectedIndex];
            if (selected) {
                selected.click();
            }
            return;
        }
        const query = normalizeSearchDisplayQuery(manager.requireDom().input.value);
        if (query) {
            const storage = manager.header.getStorage();
            storage.addRecentSearch(query);
            const router = manager.header.resolveService('core.router', isRouterInterface, 'Router');
            router.navigateWithQuery('search', { q: query });
            manager.collapse({});
        }
        return;
    }
    if (event.key === 'Escape') {
        event.preventDefault();
        manager.collapse({});
    }
};

const handleButtonClick = (manager: SearchButtonRuntime, event: Event): void => {
    event.preventDefault();
    event.stopPropagation();
    if (isMobileMode()) {
        const placeholder = i18n.t('header.search.placeholder');
        const prompt = getPrompt();
        const query = prompt(placeholder);
        const trimmedQuery = normalizeSearchDisplayQuery(query ?? '');
        if (trimmedQuery) {
            const storage = manager.header.getStorage();
            storage.addRecentSearch(trimmedQuery);
            const router = manager.header.resolveService('core.router', isRouterInterface, 'Router');
            router.navigateWithQuery('search', { q: trimmedQuery });
        }
        return;
    }
    if (manager.expanded) {
        const { input } = manager.requireDom();
        const query = normalizeSearchDisplayQuery(input.value);
        if (query) {
            const storage = manager.header.getStorage();
            storage.addRecentSearch(query);
            const router = manager.header.resolveService('core.router', isRouterInterface, 'Router');
            router.navigateWithQuery('search', { q: query });
        }
        manager.collapse({});
        return;
    }
    manager.expand();
};

export { ensureSearchPanel, handleButtonClick, handleInput, handleKeyDown, handleSearchResize, initializeSearchManager, performSearch, scheduleSearch };
