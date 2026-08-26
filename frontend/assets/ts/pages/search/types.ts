/* SoAI - Search page public contracts [frontend/assets/ts/pages/search/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchItem } from '@core/search/searchTypes.ts';

export type SearchResultsByCategory = Record<string, SearchItem[]>;

export interface SearchUiRefs {
    resultsContainer: HTMLElement;
    noResultsContainer: HTMLElement;
    noResultsIcon: HTMLElement;
    tabsContainer: HTMLElement;
    noResultsTitle: HTMLElement;
    noResultsMessage: HTMLElement;
}
