/* SoAI - Shared primitives collection grouping keys [frontend/assets/ts/core/primitives/grouping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';

const ALPHABETIC_GROUP_FALLBACK_KEY = '#';

const resolveAlphabeticGroupKey = (name: string | null | undefined): string => {
    const trimmed = isString(name) ? name.trim() : '';
    if (!trimmed) {
        return ALPHABETIC_GROUP_FALLBACK_KEY;
    }
    const first = trimmed.charAt(0).toUpperCase();
    return /^[A-Z]$/.test(first) ? first : ALPHABETIC_GROUP_FALLBACK_KEY;
};

export { ALPHABETIC_GROUP_FALLBACK_KEY, resolveAlphabeticGroupKey };
