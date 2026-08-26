/* SoAI - Search feature mappers [frontend/assets/ts/features/search/panel/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { SearchIndex, SearchItem } from '@core/search/searchTypes.ts';
import type { SearchIndexKey } from '@features/search/panel/contracts.ts';
import { calculateRelevanceScore, deduplicateResults, sortResultsByRelevance } from '@features/search/searchItemScoring.ts';

const getSearchIndexBucket = (index: SearchIndex, type: SearchIndexKey): Map<string, SearchItem> => {
    switch (type) {
        case 'models':
            return index.models;
        case 'plugins':
            return index.plugins;
        case 'devices':
            return index.devices;
        case 'configs':
            return index.configs;
        case 'pages':
            return index.pages;
        case 'help':
            return index.help;
        case 'modals':
            return index.modals;
        case 'powerActions':
            return index.powerActions;
    }
    throw new Error(`Unsupported search index type: ${String(type)}`);
};

const collectSearchResults = (index: SearchIndex, term: string): SearchItem[] => {
    const normalizedTerm = normalizeSearchMatchQuery(term);
    if (!normalizedTerm) {
        return [];
    }
    const all: SearchItem[] = [];
    const buckets: SearchIndexKey[] = ['models', 'plugins', 'devices', 'configs', 'pages', 'help', 'modals', 'powerActions'];
    for (const key of buckets) {
        const bucket = getSearchIndexBucket(index, key);
        for (const item of bucket.values()) {
            const score = calculateRelevanceScore(item, normalizedTerm);
            if (score > 0) {
                all.push({ ...item, score });
            }
        }
    }
    return all;
};

const mergeSearchResults = (remoteResults: SearchItem[], localResults: SearchItem[], limit: number | null): SearchItem[] => {
    const aggregated: SearchItem[] = [...remoteResults, ...localResults];
    const sorted = sortResultsByRelevance(deduplicateResults(aggregated));
    return limit === null ? sorted : sorted.slice(0, limit);
};

export { getSearchIndexBucket, collectSearchResults, mergeSearchResults };
