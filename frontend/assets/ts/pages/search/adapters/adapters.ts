/* SoAI - Search page adapters [frontend/assets/ts/pages/search/adapters/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';
import { i18n } from '@core/i18n/index.ts';
import { normalizeSearchCategory, SEARCH_VISIBLE_TAB_IDS, type SearchFilter, type SearchTabCounts } from '@core/search/searchCategory.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { isFunction } from '@core/typeGuards.ts';
import { applyFilteredTabNotifyBadges, clearFilteredTabNotifyBadges, type FilterTabsComponent, type TabCountEntry } from '@core/ui/controls/tabs/filterState.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { SearchComponentContract, SearchStatusIndicatorFactory } from '@pages/search/contracts/contracts.ts';
import type { SearchViewDependencies } from '@pages/search/services/contracts.ts';
import type { SearchUiRefs } from '@pages/search/types.ts';

export interface SearchPageAdapterDependencies {
    searchComponent: SearchComponentContract;
    getRecentSearchIconMarkup: () => TrustedHtml;
    statusIndicatorFactory: () => SearchStatusIndicatorFactory | null;
    getIconSync: (iconName: IconName, options?: IconOptions) => TrustedHtml;
    sanitizer: {
        html(value: string): string;
        attribute(value: string): string;
    };
    getUiRefs: () => SearchUiRefs;
    setLoadingState: (element: HTMLElement, isLoading: boolean, statusMessage?: string) => void;
    updateHTML: (element: HTMLElement, html: TrustedHtml, options?: { escape?: boolean }) => void;
    updateText: (element: HTMLElement, text: string) => void;
    addClassName: (element: Element, className: string) => void;
    removeClassName: (element: Element, className: string) => void;
    getTabsComponent: () => FilterTabsComponent | null;
    setSearchValue: (value: string) => void;
    setTabNotifyBadge: (tab: SearchFilter, count: number) => void;
}

const getTypeMetadata = (searchComponent: SearchComponentContract, category: string) => {
    const normalized = normalizeSearchCategory(category);
    const metadata = searchComponent.getTypeMetadata(normalized);
    if (!metadata || !metadata.icon) {
        throw new Error(`Search type metadata is invalid for category "${category}"`);
    }
    return metadata;
};

export const createSearchRenderControllerDependencies = (dependencies: SearchPageAdapterDependencies): { getSearchItemIconMarkup: (item: SearchItem) => TrustedHtml; getSearchItemStatusMarkup: (status: string) => TrustedHtml; getRecentSearchIconMarkup: () => TrustedHtml; sanitizer: { html(value: string): string; attribute(value: string): string } } => {
    const getTypeMetadataByCategory = (category: string) => getTypeMetadata(dependencies.searchComponent, category);
    const getSearchItemIconMarkup = (item: SearchItem): TrustedHtml => {
        if (item.icon) {
            return dependencies.getIconSync(item.icon, { size: 16, strokeWidth: 1.5 });
        }
        const metadata = getTypeMetadataByCategory(item.type);
        return dependencies.getIconSync(metadata.icon, { size: 16, strokeWidth: 1.5 });
    };

    const getSearchItemStatusMarkup = (status: string): TrustedHtml => {
        if (!status) {
            return EMPTY_UI_HTML;
        }
        const factory = dependencies.statusIndicatorFactory();
        if (!factory || !isFunction(factory.createIndicator)) {
            return EMPTY_UI_HTML;
        }
        const indicator = factory.createIndicator(status);
        return indicator instanceof HTMLElement ? toTrustedUiHtml(serializeElementToHtml(indicator)) : EMPTY_UI_HTML;
    };

    return {
        getSearchItemIconMarkup,
        getSearchItemStatusMarkup,
        getRecentSearchIconMarkup: dependencies.getRecentSearchIconMarkup,
        sanitizer: dependencies.sanitizer
    };
};

export const createSearchViewDependencies = (dependencies: SearchPageAdapterDependencies): SearchViewDependencies => {
    const toggleResultsVisibility = (show: boolean): void => {
        const ui = dependencies.getUiRefs();
        if (show) {
            dependencies.removeClassName(ui.resultsContainer, 'u-hidden');
            dependencies.addClassName(ui.noResultsContainer, 'u-hidden');
            return;
        }
        dependencies.addClassName(ui.resultsContainer, 'u-hidden');
        dependencies.removeClassName(ui.noResultsContainer, 'u-hidden');
    };

    const showStatusMessage = (title: string, message: string, clearBadges = false): void => {
        const ui = dependencies.getUiRefs();
        dependencies.updateHTML(ui.resultsContainer, EMPTY_UI_HTML);
        toggleResultsVisibility(false);
        dependencies.updateText(ui.noResultsTitle, title);
        dependencies.updateText(ui.noResultsMessage, message);
        if (clearBadges) {
            clearFilteredTabNotifyBadges(dependencies.getTabsComponent(), SEARCH_VISIBLE_TAB_IDS);
        }
    };

    const showInitializingMessage = (): void => {
        showStatusMessage(i18n.t('search.status.preparing'), i18n.t('search.status.loading'), true);
    };

    const updateTabNotifyBadges = (counts: SearchTabCounts): void => {
        const tabCounts: TabCountEntry[] = [];
        Object.entries(counts).forEach(([tabId, count]) => {
            tabCounts.push([tabId, count]);
        });
        applyFilteredTabNotifyBadges(dependencies.getTabsComponent(), tabCounts, true);
    };

    const clearTabNotifyBadges = (): void => {
        clearFilteredTabNotifyBadges(dependencies.getTabsComponent(), SEARCH_VISIBLE_TAB_IDS);
    };

    const setActiveTab = (tab: SearchFilter): void => {
        const tabs = dependencies.getTabsComponent();
        tabs?.setActiveTab?.(tab);
    };

    return {
        getUiRefs: () => dependencies.getUiRefs(),
        setLoadingState: (element, isLoading, statusMessage) => dependencies.setLoadingState(element, isLoading, statusMessage),
        toggleResultsVisibility,
        updateHTML: (element, html, options) => dependencies.updateHTML(element, html, options),
        showStatusMessage,
        showInitializingMessage,
        updateTabNotifyBadges,
        clearTabNotifyBadges,
        setActiveTab,
        setSearchValue: (value) => dependencies.setSearchValue(value),
        setTabNotifyBadge: (tab, count) => dependencies.setTabNotifyBadge(tab, count)
    };
};

export const renderSearchNoResultsIcon = (dependencies: Pick<SearchPageAdapterDependencies, 'getIconSync' | 'getUiRefs' | 'updateHTML'>): void => {
    const ui = dependencies.getUiRefs();
    const markup = dependencies.getIconSync('search', { size: 48, strokeWidth: 1.5 });
    dependencies.updateHTML(ui.noResultsIcon, markup, { escape: false });
};
