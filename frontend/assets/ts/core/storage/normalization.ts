/* SoAI - Shared storage normalization [frontend/assets/ts/core/storage/normalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SessionData } from '@core/storage/types.ts';
import { isJsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isString } from '@core/typeGuards.ts';

const normalizeSessionData = (value: JsonValue | undefined): SessionData => (isJsonObject(value) ? value : {});

const normalizeStringArray = (value: JsonValue | undefined, limit: number): string[] => {
    if (!isArray(value)) {
        return [];
    }
    const results: string[] = [];
    for (const entry of value) {
        if (!isString(entry)) {
            continue;
        }
        const trimmed = entry.trim();
        if (!trimmed) {
            continue;
        }
        results.push(trimmed);
        if (results.length >= limit) {
            break;
        }
    }
    return results;
};

const normalizeNonBlankStringOrNull = (value: JsonValue | undefined): string | null => {
    if (!isString(value)) {
        return null;
    }
    return value.trim() ? value : null;
};

export { normalizeNonBlankStringOrNull, normalizeSessionData, normalizeStringArray };
