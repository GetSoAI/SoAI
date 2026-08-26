/* SoAI - Shared primitives text [frontend/assets/ts/core/primitives/text.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';

export const MIDDLE_ELLIPSIS = '...';
export const MIDDLE_ELLIPSIS_MIN_SIDE_LENGTH = 5;

export const isUnicodeScalarText = (value: string): boolean => {
    for (let index = 0; index < value.length; index += 1) {
        const codeUnit = value.charCodeAt(index);
        if (codeUnit >= 0xd800 && codeUnit <= 0xdbff) {
            const nextCodeUnit = value.charCodeAt(index + 1);
            if (!(nextCodeUnit >= 0xdc00 && nextCodeUnit <= 0xdfff)) {
                return false;
            }
            index += 1;
        } else if (codeUnit >= 0xdc00 && codeUnit <= 0xdfff) {
            return false;
        }
    }
    return true;
};

const isPythonWhitespace = (character: string): boolean => {
    const codePoint = character.codePointAt(0);
    return codePoint !== undefined && ((codePoint >= 0x0009 && codePoint <= 0x000d) || (codePoint >= 0x001c && codePoint <= 0x0020) || codePoint === 0x0085 || codePoint === 0x00a0 || codePoint === 0x1680 || (codePoint >= 0x2000 && codePoint <= 0x200a) || codePoint === 0x2028 || codePoint === 0x2029 || codePoint === 0x202f || codePoint === 0x205f || codePoint === 0x3000);
};

export const trimPythonWhitespace = (value: string): string => {
    const characters = Array.from(value);
    let start = 0;
    let end = characters.length;
    while (start < end && isPythonWhitespace(characters[start] ?? '')) start += 1;
    while (end > start && isPythonWhitespace(characters[end - 1] ?? '')) end -= 1;
    return characters.slice(start, end).join('');
};

export type MiddleEllipsisSegments = {
    full: string;
    leading: string;
    trailing: string;
    truncated: boolean;
};

export const splitMiddleEllipsisText = (value: string, maxLength: number): MiddleEllipsisSegments => {
    const full = toTrimmedString(value);
    const characters = Array.from(full);
    const budget = Math.max(maxLength - MIDDLE_ELLIPSIS.length, MIDDLE_ELLIPSIS_MIN_SIDE_LENGTH * 2);
    const leadingCount = Math.max(MIDDLE_ELLIPSIS_MIN_SIDE_LENGTH, Math.ceil(budget / 2));
    const trailingCount = Math.max(MIDDLE_ELLIPSIS_MIN_SIDE_LENGTH, budget - leadingCount);
    if (characters.length <= maxLength || leadingCount + trailingCount >= characters.length) {
        return { full, leading: full, trailing: '', truncated: false };
    }
    return {
        full,
        leading: characters.slice(0, leadingCount).join(''),
        trailing: characters.slice(-trailingCount).join(''),
        truncated: true
    };
};

export const middleEllipsisText = (value: string, maxLength: number): string => {
    const segments = splitMiddleEllipsisText(value, maxLength);
    return segments.truncated ? `${segments.leading}${MIDDLE_ELLIPSIS}${segments.trailing}` : segments.full;
};

export const capitalize = (str: string): string => (str ? str.charAt(0).toUpperCase() + str.slice(1) : '');

const isAllUppercaseSegment = (segment: string): boolean => /^[A-Z0-9]+$/.test(segment);

export const formatTitleFromId = (value: string | null | undefined): string => {
    const source = toTrimmedString(value);
    if (!source) return '';
    return source
        .split(/[\s_-]+/)
        .filter(Boolean)
        .map((segment) => (isAllUppercaseSegment(segment) ? segment : capitalize(segment.toLowerCase())))
        .join(' ');
};

export const formatSentenceLabelFromId = (value: string | null | undefined): string => {
    if (!isString(value) || !value) {
        return '';
    }
    return value
        .replace(/_/g, ' ')
        .split(' ')
        .map((word: string, index: number): string => {
            if (!word) {
                return word;
            }
            const lower = word.toLowerCase();
            return index === 0 ? lower.charAt(0).toUpperCase() + lower.slice(1) : lower;
        })
        .join(' ');
};

export const replaceUnderscoresWithSpaces = (value: string): string => value.replace(/_/g, ' ');

export const formatCapitalizedUnderscoreLabel = (value: string): string => {
    const normalized = replaceUnderscoresWithSpaces(value).trim();
    if (!normalized) {
        return '';
    }
    return `${normalized.charAt(0).toUpperCase()}${normalized.slice(1)}`;
};

export const formatUppercaseUnderscoreLabel = (value: string): string => replaceUnderscoresWithSpaces(value).toUpperCase().trim();
