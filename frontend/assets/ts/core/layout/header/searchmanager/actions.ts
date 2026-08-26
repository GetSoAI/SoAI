/* SoAI - Shared layout search manager actions [frontend/assets/ts/core/layout/header/searchmanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import { i18n } from '@core/i18n/index.ts';
import { EMPTY_UI_HTML, uiHtml } from '@core/security/uiHtml.ts';
import { resolveSearchCategoryLabel } from '@core/search/searchCategory.ts';
import type { IconOptions } from '@core/layout/HeaderInterface.ts';
import { renderer } from '@core/search/SearchResultsRenderer.ts';
import { renderSearchCategoryStateMarkup, type SearchCategoryStateType } from '@core/search/searchCategoryStateMarkup.ts';
import type { SearchItem } from '@core/search/searchTypes.ts';
import { ICON_ALIASES, SEARCH_TEMPLATES } from '@core/layout/header/searchmanager/constants.ts';
import type { StatusManagerInterface } from '@core/layout/header/searchmanager/types.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { requireIconName } from '@core/ui/icons/iconservice/public.ts';
import { serializeElementToHtml } from '@core/dom/html.ts';

interface SearchButtonRenderState {
    iconMarkup: TrustedHtml;
    iconType: 'search' | 'close';
    ariaLabel: string;
}

type SearchIconResolver = (name: IconName, options?: IconOptions) => TrustedHtml | undefined;

const SEARCH_ICON_OPTIONS: IconOptions = { size: 16, strokeWidth: 1.5 };

const requireIconMarkup = (resolver: SearchIconResolver, iconName: IconName): TrustedHtml => {
    const iconMarkup = resolver(iconName, SEARCH_ICON_OPTIONS);
    if (!iconMarkup || !isString(iconMarkup.html) || !iconMarkup.html.trim()) {
        throw new Error(`HeaderSearchManager requires icon "${iconName}"`);
    }
    return iconMarkup;
};

const buildSearchButtonIconMarkup = (iconResolver: SearchIconResolver): TrustedHtml => {
    const searchIconMarkup = requireIconMarkup(iconResolver, 'search');
    const closeIconMarkup = requireIconMarkup(iconResolver, 'close');
    const searchLayer = `<span class="header-search__button-icon header-search__button-icon--search" aria-hidden="true">${searchIconMarkup.html}</span>`;
    const closeLayer = `<span class="header-search__button-icon header-search__button-icon--close" aria-hidden="true">${closeIconMarkup.html}</span>`;
    return toTrustedUiHtml(`${searchLayer}${closeLayer}`);
};

const getSearchCategoryDisplayName = (category: string): string => {
    return resolveSearchCategoryLabel(category);
};

const getSearchButtonRenderState = (expanded: boolean, hasText: boolean, iconResolver: SearchIconResolver): SearchButtonRenderState => {
    const showClose = expanded && !hasText;
    const iconType = showClose ? 'close' : 'search';
    const iconMarkup = buildSearchButtonIconMarkup(iconResolver);
    const ariaLabel = expanded ? (hasText ? i18n.t('header.search.submit') : i18n.t('header.search.close')) : i18n.t('header.search.open');
    return { iconMarkup, iconType, ariaLabel };
};

const resolveSearchItemIcon = (iconResolver: SearchIconResolver, item: SearchItem): TrustedHtml => {
    if (isObject(item)) {
        const rawIcon = item['icon'];
        const iconCandidate = isString(rawIcon) ? rawIcon : '';
        if (iconCandidate) {
            const iconName = requireIconName(iconCandidate, 'Search item icon');
            return requireIconMarkup(iconResolver, iconName);
        }
        const typeName = isString(item['type']) ? item['type'].trim() : '';
        const typeAlias = ICON_ALIASES[typeName] || ICON_ALIASES[typeName.toLowerCase()];
        if (typeAlias) {
            return requireIconMarkup(iconResolver, typeAlias);
        }
        const categoryName = isString(item['category']) ? item['category'].trim() : '';
        const categoryAlias = ICON_ALIASES[categoryName] || ICON_ALIASES[categoryName.toLowerCase()];
        if (categoryAlias) {
            return requireIconMarkup(iconResolver, categoryAlias);
        }
    }
    throw new Error('HeaderSearchManager requires a supported search item icon, type, or category');
};

const getSearchItemStatus = (statusManager: StatusManagerInterface, item: SearchItem): TrustedHtml => (isObject(item) && item['status'] ? toTrustedUiHtml(serializeElementToHtml(statusManager.createIndicator(item['status']))) : EMPTY_UI_HTML);

const buildSearchResultsMarkup = (items: SearchItem[], statusManager: StatusManagerInterface, getIconMarkup: SearchIconResolver): TrustedHtml =>
    renderer.createMarkup(items, {
        getCategoryDisplayName: (category: string) => getSearchCategoryDisplayName(category),
        getItemStatus: (item: SearchItem) => getSearchItemStatus(statusManager, item),
        getItemIcon: (item: SearchItem) => resolveSearchItemIcon(getIconMarkup, item),
        getItemAction: () => 'header.search.openItem'
    });

const buildSearchResultsWithCategoryStateMarkup = (items: SearchItem[], state: { category: string; type: SearchCategoryStateType; message: string }, statusManager: StatusManagerInterface, getIconMarkup: SearchIconResolver): TrustedHtml => {
    const resultsMarkup = buildSearchResultsMarkup(items, statusManager, getIconMarkup);
    const stateMarkup = renderSearchCategoryStateMarkup(state);
    return toTrustedUiHtml(`${resultsMarkup.html}${stateMarkup.html}`);
};

const buildSearchNoResultsMarkup = (query: string): TrustedHtml => {
    const message = i18n.t('header.search.noResults', { query });
    return uiHtml`<div class="search-no-results"><div class="search-no-results-text">${message}</div></div>`;
};

const requireSearchTemplate = (key: keyof typeof SEARCH_TEMPLATES): string => {
    const template = SEARCH_TEMPLATES[key];
    if (!template) {
        throw new Error(`HeaderSearchManager template "${String(key)}" is missing`);
    }
    return template;
};

const buildSearchPreparingMarkup = (): TrustedHtml => {
    const template = requireSearchTemplate('preparing');
    return uiHtml`${toTrustedUiHtml(template.replace('{message}', uiHtml`${i18n.t('search.status.preparing')}`.html))}`;
};

const buildSearchSearchingMarkup = (): TrustedHtml => {
    const template = requireSearchTemplate('searching');
    return uiHtml`${toTrustedUiHtml(template.replace('{message}', uiHtml`${i18n.t('search.status.searching')}`.html))}`;
};

const buildSearchErrorMarkup = (): TrustedHtml => {
    const template = requireSearchTemplate('searchError');
    return uiHtml`${toTrustedUiHtml(template.replace('{message}', uiHtml`${i18n.t('header.search.failed')}`.html))}`;
};

const buildSearchInitializingMarkup = (): TrustedHtml => buildSearchPreparingMarkup();

export { buildSearchErrorMarkup, buildSearchInitializingMarkup, buildSearchNoResultsMarkup, buildSearchResultsMarkup, buildSearchResultsWithCategoryStateMarkup, buildSearchSearchingMarkup, getSearchButtonRenderState, resolveSearchItemIcon };

export type { SearchButtonRenderState, SearchIconResolver };
