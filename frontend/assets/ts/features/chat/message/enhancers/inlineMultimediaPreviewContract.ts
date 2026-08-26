/* SoAI - Canonical assistant-authored WebUI preview contract helpers [frontend/assets/ts/features/chat/message/enhancers/inlineMultimediaPreviewContract.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { PREVIEW_REFERENCE_TYPES, isContentPreviewReferenceType } from '@features/chat/preview/previewReferenceContract.ts';
import type { ContentPreviewReferenceType } from '@features/chat/contentPreviewContracts.ts';

const PREVIEW_REFERENCE_START = '[[preview:';
const PREVIEW_REFERENCE_TOKEN_PATTERN_SOURCE = String.raw`\[\[preview:(absolute_path|virtual_path|remote_url):([^\]|]+)(?:\|([^\]]+))?\]\]`;

type PreviewReferenceType = ContentPreviewReferenceType;

interface PreviewReferenceToken {
    type: PreviewReferenceType;
    target: string;
    label: string | null;
    raw: string;
}

interface PreviewReferenceDraft {
    target: string;
    label: string | null;
    raw: string;
}

const PREVIEW_REFERENCE_PATTERN = new RegExp(PREVIEW_REFERENCE_TOKEN_PATTERN_SOURCE, 'g');
const INDENTED_PREVIEW_REFERENCE_LINE_PATTERN = new RegExp(`^([ \\t]{4,})(${PREVIEW_REFERENCE_TOKEN_PATTERN_SOURCE})([ \\t]*)$`);

const isPreviewReferenceType = (value: string): value is PreviewReferenceType => isContentPreviewReferenceType(value);

const buildPreviewReferenceToken = (inputArguments: { type: PreviewReferenceType; target: string; label?: string | null }): string => {
    const target = toTrimmedString(inputArguments.target);
    if (!target) {
        throw new Error('Preview reference target must be non-empty');
    }
    const label = toTrimmedString(inputArguments.label ?? '');
    if (label) {
        return `[[preview:${inputArguments.type}:${target}|${label}]]`;
    }
    return `[[preview:${inputArguments.type}:${target}]]`;
};

const parsePreviewReferenceTokenMatch = (match: RegExpMatchArray): PreviewReferenceToken | null => {
    const type = toTrimmedString(match[1] ?? '');
    const target = toTrimmedString(match[2] ?? '');
    if (!isPreviewReferenceType(type) || !target) {
        return null;
    }
    const label = toTrimmedString(match[3] ?? '');
    return {
        type,
        target,
        label: label ? label : null,
        raw: String(match[0] ?? '')
    };
};

const parseTrailingPreviewReferenceDraft = (value: string): PreviewReferenceDraft | null => {
    const startIndex = value.lastIndexOf(PREVIEW_REFERENCE_START);
    if (startIndex < 0) {
        return null;
    }
    const raw = value.slice(startIndex);
    if (!raw || raw.includes(']]') || raw.includes('\n')) {
        return null;
    }
    const body = raw.slice(PREVIEW_REFERENCE_START.length);
    const firstColon = body.indexOf(':');
    if (firstColon < 0) {
        return {
            target: '',
            label: null,
            raw
        };
    }
    const remainder = body.slice(firstColon + 1);
    const pipeIndex = remainder.indexOf('|');
    const target = toTrimmedString(pipeIndex >= 0 ? remainder.slice(0, pipeIndex) : remainder);
    const label = pipeIndex >= 0 ? toTrimmedString(remainder.slice(pipeIndex + 1)) : '';
    return {
        target,
        label: label ? label : null,
        raw
    };
};

const stripPreviewReferenceTokensForClipboard = (value: string): string => {
    if (!value.includes(PREVIEW_REFERENCE_START)) {
        return value;
    }
    PREVIEW_REFERENCE_PATTERN.lastIndex = 0;
    let result = '';
    let lastIndex = 0;
    for (const match of value.matchAll(PREVIEW_REFERENCE_PATTERN)) {
        const raw = String(match[0] ?? '');
        const matchIndex = match.index;
        if (matchIndex === undefined || !raw) {
            continue;
        }
        const token = parsePreviewReferenceTokenMatch(match);
        if (token === null) {
            continue;
        }
        result += value.slice(lastIndex, matchIndex);
        result += token.target;
        lastIndex = matchIndex + raw.length;
    }
    if (lastIndex <= 0) {
        return value;
    }
    PREVIEW_REFERENCE_PATTERN.lastIndex = 0;
    return `${result}${value.slice(lastIndex)}`;
};

const stripPreviewReferenceTokensForPlainText = (value: string): string => {
    const stripped = stripPreviewReferenceTokensForClipboard(value);
    const trailingDraft = parseTrailingPreviewReferenceDraft(stripped);
    if (trailingDraft === null) {
        return stripped;
    }
    const startIndex = stripped.lastIndexOf(trailingDraft.raw);
    if (startIndex < 0) {
        return stripped;
    }
    return `${stripped.slice(0, startIndex)}${trailingDraft.target}${stripped.slice(startIndex + trailingDraft.raw.length)}`;
};

const normalizeIndentedPreviewReferenceTokenLines = (content: string, options: { isCodeFenceLine: (line: string) => boolean }): string => {
    const lines = content.split('\n');
    let isInsideFencedCodeBlock = false;
    for (let index = 0; index < lines.length; index += 1) {
        const line = lines[index] ?? '';
        if (options.isCodeFenceLine(line)) {
            isInsideFencedCodeBlock = !isInsideFencedCodeBlock;
            continue;
        }
        if (isInsideFencedCodeBlock) {
            continue;
        }
        const match = line.match(INDENTED_PREVIEW_REFERENCE_LINE_PATTERN);
        if (!match) {
            continue;
        }
        const token = match[2] ?? '';
        const trailingWhitespace = match[6] ?? '';
        lines[index] = `${token}${trailingWhitespace}`;
    }
    return lines.join('\n');
};

export { PREVIEW_REFERENCE_PATTERN, PREVIEW_REFERENCE_START, PREVIEW_REFERENCE_TOKEN_PATTERN_SOURCE, PREVIEW_REFERENCE_TYPES, buildPreviewReferenceToken, isPreviewReferenceType, normalizeIndentedPreviewReferenceTokenLines, parsePreviewReferenceTokenMatch, parseTrailingPreviewReferenceDraft, stripPreviewReferenceTokensForClipboard, stripPreviewReferenceTokensForPlainText };
export type { PreviewReferenceDraft, PreviewReferenceToken, PreviewReferenceType };
