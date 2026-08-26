/* SoAI - Chat feature inline activity text [frontend/assets/ts/features/chat/message/messageview/inlineActivityText.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';

const THINKING_PREVIEW_ATTRIBUTE_NAMES = Object.freeze({
    root: 'data-thinking-preview',
    status: 'data-thinking-preview-status',
    visible: 'data-thinking-preview-visible',
    latest: 'data-thinking-preview-latest'
});

const THINKING_SENTENCE_TERMINATORS = new Set(['.', '!', '?', '…', '。', '！', '？']);
const THINKING_SENTENCE_CLOSERS = new Set(['"', "'", ')', ']', '}', '”', '’']);
const THINKING_NUMBERED_POINT_MAX_DIGITS = 3;
const THINKING_NUMBERED_POINT_CONTEXT_CHARACTERS = new Set([':', ',', ';', '(', '[', '{']);
const THINKING_NUMBERED_POINT_SEPARATOR_CHARACTERS = new Set([',', ';', ':']);

const clampInlineLabel = (value: string, maxLength: number): string => {
    if (value.length <= maxLength) {
        return value;
    }
    return `${value.slice(0, Math.max(0, maxLength - 3))}...`;
};

const normalizeThinkingPreviewText = (text: string): string => {
    const normalized = text.replace(/\r\n/g, '\n').trim();
    if (!normalized) {
        return '';
    }
    return normalized.replace(/\s+/g, ' ').trim();
};

const resolveThinkingWordPreview = (text: string, maxWords: number): string => {
    const normalized = normalizeThinkingPreviewText(text);
    if (!normalized) {
        return '';
    }
    const resolvedMaxWords = Math.max(0, Math.floor(maxWords));
    if (resolvedMaxWords <= 0) {
        return '';
    }
    const words = normalized.split(' ');
    if (words.length <= resolvedMaxWords) {
        return normalized;
    }
    return words.slice(0, resolvedMaxWords).join(' ');
};

const isAsciiDigit = (character: string): boolean => character >= '0' && character <= '9';

const isAsciiAlphanumeric = (character: string): boolean => isAsciiDigit(character) || (character >= 'A' && character <= 'Z') || (character >= 'a' && character <= 'z');

const isWhitespace = (character: string | undefined): boolean => character !== undefined && /\s/.test(character);

const resolvePreviousVisibleIndex = (text: string, startIndex: number): number | null => {
    let cursor = startIndex - 1;
    while (cursor >= 0) {
        const character = text[cursor];
        if (character !== undefined && !isWhitespace(character)) {
            return cursor;
        }
        cursor -= 1;
    }
    return null;
};

const resolveNumberedPointStart = (text: string, dotIndex: number, sentenceStart: number): number | null => {
    let digitStart = dotIndex;
    let digitCount = 0;
    while (digitStart > 0) {
        const character = text[digitStart - 1];
        if (character === undefined || !isAsciiDigit(character)) {
            break;
        }
        if (digitCount >= THINKING_NUMBERED_POINT_MAX_DIGITS) {
            return null;
        }
        digitStart -= 1;
        digitCount += 1;
    }
    if (digitCount === 0) {
        return null;
    }
    const previousCharacter = digitStart > 0 ? text[digitStart - 1] : undefined;
    if (previousCharacter !== undefined && isAsciiAlphanumeric(previousCharacter)) {
        return null;
    }
    const previousVisibleIndex = resolvePreviousVisibleIndex(text, digitStart);
    if (previousVisibleIndex === null || previousVisibleIndex < sentenceStart) {
        return digitStart;
    }
    const previousVisibleCharacter = text[previousVisibleIndex];
    if (previousVisibleCharacter !== undefined && THINKING_NUMBERED_POINT_CONTEXT_CHARACTERS.has(previousVisibleCharacter)) {
        return digitStart;
    }
    return null;
};

const hasNumberedPointContinuation = (text: string, dotIndex: number): boolean => {
    let cursor = dotIndex + 1;
    while (cursor < text.length) {
        const character = text[cursor];
        if (character !== undefined && !isWhitespace(character)) {
            return true;
        }
        cursor += 1;
    }
    return false;
};

const trimNumberedPointSeparator = (text: string, markerStart: number, sentenceStart: number): number => {
    let cursor = markerStart;
    while (cursor > sentenceStart && isWhitespace(text[cursor - 1])) {
        cursor -= 1;
    }
    if (cursor > sentenceStart && THINKING_NUMBERED_POINT_SEPARATOR_CHARACTERS.has(text[cursor - 1] ?? '')) {
        cursor -= 1;
    }
    while (cursor > sentenceStart && isWhitespace(text[cursor - 1])) {
        cursor -= 1;
    }
    return cursor;
};

const resolveThinkingSentences = (text: string): string[] => {
    const normalized = text.replace(/\r\n/g, '\n').trim();
    if (!normalized) {
        return [];
    }

    const sentences: string[] = [];
    let sentenceStart = 0;
    let consumedNumberedPoint = false;

    for (let index = 0; index < normalized.length; index += 1) {
        const character = normalized[index];
        if (character === undefined) {
            continue;
        }
        const isNewlineBoundary = character === '\n';
        const isColonBoundary = character === ':' && normalized[index + 1] === '\n';
        if (!isNewlineBoundary && !isColonBoundary && !THINKING_SENTENCE_TERMINATORS.has(character)) {
            continue;
        }
        const baseSentenceEnd = isNewlineBoundary ? index : index + 1;
        let sentenceEnd = baseSentenceEnd;
        while (sentenceEnd < normalized.length) {
            const closer = normalized[sentenceEnd];
            if (closer === undefined || !THINKING_SENTENCE_CLOSERS.has(closer)) {
                break;
            }
            sentenceEnd += 1;
        }
        const nextCharacter = normalized[sentenceEnd];
        if (!isNewlineBoundary && nextCharacter !== undefined && !isWhitespace(nextCharacter)) {
            continue;
        }
        const numberedPointStart = character === '.' ? resolveNumberedPointStart(normalized, index, sentenceStart) : null;
        if (numberedPointStart !== null) {
            if (consumedNumberedPoint) {
                const sentenceEnd = trimNumberedPointSeparator(normalized, numberedPointStart, sentenceStart);
                const sentence = normalizeThinkingPreviewText(normalized.slice(sentenceStart, sentenceEnd));
                if (sentence) {
                    sentences.push(sentence);
                }
                sentenceStart = numberedPointStart;
                consumedNumberedPoint = true;
                continue;
            }
            if (hasNumberedPointContinuation(normalized, index)) {
                consumedNumberedPoint = true;
                continue;
            }
        }
        const sentence = normalizeThinkingPreviewText(normalized.slice(sentenceStart, sentenceEnd));
        if (sentence) {
            sentences.push(sentence);
        }
        sentenceStart = Math.min(normalized.length, sentenceEnd + (isNewlineBoundary ? 1 : 0));
        consumedNumberedPoint = false;
    }

    return sentences;
};

const resolveThinkingInitialPreview = (text: string): string => {
    const sentences = resolveThinkingSentences(text);
    if (sentences.length === 0) {
        return resolveThinkingWordPreview(text, 2);
    }
    const firstSentence = sentences[0];
    if (!isString(firstSentence)) {
        return '';
    }
    return firstSentence;
};

const resolveThinkingLatestCompletePreview = (text: string): string => {
    const sentences = resolveThinkingSentences(text);
    if (sentences.length === 0) {
        return resolveThinkingWordPreview(text, 40);
    }
    const latestSentence = sentences[sentences.length - 1];
    if (!isString(latestSentence)) {
        return '';
    }
    return latestSentence;
};

const stripTrailingPreviewDot = (text: string): string => {
    if (text.endsWith('.')) {
        return text.slice(0, -1);
    }
    return text;
};

const formatThinkingPreviewLabel = (preview: string): string => {
    const normalizedPreview = preview.trim();
    return stripTrailingPreviewDot(normalizedPreview);
};

export { THINKING_PREVIEW_ATTRIBUTE_NAMES, clampInlineLabel, formatThinkingPreviewLabel, resolveThinkingInitialPreview, resolveThinkingLatestCompletePreview, stripTrailingPreviewDot };
