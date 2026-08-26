/* SoAI - Shared frontend syntax highlighter scoring mapping [frontend/assets/ts/core/syntaxhighlighter/scoring/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { safeCloneRegex } from '@core/syntaxhighlighter/regex.ts';

const DETECTION_BASE_THRESHOLD = 14;

const countMatches = (regex: RegExp, content: string, limit: number = 100): number => {
    if (!regex || !content) {
        return 0;
    }
    const pattern = safeCloneRegex(regex);
    let count = 0;
    let match: RegExpExecArray | null;
    while ((match = pattern.exec(content)) !== null) {
        count++;
        if (count >= limit) {
            break;
        }
        if (pattern.lastIndex === match.index) {
            pattern.lastIndex++;
        }
    }
    return count;
};

const dynamicThreshold = (length: number): number => {
    if (!Number.isFinite(length) || length <= 0) {
        return 4;
    }
    if (length < 60) {
        return 4;
    }
    if (length < 160) {
        return 8;
    }
    if (length < 400) {
        return 12;
    }
    return DETECTION_BASE_THRESHOLD;
};

export { countMatches, dynamicThreshold };
