/* SoAI - Shared frontend collection cache [frontend/assets/ts/core/collectionCache.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readStorageJson, writeStorageJson } from '@core/storage/ttlStorageCache.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { isBoolean } from '@core/typeGuards.ts';

const STORAGE_KEY = 'soai.collection.cache';

const readCache = (): JsonObject => {
    const parsed = readStorageJson('localStorage', STORAGE_KEY);
    return isJsonObject(parsed) ? parsed : {};
};

const collectionCache = Object.freeze({
    hasItemsCached(key: string): boolean | null {
        const value = readCache()[key];
        return isBoolean(value) ? value : null;
    },
    set(key: string, hasItems: boolean): void {
        const data = readCache();
        data[key] = hasItems;
        writeStorageJson('localStorage', STORAGE_KEY, data);
    }
});

export { collectionCache };
