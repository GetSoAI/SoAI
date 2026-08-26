/* SoAI - Shared collection search helpers [frontend/assets/ts/core/collectionpage/search.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { matchesSearchFilterQuery, normalizeSearchMatchQuery } from '@core/search/searchQuery.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const normalizeCollectionSearchQuery = (value: JsonValue | null | undefined): string => normalizeSearchMatchQuery(value ?? null);

const matchesCollectionSearchFields = (fields: readonly (JsonValue | null | undefined)[], query: JsonValue | null | undefined): boolean => {
    const normalizedQuery = normalizeCollectionSearchQuery(query);
    if (!normalizedQuery) {
        return true;
    }
    return fields.some((field) => matchesSearchFilterQuery(field ?? null, normalizedQuery));
};

export { matchesCollectionSearchFields, normalizeCollectionSearchQuery };
