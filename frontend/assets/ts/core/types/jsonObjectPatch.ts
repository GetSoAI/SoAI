/* SoAI - Shared frontend types JSON object patch [frontend/assets/ts/core/types/jsonObjectPatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import { cloneJsonObject, cloneJsonValue } from '@core/primitives/clone.ts';
import { deepEqual } from '@core/primitives/equality.ts';

const mergeJsonObjectPatch = (base: JsonObject, patch: JsonObject): JsonObject => {
    const merged: JsonObject = { ...base };
    for (const [key, value] of Object.entries(patch)) {
        const existing = merged[key];
        if (isJsonObject(existing) && isJsonObject(value)) {
            merged[key] = mergeJsonObjectPatch(existing, value);
        } else {
            merged[key] = value;
        }
    }
    return merged;
};

const rebaseJsonObjectChanges = (base: JsonObject, edited: JsonObject, latest: JsonObject): JsonObject => {
    const rebased = cloneJsonObject(latest);
    for (const key of new Set([...Object.keys(base), ...Object.keys(edited)])) {
        const original = base[key];
        const local = edited[key];
        if (deepEqual(original, local)) continue;
        if (local === undefined) {
            delete rebased[key];
        } else if (isJsonObject(original) && isJsonObject(local) && isJsonObject(latest[key])) {
            rebased[key] = rebaseJsonObjectChanges(original, local, latest[key]);
        } else {
            rebased[key] = cloneJsonValue(local);
        }
    }
    return rebased;
};

export { mergeJsonObjectPatch, rebaseJsonObjectChanges };
