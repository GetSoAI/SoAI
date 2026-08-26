/* SoAI - Shared frontend syntax highlighter languages diff [frontend/assets/ts/core/syntaxhighlighter/languages/diff.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { LanguageDefinition } from '@core/syntaxhighlighter/types.ts';

const scoreDiff = (text: string): number => {
    let score = 0;
    const hasDiffHeader = /^diff\s/m.test(text);
    const hasHunkRange = /^@@\s.*\s@@/m.test(text);
    const hasInsertedLine = /^\+[^+]/m.test(text);
    const hasDeletedLine = /^-[^-]/m.test(text);
    const hasFileHeader = /^(?:---|\+\+\+)\s/m.test(text);

    if (!hasDiffHeader && !hasHunkRange && !hasFileHeader && !(hasInsertedLine && hasDeletedLine)) {
        return 0;
    }

    if (hasDiffHeader) {
        score += 35;
    }
    if (hasHunkRange) {
        score += 30;
    }
    if (hasInsertedLine) {
        score += 15;
    }
    if (hasDeletedLine) {
        score += 15;
    }
    if (hasFileHeader) {
        score += 20;
    }
    return score;
};

const DIFF_LANGUAGE_DEFINITION: LanguageDefinition = {
    id: 'diff',
    label: '',
    aliases: ['patch', 'unified'],
    score: (text: string): number => scoreDiff(text),
    grammar: [
        { type: 'diff.meta', regex: /^(?:diff|index|---|\+\+\+).*$/gm, priority: 10 },
        { type: 'diff.range', regex: /^@@\s.*\s@@.*$/gm, priority: 9 },
        { type: 'diff.viewed', regex: /^>.*$/gm, priority: 8 },
        { type: 'diff.inserted', regex: /^\+.*$/gm, priority: 8 },
        { type: 'diff.deleted', regex: /^-.*$/gm, priority: 8 }
    ]
};

export { DIFF_LANGUAGE_DEFINITION };
