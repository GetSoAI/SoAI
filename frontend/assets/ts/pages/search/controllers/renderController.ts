/* SoAI - Search page render controller [frontend/assets/ts/pages/search/controllers/renderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderer } from '@core/search/SearchResultsRenderer.ts';
import { countSearchResultsByTab, resolveSearchCategoryLabel, searchCategoryMatchesFilter, type SearchFilter, type SearchTabCounts } from '@core/search/searchCategory.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import { SEARCH_ACTION_CLEAR_RECENT, SEARCH_ACTION_OPEN_ITEM, SEARCH_ACTION_SELECT_RECENT } from '@pages/search/actions.ts';
import type { SearchResultsByCategory } from '@pages/search/types.ts';

interface SearchSanitizer {
    html(value: string): string;
    attribute(value: string): string;
}

interface SearchRenderControllerDependencies {
    getSearchItemIconMarkup: (item: SearchItem) => TrustedHtml;
    getSearchItemStatusMarkup: (status: string) => TrustedHtml;
    getRecentSearchIconMarkup: () => TrustedHtml;
    sanitizer: SearchSanitizer;
}

interface SearchResultsRenderOutput {
    html: TrustedHtml;
    counts: SearchTabCounts;
    hasVisibleResults: boolean;
}

export interface SearchResultsRenderInput {
    results: SearchItem[];
    currentFilter: SearchFilter;
    recentCount: number;
}

const requireSearchText = (value: string, label: string): string => {
    const normalized = value.trim();
    if (!normalized) {
        throw new Error(`Search result ${label} must be non-empty`);
    }
    return normalized;
};

class SearchRenderController {
    readonly #dependencies: SearchRenderControllerDependencies;

    constructor(dependencies: SearchRenderControllerDependencies) {
        this.#dependencies = dependencies;
    }

    #groupResultsByType(results: SearchItem[]): SearchResultsByCategory {
        const grouped: SearchResultsByCategory = {};
        for (const item of results) {
            const type = requireSearchText(item.type, 'type');
            const bucket = grouped[type];
            if (bucket) {
                bucket.push(item);
            } else {
                grouped[type] = [item];
            }
        }
        return grouped;
    }

    #orderCategoriesByResultCount(grouped: SearchResultsByCategory, currentFilter: SearchFilter): [string, SearchItem[]][] {
        return Object.entries(grouped)
            .filter(([category]) => searchCategoryMatchesFilter(category, currentFilter))
            .sort(([, first], [, second]) => second.length - first.length);
    }

    renderSearchResults(input: SearchResultsRenderInput): SearchResultsRenderOutput {
        const grouped = this.#groupResultsByType(input.results);
        const visibleResults: SearchItem[] = [];

        for (const [, items] of this.#orderCategoriesByResultCount(grouped, input.currentFilter)) {
            visibleResults.push(...items);
        }

        const counts = countSearchResultsByTab(input.results, input.recentCount);
        return {
            html: renderer.createMarkup(visibleResults, {
                getCategoryDisplayName: (category: string) => resolveSearchCategoryLabel(category),
                getItemAction: () => SEARCH_ACTION_OPEN_ITEM,
                getItemIcon: (item: SearchItem) => this.#dependencies.getSearchItemIconMarkup(item),
                getItemStatus: (item: SearchItem) => (item.status ? this.#dependencies.getSearchItemStatusMarkup(item.status) : EMPTY_UI_HTML),
                itemClassName: 'search-item--card',
                descriptionCharacterLimit: 120,
                includeNameAfterBadge: true
            }),
            counts,
            hasVisibleResults: visibleResults.length > 0
        };
    }

    renderRecentSearchesMarkup(recentSearches: string[]): TrustedHtml {
        const recentIcon = this.#dependencies.getRecentSearchIconMarkup().html;
        const sanitizer = this.#dependencies.sanitizer;
        const clearLabel = sanitizer.html(i18n.t('search.recent.clearAll'));
        const clickableLabel = sanitizer.html(i18n.t('search.recent.clickToSearch'));

        let html = `
        <div class="search-category glass-surface-strong">
        <div class="section-header">
        <h2 class="section-title">${sanitizer.html(i18n.t('search.recent.title'))}</h2>
        <button class="ui-button ui-button--titlebar ui-variant-danger recent-searches-clear" id="clear-recent-searches" data-action="${SEARCH_ACTION_CLEAR_RECENT}" type="button" aria-label="${sanitizer.attribute(i18n.t('search.recent.clearAll'))}" data-tooltip="${sanitizer.attribute(i18n.t('search.recent.clearAll'))}">
        ${clearLabel}
        </button>
        </div>
        <div class="search-category-content">`;

        for (const search of recentSearches) {
            const normalized = requireSearchText(search, 'recent search');
            const safeData = sanitizer.attribute(normalized);
            const safeText = sanitizer.html(normalized);
            html += `
            <button type="button" class="search-item search-item--card recent-search-item" data-action="${SEARCH_ACTION_SELECT_RECENT}" data-search="${safeData}" aria-label="${safeData}" data-tooltip="${safeData}">
            <div class="search-item-icon">${recentIcon}</div>
            <div class="search-item-content">
            <div class="search-item-title" data-tooltip="${sanitizer.attribute(normalized)}">${safeText}</div>
            <div class="search-item-description">${clickableLabel}</div>
            </div>
            </button>`;
        }

        html += `</div></div>`;
        return toTrustedUiHtml(html);
    }
}

export { SearchRenderController, type SearchResultsRenderOutput };
