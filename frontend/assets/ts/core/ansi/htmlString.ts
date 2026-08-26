/* SoAI - ANSI segment HTML rendering [frontend/assets/ts/core/ansi/htmlString.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { formatTerminalControlCharacters, parseAnsiSegments, type AnsiColor, type AnsiSegment } from '@core/ansi/sgrSegments.ts';
import { escapeHtml } from '@core/security/textSanitizer.ts';

const PALETTE_COLOR_CLASSES: ReadonlyMap<number, string> = new Map<number, string>([
    [208, 'inline-ansi-fg-208'],
    [215, 'inline-ansi-fg-215'],
    [246, 'inline-ansi-fg-246']
]);

const BOLD_CLASS = 'inline-ansi-bold';

const resolveColorClass = (color: AnsiColor): string | null => {
    if (color.type === 'named') {
        return `inline-ansi-fg-${String(color.code)}`;
    }
    if (color.type === 'palette') {
        return PALETTE_COLOR_CLASSES.get(color.index) ?? null;
    }
    return null;
};

const resolveSegmentClasses = (segment: AnsiSegment): string[] => {
    const classes: string[] = [];
    if (segment.color !== null) {
        const colorClass = resolveColorClass(segment.color);
        if (colorClass !== null) {
            classes.push(colorClass);
        }
    }
    if (segment.bold) {
        classes.push(BOLD_CLASS);
    }
    return classes;
};

const renderSegment = (segment: AnsiSegment): string => {
    const escaped = escapeHtml(formatTerminalControlCharacters(segment.text));
    const classes = resolveSegmentClasses(segment);
    if (classes.length === 0) {
        return escaped;
    }
    return `<span class="${classes.join(' ')}">${escaped}</span>`;
};

const ansiToHtmlString = (text: string): string => {
    const parts: string[] = [];
    for (const segment of parseAnsiSegments(text)) {
        if (segment.text === '') {
            continue;
        }
        parts.push(renderSegment(segment));
    }
    return parts.join('');
};

export { ansiToHtmlString };
