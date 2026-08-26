/* SoAI - ANSI SGR segment parsing [frontend/assets/ts/core/ansi/sgrSegments.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFiniteNumber } from '@core/typeGuards.ts';

const ESCAPE = String.fromCharCode(27);
const CSI_PATTERN = new RegExp(`${ESCAPE}\\[([0-9;]*)([A-Za-z])`, 'g');
const ESCAPED_ESCAPE_PATTERN = /\\(?:x1[bB]|u001[bB]|033|e)/g;
const SGR_FINAL_BYTE = 'm';

const NAMED_FOREGROUND_CODES: ReadonlySet<number> = new Set<number>([30, 31, 32, 33, 34, 35, 36, 37, 90, 91, 92, 93, 94, 95, 96, 97]);

interface AnsiNamedColor {
    type: 'named';
    code: number;
}

interface AnsiPaletteColor {
    type: 'palette';
    index: number;
}

interface AnsiRgbColor {
    type: 'rgb';
    r: number;
    g: number;
    b: number;
}

type AnsiColor = AnsiNamedColor | AnsiPaletteColor | AnsiRgbColor;

interface AnsiSegment {
    text: string;
    color: AnsiColor | null;
    bold: boolean;
}

interface AnsiState {
    color: AnsiColor | null;
    bold: boolean;
}

const normalizeAnsiControlSequences = (text: string): string => {
    if (!text.includes('\\')) {
        return text;
    }
    return text.replace(ESCAPED_ESCAPE_PATTERN, ESCAPE);
};

const formatControlCodePoint = (codePoint: number): string | null => {
    if (codePoint === 9 || codePoint === 10) {
        return null;
    }
    if (codePoint === 13) {
        return '\\r';
    }
    if (codePoint < 32 || codePoint === 127 || (codePoint >= 128 && codePoint <= 159)) {
        return `\\x${codePoint.toString(16).padStart(2, '0')}`;
    }
    return null;
};

const formatTerminalControlCharacters = (text: string): string => {
    const normalizedLineEndings = text.replace(/\r\n/g, '\n');
    let formatted = '';
    for (const character of normalizedLineEndings) {
        const codePoint = character.codePointAt(0);
        if (codePoint === undefined) {
            continue;
        }
        formatted += formatControlCodePoint(codePoint) ?? character;
    }
    return formatted;
};

const containsAnsi = (text: string): boolean => normalizeAnsiControlSequences(text).includes(`${ESCAPE}[`);

const parseSgrCodes = (raw: string): number[] => {
    if (raw === '') {
        return [0];
    }
    const codes: number[] = [];
    for (const part of raw.split(';')) {
        const value = Number.parseInt(part, 10);
        if (isFiniteNumber(value)) {
            codes.push(value);
        }
    }
    return codes;
};

const applyExtendedColor = (codes: number[], index: number): { color: AnsiColor | null; consumed: number } => {
    const mode = codes[index + 1];
    if (mode === 5) {
        const paletteIndex = codes[index + 2];
        if (isFiniteNumber(paletteIndex)) {
            return { color: { type: 'palette', index: paletteIndex }, consumed: 2 };
        }
        return { color: null, consumed: 2 };
    }
    if (mode === 2) {
        const redChannel = codes[index + 2];
        const greenChannel = codes[index + 3];
        const blueChannel = codes[index + 4];
        if (isFiniteNumber(redChannel) && isFiniteNumber(greenChannel) && isFiniteNumber(blueChannel)) {
            return { color: { type: 'rgb', r: redChannel, g: greenChannel, b: blueChannel }, consumed: 4 };
        }
        return { color: null, consumed: 4 };
    }
    return { color: null, consumed: 0 };
};

const applySgrCodes = (state: AnsiState, codes: number[]): AnsiState => {
    let color: AnsiColor | null = state.color;
    let bold = state.bold;
    for (let index = 0; index < codes.length; index += 1) {
        const code = codes[index];
        if (code === undefined) {
            continue;
        }
        if (code === 0) {
            color = null;
            bold = false;
            continue;
        }
        if (code === 1) {
            bold = true;
            continue;
        }
        if (code === 22) {
            bold = false;
            continue;
        }
        if (code === 39) {
            color = null;
            continue;
        }
        if (code === 38) {
            const extended = applyExtendedColor(codes, index);
            if (extended.consumed > 0) {
                color = extended.color;
            }
            index += extended.consumed;
            continue;
        }
        if (NAMED_FOREGROUND_CODES.has(code)) {
            color = { type: 'named', code };
        }
    }
    return { color, bold };
};

const parseAnsiSegments = (text: string): AnsiSegment[] => {
    const normalizedText = normalizeAnsiControlSequences(text);
    const segments: AnsiSegment[] = [];
    let state: AnsiState = { color: null, bold: false };
    let lastIndex = 0;
    CSI_PATTERN.lastIndex = 0;
    let match = CSI_PATTERN.exec(normalizedText);
    while (match) {
        if (match.index > lastIndex) {
            segments.push({ text: normalizedText.slice(lastIndex, match.index), color: state.color, bold: state.bold });
        }
        if (match[2] === SGR_FINAL_BYTE) {
            state = applySgrCodes(state, parseSgrCodes(match[1] ?? ''));
        }
        lastIndex = CSI_PATTERN.lastIndex;
        match = CSI_PATTERN.exec(normalizedText);
    }
    if (lastIndex < normalizedText.length) {
        segments.push({ text: normalizedText.slice(lastIndex), color: state.color, bold: state.bold });
    }
    return segments;
};

export { containsAnsi, formatTerminalControlCharacters, parseAnsiSegments };
export type { AnsiColor, AnsiSegment };
