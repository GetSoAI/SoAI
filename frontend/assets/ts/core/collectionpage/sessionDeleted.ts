/* SoAI - Shared collection page session deleted [frontend/assets/ts/core/collectionpage/sessionDeleted.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { Storage } from '@core/collectionpage/types.ts';
import { isArray, isString } from '@core/typeGuards.ts';

const readSessionDeletedIds = (pageId: string, storage: Storage | undefined, storageKey: string): Set<string> => {
    const stored = storage?.get?.(storageKey);
    if (!isArray(stored)) {
        return new Set();
    }
    const ids: string[] = [];
    stored.forEach((value, index) => {
        if (!isString(value)) {
            throw new TypeError(`${pageId} session deleted id at index ${index} must be a string`);
        }
        ids.push(value);
    });
    return new Set(ids);
};

const writeSessionDeletedIds = (storage: Storage | undefined, storageKey: string, ids: Set<string>): void => {
    storage?.set?.(storageKey, [...ids]);
};

export { readSessionDeletedIds, writeSessionDeletedIds };
