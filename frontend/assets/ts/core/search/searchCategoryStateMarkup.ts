/* SoAI - Search category state markup [frontend/assets/ts/core/search/searchCategoryStateMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveSearchCategoryLabel } from '@core/search/searchCategory.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';

type SearchCategoryStateType = 'loading' | 'empty' | 'error';

interface SearchCategoryStateMarkupOptions {
    category: string;
    type: SearchCategoryStateType;
    message: string;
}

const renderSearchCategoryStateMarkup = (options: SearchCategoryStateMarkupOptions): TrustedHtml => {
    const label = resolveSearchCategoryLabel(options.category);
    const stateClassName = `search-category-state search-category-state--${options.type}`;
    if (options.type === 'loading') {
        return uiHtml`<div class="search-category glass-surface-strong" data-search-category-state="${uiAttr(options.category)}"><div class="section-header"><h2 class="section-title">${label}</h2></div><div class="search-category-content"><div class="${uiAttr(stateClassName)}" aria-live="polite"><span class="loading-spinner" aria-hidden="true"></span><span class="loading-text">${options.message}</span></div></div></div>`;
    }
    return uiHtml`<div class="search-category glass-surface-strong" data-search-category-state="${uiAttr(options.category)}"><div class="section-header"><h2 class="section-title">${label}</h2></div><div class="search-category-content"><div class="${uiAttr(stateClassName)}" aria-live="polite"><span class="search-category-state-text">${options.message}</span></div></div></div>`;
};

export { renderSearchCategoryStateMarkup };
export type { SearchCategoryStateMarkupOptions, SearchCategoryStateType };
