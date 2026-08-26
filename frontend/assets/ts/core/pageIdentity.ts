/* SoAI - Shared frontend page identity [frontend/assets/ts/core/pageIdentity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isNullOrUndefined, isString } from '@core/typeGuards.ts';

const INVALID_IDENTIFIER_PATTERN = /^\[object Object]$/;

const normalizePageIdentifier = (candidate: string | null | undefined, fallback: string | null | undefined = null): string => {
    const primary = isString(candidate) ? candidate : null;
    const fallbackValue = isString(fallback) ? fallback : null;
    const ordered = [primary, fallbackValue].filter((value) => !isNullOrUndefined(value));
    for (const value of ordered) {
        const trimmed = value.trim();
        if (trimmed && !INVALID_IDENTIFIER_PATTERN.test(trimmed)) {
            return trimmed;
        }
    }
    throw new Error('Page identifier must be a non-empty string');
};

export { normalizePageIdentifier };
