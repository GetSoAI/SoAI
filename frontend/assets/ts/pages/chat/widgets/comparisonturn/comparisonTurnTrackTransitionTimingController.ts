/* SoAI - Track transition timing helpers for comparison-turn carousels [frontend/assets/ts/pages/chat/widgets/comparisonturn/comparisonTurnTrackTransitionTimingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';

const trackTransitionTargetsTransform = (property: string): boolean => {
    const normalizedProperty = property.trim();
    if (!normalizedProperty) {
        return false;
    }
    const properties = normalizedProperty.split(',').map((item) => item.trim());
    for (const token of properties) {
        if (token === 'all' || token === 'transform') {
            return true;
        }
    }
    return false;
};

const resolveTrackTransformTransitionTotalMs = (track: HTMLElement): number => {
    const style = getComputedStyle(track);
    if (!trackTransitionTargetsTransform(style.transitionProperty)) return 0;
    const durationMs = parseMaxCssDurationMs(style.transitionDuration);
    const delayMs = parseMaxCssDurationMs(style.transitionDelay);
    return Math.max(0, durationMs + delayMs);
};

export { resolveTrackTransformTransitionTotalMs };
