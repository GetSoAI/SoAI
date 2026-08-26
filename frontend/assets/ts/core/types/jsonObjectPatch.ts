/* SoAI - Shared frontend types JSON object patch [frontend/assets/ts/core/types/jsonObjectPatch.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';

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

export { mergeJsonObjectPatch };
