/* SoAI - Shared search query normalization helpers [frontend/assets/ts/core/search/searchQuery.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { toTrimmedLower, toTrimmedString } from '@core/normalize.ts';

const SEARCH_SEPARATOR_PATTERN = /[\s_]+/g;
const SEARCH_CONFIG_PATH_SEPARATOR_PATTERN = /\./g;

type SearchConfigPathMatch = 'exact' | 'suffix' | 'partial' | 'none';

const normalizeSearchDisplayQuery = (value: JsonValue): string => toTrimmedString(value);

const normalizeSearchMatchQuery = (value: JsonValue): string => toTrimmedLower(value).replace(SEARCH_SEPARATOR_PATTERN, ' ').trim();

const normalizeSearchConfigPathQuery = (value: JsonValue): string => normalizeSearchMatchQuery(toTrimmedString(value).replace(SEARCH_CONFIG_PATH_SEPARATOR_PATTERN, ' '));

const createSearchTextIndex = (values: readonly JsonValue[]): string => values.map(normalizeSearchMatchQuery).filter(Boolean).join(' ');

const matchesSearchFilterQuery = (value: JsonValue, query: JsonValue): boolean => {
    const normalizedQuery = normalizeSearchMatchQuery(query);
    if (!normalizedQuery) {
        return true;
    }
    return normalizeSearchMatchQuery(value).includes(normalizedQuery);
};

const matchSearchConfigPath = (configPath: JsonValue, query: JsonValue): SearchConfigPathMatch => {
    const normalizedPath = normalizeSearchConfigPathQuery(configPath);
    const normalizedQuery = normalizeSearchConfigPathQuery(query);
    if (!normalizedPath || !normalizedQuery) {
        return 'none';
    }
    if (normalizedPath === normalizedQuery) {
        return 'exact';
    }
    if (normalizedPath.endsWith(normalizedQuery)) {
        return 'suffix';
    }
    if (normalizedPath.includes(normalizedQuery)) {
        return 'partial';
    }
    return 'none';
};

const createSearchCacheKey = (searchTerm: string, limit: number): string => `${normalizeSearchMatchQuery(searchTerm)}::${String(limit)}`;

export { createSearchCacheKey, createSearchTextIndex, matchesSearchFilterQuery, matchSearchConfigPath, normalizeSearchConfigPathQuery, normalizeSearchDisplayQuery, normalizeSearchMatchQuery };
export type { SearchConfigPathMatch };
