/* SoAI - Search page DOM contracts [frontend/assets/ts/pages/search/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageDomHost } from '@core/routing/pages/pageDomHost.ts';
import type { SearchUiRefs } from '@pages/search/types.ts';

export const requireSearchResultsContainer = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#search-results');
export const requireNoResultsContainer = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#no-results');
export const requireNoResultsIcon = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#no-results-icon');
export const requireTabsContainer = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#search-tabs-container');
export const requireNoResultsTitle = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#no-results-title');
export const requireNoResultsMessage = (host: PageDomHost): HTMLElement => host.pageDom.requireHTMLElement('#no-results-message');

export const requireSearchUi = (host: PageDomHost): SearchUiRefs => {
    return {
        resultsContainer: requireSearchResultsContainer(host),
        noResultsContainer: requireNoResultsContainer(host),
        noResultsIcon: requireNoResultsIcon(host),
        tabsContainer: requireTabsContainer(host),
        noResultsTitle: requireNoResultsTitle(host),
        noResultsMessage: requireNoResultsMessage(host)
    };
};

export const optionalSearchResultsContainer = (host: PageDomHost): HTMLElement | null => host.pageDom.optionalHTMLElement('#search-results');
