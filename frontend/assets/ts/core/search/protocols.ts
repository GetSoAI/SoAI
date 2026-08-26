/* SoAI - Shared search protocols [frontend/assets/ts/core/search/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SearchIndex, SearchItem } from '@core/search/searchTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const SEARCH_PANEL_SERVICE_ID = 'features.search.panel';
const SEARCH_SOURCE_HARDWARE = 'hardware';

type SearchIndexContributorBucket = keyof SearchIndex;

interface SearchIndexContributor {
    readonly id: string;
    readonly bucket: SearchIndexContributorBucket;
    readonly source: string;
    index: (resourceValue: JsonValue) => SearchItem[];
}

interface SearchStaticIndexContext {
    readonly grantedActions: ReadonlySet<string>;
}

interface SearchStaticIndexContributor {
    readonly id: string;
    readonly bucket: SearchIndexContributorBucket;
    index: (context: SearchStaticIndexContext) => SearchItem[] | Promise<SearchItem[]>;
}

export { SEARCH_PANEL_SERVICE_ID, SEARCH_SOURCE_HARDWARE };
export type { SearchIndexContributor, SearchIndexContributorBucket, SearchStaticIndexContext, SearchStaticIndexContributor };
