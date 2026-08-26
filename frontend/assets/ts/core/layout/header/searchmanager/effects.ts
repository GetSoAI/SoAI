/* SoAI - Shared layout search manager effects [frontend/assets/ts/core/layout/header/searchmanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { cancelFileExplorerContentPreviewRequest, isFileExplorerContentPreviewApi, openFileExplorerContentPreview } from '@core/fileexplorerbrowser/contentPreview.ts';
import { i18n } from '@core/i18n/index.ts';
import { setHeaderDropdownState } from '@core/layout/header/dropdownController.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { normalizeSearchCategory } from '@core/search/searchCategory.ts';
import { readSearchResultDataset, resolveSearchResultNavigation } from '@core/search/searchResultActivation.ts';
import { normalizeSearchDisplayQuery } from '@core/search/searchQuery.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { buildSearchErrorMarkup, buildSearchInitializingMarkup, buildSearchNoResultsMarkup, buildSearchResultsMarkup, buildSearchResultsWithCategoryStateMarkup, getSearchButtonRenderState } from '@core/layout/header/searchmanager/actions.ts';
import { isRouterInterface } from '@core/layout/header/searchmanager/guards.ts';
import type { HeaderSearchManagerContract, SearchManagerCollapseOptions, RouterInterface, SearchManagerRefs, SearchNavigationCommand } from '@core/layout/header/searchmanager/types.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { SearchCategoryStateType } from '@core/search/searchCategoryStateMarkup.ts';

type SearchEffectsRuntime = Pick<HeaderSearchManagerContract, 'abortSearchRequest' | 'advanceSearchToken' | 'button' | 'cancelBlurTimer' | 'cancelScheduledSearch' | 'collapse' | 'container' | 'displaySearchError' | 'dropdown' | 'expanded' | 'header' | 'input' | 'panel' | 'requireDom' | 'requireDropdownItems' | 'selectedIndex' | 'statusManager' | 'updateSelectedItems'>;

const getSearchManagerRefs = (manager: SearchEffectsRuntime): SearchManagerRefs | null => {
    const container = manager.container;
    const input = manager.input;
    const button = manager.button;
    const dropdown = manager.dropdown;
    if (!(container instanceof HTMLElement) || !(input instanceof HTMLInputElement) || !(button instanceof HTMLElement) || !(dropdown instanceof HTMLElement)) {
        return null;
    }
    return { container, input, button, dropdown };
};

const renderSearchButtonFromRefs = (manager: SearchEffectsRuntime, refs: Pick<SearchManagerRefs, 'button' | 'input'>): void => {
    const hasText = Boolean(normalizeSearchDisplayQuery(refs.input?.value ?? ''));
    const state = getSearchButtonRenderState(manager.expanded, hasText, (name, options) => manager.header.icons.get(name, options));
    const hasSearchIconLayer = dom.resolve('.header-search__button-icon--search', refs.button) instanceof HTMLElement;
    const hasCloseIconLayer = dom.resolve('.header-search__button-icon--close', refs.button) instanceof HTMLElement;
    const hasIconLayers = hasSearchIconLayer && hasCloseIconLayer;
    if (!hasIconLayers) {
        manager.header.updateHTML(refs.button, state.iconMarkup, { escape: false });
    }
    manager.header.updateAttribute(refs.button, 'data-search-button-state', state.iconType);
    setTooltipText(refs.button, state.ariaLabel);
    manager.header.updateAttribute(refs.button, 'aria-label', state.ariaLabel);
    manager.header.updateAttribute(refs.button, 'aria-expanded', manager.expanded ? 'true' : 'false');
    manager.header.updateAttribute(refs.button, 'aria-haspopup', 'true');
};

const resolveSearchRouter = (manager: SearchEffectsRuntime): RouterInterface => {
    return manager.header.resolveService('core.router', isRouterInterface, 'Router');
};

const isMobileMode = (): boolean => {
    const viewport = measureLayoutViewport();
    return viewport.width <= 900 || viewport.height < 640;
};

const renderSearchButton = (manager: SearchEffectsRuntime): void => {
    const { button, input } = manager.requireDom();
    renderSearchButtonFromRefs(manager, { button, input });
};

const updateSearchSelectedItems = (manager: SearchEffectsRuntime, nodes: HTMLElement[], options: { scroll?: boolean } = {}): void => {
    const shouldScroll = options.scroll !== false;
    nodes.forEach((node, index) => {
        if (index === manager.selectedIndex) {
            manager.header.addClassName(node, 'search-item-selected');
            if (shouldScroll) {
                scrollElementIntoView(node, { block: 'nearest', behavior: 'smooth' });
            }
            return;
        }
        manager.header.removeClassName(node, 'search-item-selected');
    });
};

const navigateSearchItem = (manager: SearchEffectsRuntime, nodes: HTMLElement[], delta: number): void => {
    if (!nodes.length) {
        return;
    }
    manager.selectedIndex = clampNumber(manager.selectedIndex + delta, -1, nodes.length - 1);
    manager.updateSelectedItems(nodes);
};

const handleSearchItemNavigation = async (manager: SearchEffectsRuntime, node: HTMLElement): Promise<void> => {
    try {
        const router = resolveSearchRouter(manager);
        const dataset = node?.dataset ?? {};
        const searchDataset = readSearchResultDataset(dataset);
        const navigation: SearchNavigationCommand = resolveSearchResultNavigation(searchDataset);
        manager.collapse({ blur: false });
        const normalizedType = normalizeSearchCategory(searchDataset.type ?? '');
        const shouldOpenFilePreview = normalizedType === 'files' && searchDataset.fileEntryType === 'file' && Boolean(searchDataset.filePath);
        const shouldOpenPromptPreview = normalizedType === 'prompt' && Boolean(searchDataset.id);
        if (shouldOpenFilePreview && searchDataset.filePath) {
            const api = manager.header.resolveService('core.apiClient', isFileExplorerContentPreviewApi, 'API client');
            const opened = await openFileExplorerContentPreview(api, searchDataset.filePath);
            if (opened) {
                return;
            }
        } else if (shouldOpenPromptPreview && searchDataset.id) {
            cancelFileExplorerContentPreviewRequest();
            const panel = manager.panel;
            if (!panel) {
                throw new Error('Search panel is unavailable for prompt preview');
            }
            const opened = await panel.openPromptPreview(searchDataset.id);
            if (opened) {
                return;
            }
        } else {
            cancelFileExplorerContentPreviewRequest();
        }
        if (navigation.query) {
            router.navigateWithQuery(navigation.route, navigation.query, { force: navigation.route === 'fileExplorer' });
            return;
        }
        await router.navigate(navigation.route);
    } catch (error) {
        const runtimeError = ensureError(error);
        manager.header.logger('error', 'Search result activation failed', runtimeError);
        manager.displaySearchError();
    }
};

const showSearchMessage = (manager: SearchEffectsRuntime, markup: TrustedHtml): void => {
    const { button, dropdown } = manager.requireDom();
    const styles = getComputedStyle(button);
    if (styles.display === 'none' || button.classList.contains('u-hidden')) {
        return;
    }
    manager.header.updateHTML(dropdown, markup, { escape: false });
    manager.header.removeClassName(dropdown, 'u-hidden');
    manager.selectedIndex = -1;
};

const wireSearchResultItems = (manager: SearchEffectsRuntime): void => {
    const items = manager.requireDropdownItems();
    items.forEach((item, index) => {
        manager.header.on(item, 'mousedown', () => {
            manager.cancelBlurTimer();
        });
        manager.header.on(item, 'click', (event: Event) => {
            event.preventDefault();
            terminateHandledPromise(handleSearchItemNavigation(manager, item));
        });
        manager.header.on(item, 'mouseenter', () => {
            manager.selectedIndex = index;
            manager.updateSelectedItems(items, { scroll: false });
        });
        manager.header.on(item, 'mouseleave', () => {
            manager.selectedIndex = -1;
            manager.updateSelectedItems(items, { scroll: false });
        });
    });
};

const renderSearchMarkup = (manager: SearchEffectsRuntime, markup: TrustedHtml): void => {
    const { dropdown } = manager.requireDom();
    manager.header.updateHTML(dropdown, markup, { escape: false });
    manager.header.removeClassName(dropdown, 'u-hidden');
    manager.selectedIndex = -1;
    wireSearchResultItems(manager);
};

const renderSearchResults = (manager: SearchEffectsRuntime, results: SearchItem[]): void => {
    const markup = buildSearchResultsMarkup(results, manager.statusManager, (name, options) => manager.header.icons.get(name, options));
    renderSearchMarkup(manager, markup);
};

const renderSearchResultsWithCategoryState = (manager: SearchEffectsRuntime, results: SearchItem[], state: { category: string; type: SearchCategoryStateType; message: string }): void => {
    const markup = buildSearchResultsWithCategoryStateMarkup(results, state, manager.statusManager, (name, options) => manager.header.icons.get(name, options));
    renderSearchMarkup(manager, markup);
};

const renderSearchNoResults = (manager: SearchEffectsRuntime, query: string): void => {
    const markup = buildSearchNoResultsMarkup(query);
    showSearchMessage(manager, markup);
};

const renderSearchInitializing = (manager: SearchEffectsRuntime): void => {
    const message = buildSearchInitializingMarkup();
    showSearchMessage(manager, message);
};

const renderSearchError = (manager: SearchEffectsRuntime): void => {
    const message = buildSearchErrorMarkup();
    showSearchMessage(manager, message);
};

const resetSearchDropdown = (manager: SearchEffectsRuntime): void => {
    const { dropdown } = manager.requireDom();
    manager.header.updateHTML(dropdown, EMPTY_UI_HTML, { escape: false });
    manager.header.addClassName(dropdown, 'u-hidden');
    manager.selectedIndex = -1;
};

const collapseSearchManager = (manager: SearchEffectsRuntime, options: SearchManagerCollapseOptions = {}): void => {
    manager.cancelScheduledSearch();
    manager.cancelBlurTimer();
    manager.abortSearchRequest();
    manager.advanceSearchToken();
    const refs = getSearchManagerRefs(manager);
    const { blur = true } = options;
    if (!refs) {
        if (manager.input instanceof HTMLInputElement) {
            manager.header.updateProperty(manager.input, 'value', '');
        }
        manager.selectedIndex = -1;
        manager.expanded = false;
        setHeaderDropdownState(manager.button, false);
        return;
    }
    const { container, input, button, dropdown } = refs;
    manager.header.updateHTML(dropdown, EMPTY_UI_HTML, { escape: false });
    manager.header.addClassName(dropdown, 'u-hidden');
    manager.header.updateProperty(input, 'value', '');
    manager.selectedIndex = -1;
    manager.header.removeClassName(container, 'header-search--expanded');
    if (blur) {
        manager.input?.blur();
    }
    manager.header.updateProperty(input, 'disabled', true);
    manager.expanded = false;
    renderSearchButtonFromRefs(manager, { button, input });
    setHeaderDropdownState(button, false);
};

const localizeSearchManager = (manager: SearchEffectsRuntime): void => {
    const { container, input } = manager.requireDom();
    const label = i18n.t('header.search.placeholder');
    manager.header.updateAttribute(input, 'placeholder', label);
    manager.header.updateAttribute(input, 'aria-label', label);
    renderSearchButton(manager);
    manager.header.updateAttribute(container, 'aria-label', i18n.t('header.search.containerAria'));
};

const expandSearchManager = (manager: SearchEffectsRuntime): void => {
    const { container, input } = manager.requireDom();
    manager.header.closeDropdowns({ except: 'search' });
    manager.header.addClassName(container, 'header-search--expanded');
    manager.header.updateProperty(input, 'disabled', false);
    input.focus();
    manager.expanded = true;
    renderSearchButton(manager);
    setHeaderDropdownState(manager.button, true);
};

const onSearchNavigation = (manager: SearchEffectsRuntime, component: string | null): void => {
    const { button } = manager.requireDom();
    if (component === 'search') {
        manager.header.addClassName(button, 'u-hidden');
        collapseSearchManager(manager, { blur: false });
        return;
    }
    manager.header.removeClassName(button, 'u-hidden');
};

const getSearchItemStatus = (manager: SearchEffectsRuntime, item: SearchItem): string => {
    if (!item || !item.status) {
        return '';
    }
    return serializeElementToHtml(manager.statusManager.createIndicator(item.status));
};

export { collapseSearchManager, expandSearchManager, getSearchItemStatus, handleSearchItemNavigation, isMobileMode, localizeSearchManager, navigateSearchItem, onSearchNavigation, renderSearchButton, renderSearchError, renderSearchInitializing, renderSearchNoResults, renderSearchResults, renderSearchResultsWithCategoryState, resetSearchDropdown, showSearchMessage, updateSearchSelectedItems };
