/* SoAI - Default collection item identity and sorting behavior [frontend/assets/ts/core/collectionpage/defaultBehavior.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import { isArray, isObject } from '@core/typeGuards.ts';

const getDefaultCollectionItemCardId = (item: ResourceIncomingValue): string | null => {
    if (!isObject(item) || isArray(item)) return null;
    const identifier = item['id'] ?? item['name'];
    return typeof identifier === 'string' || typeof identifier === 'number' ? String(identifier) : null;
};

const getDefaultCollectionSortValue = (item: ResourceItem, field: string): string | number | null => {
    const value = item[field];
    return typeof value === 'string' || typeof value === 'number' ? value : null;
};

export { getDefaultCollectionItemCardId, getDefaultCollectionSortValue };
