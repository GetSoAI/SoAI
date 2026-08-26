/* SoAI - Shared collection page recent item snapshot [frontend/assets/ts/core/collectionpage/recentItemSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';
import { isArray, isObject, isString } from '@core/typeGuards.ts';

type RecentItemDiffKey = 'added' | 'removed';

const collectRecentItemDiffIds = (snapshot: JsonObject | null | undefined, key: RecentItemDiffKey): string[] => {
    if (!isObject(snapshot)) {
        return [];
    }
    const diff = snapshot['diff'];
    if (!isObject(diff)) {
        return [];
    }
    const values = diff[key];
    if (!isArray(values)) {
        return [];
    }
    const identifiers: string[] = [];
    for (const value of values) {
        const identifier = isString(value) ? value.trim() : '';
        if (identifier) {
            identifiers.push(identifier);
        }
    }
    return identifiers;
};

export { collectRecentItemDiffIds };
