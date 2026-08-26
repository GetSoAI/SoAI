/* SoAI - Shared UI badge colors [frontend/assets/ts/core/ui/badgeColors.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedLower } from '@core/normalize.ts';
import { computeHash } from '@core/primitives/hash.ts';
const BADGE_COLOR_CLASSES: readonly string[] = Object.freeze(['ui-model-type-badge--theme-0', 'ui-model-type-badge--theme-1', 'ui-model-type-badge--theme-2', 'ui-model-type-badge--theme-3', 'ui-model-type-badge--theme-4', 'ui-model-type-badge--theme-5', 'ui-model-type-badge--theme-6', 'ui-model-type-badge--theme-7', 'ui-model-type-badge--theme-8', 'ui-model-type-badge--theme-9', 'ui-model-type-badge--theme-10', 'ui-model-type-badge--theme-11', 'ui-model-type-badge--theme-12', 'ui-model-type-badge--theme-13', 'ui-model-type-badge--theme-14', 'ui-model-type-badge--theme-15', 'ui-model-type-badge--theme-16', 'ui-model-type-badge--theme-17', 'ui-model-type-badge--theme-18', 'ui-model-type-badge--theme-19', 'ui-model-type-badge--theme-20', 'ui-model-type-badge--theme-21', 'ui-model-type-badge--theme-22', 'ui-model-type-badge--theme-23']);

const getBadgeColorClass = (value: string | null | undefined): string => {
    const fallback = BADGE_COLOR_CLASSES[0];
    if (!fallback) {
        throw new Error('Badge color palette is empty');
    }
    const normalized = toTrimmedLower(value);
    if (!normalized) {
        return fallback;
    }
    const hash = computeHash(normalized);
    const paletteIndex = hash % BADGE_COLOR_CLASSES.length;
    return BADGE_COLOR_CLASSES[paletteIndex] ?? fallback;
};

export { getBadgeColorClass };
