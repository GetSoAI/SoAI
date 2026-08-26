/* SoAI - Internal SoAI link token codec [frontend/assets/ts/core/soailinks/codec.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';

const SOAI_PATH_TOKEN_PREFIX = '[[soai:path:';
const SOAI_PATH_TOKEN_SUFFIX = ']]';

type BuildSoaiPathTokenArguments = Readonly<{
    virtualPath: string;
    label?: string | null | undefined;
}>;

type SoaiPathTokenText = Readonly<{
    token: string;
    virtualPath: string;
    label: string;
    startIndex: number;
    endIndex: number;
}>;

const requireSoaiVirtualPath = (virtualPath: string): string => {
    const normalized = toTrimmedString(virtualPath);
    if (!normalized || !normalized.startsWith('/')) {
        throw new Error('SoAI path link virtual path must be absolute');
    }
    if (normalized.includes('\u0000')) {
        throw new Error('SoAI path link virtual path must not contain NUL bytes');
    }
    return normalized;
};

const buildSoaiPathToken = ({ virtualPath, label }: BuildSoaiPathTokenArguments): string => {
    const encodedPath = encodeURIComponent(requireSoaiVirtualPath(virtualPath));
    const normalizedLabel = toTrimmedString(label ?? '');
    if (!normalizedLabel) {
        return `${SOAI_PATH_TOKEN_PREFIX}${encodedPath}${SOAI_PATH_TOKEN_SUFFIX}`;
    }
    return `${SOAI_PATH_TOKEN_PREFIX}${encodedPath}|${encodeURIComponent(normalizedLabel)}${SOAI_PATH_TOKEN_SUFFIX}`;
};

const containsSoaiPathToken = (value: string): boolean => value.includes(SOAI_PATH_TOKEN_PREFIX);

const appendedTextIntroducesSoaiPathToken = (existing: string, appended: string): boolean => {
    const overlapLength = SOAI_PATH_TOKEN_PREFIX.length - 1;
    return `${existing.slice(-overlapLength)}${appended}`.includes(SOAI_PATH_TOKEN_PREFIX);
};

const decodeTokenComponent = (value: string): string => {
    try {
        return decodeURIComponent(value);
    } catch {
        throw new Error('SoAI path link token contains invalid encoding');
    }
};

const basenameFromVirtualPath = (virtualPath: string): string => {
    const parts = virtualPath.split('/').filter((part) => part.length > 0);
    const lastPart = parts[parts.length - 1];
    return lastPart === undefined ? virtualPath : lastPart;
};

const extractSoaiPathTokenTexts = (value: string): SoaiPathTokenText[] => {
    const tokens: SoaiPathTokenText[] = [];
    let cursor = 0;
    while (cursor < value.length) {
        const startIndex = value.indexOf(SOAI_PATH_TOKEN_PREFIX, cursor);
        if (startIndex < 0) {
            break;
        }
        const endIndex = value.indexOf(SOAI_PATH_TOKEN_SUFFIX, startIndex + SOAI_PATH_TOKEN_PREFIX.length);
        if (endIndex < 0) {
            break;
        }
        const token = value.slice(startIndex, endIndex + SOAI_PATH_TOKEN_SUFFIX.length);
        const body = token.slice(SOAI_PATH_TOKEN_PREFIX.length, -SOAI_PATH_TOKEN_SUFFIX.length);
        const separatorIndex = body.indexOf('|');
        const encodedPath = separatorIndex < 0 ? body : body.slice(0, separatorIndex);
        const encodedLabel = separatorIndex < 0 ? '' : body.slice(separatorIndex + 1);
        const virtualPath = decodeTokenComponent(encodedPath);
        const label = encodedLabel ? decodeTokenComponent(encodedLabel) : basenameFromVirtualPath(virtualPath);
        const displayLabel = (label.trim() || virtualPath).replace(/\s+/g, ' ').trim();
        tokens.push({ token, virtualPath, label: displayLabel || virtualPath, startIndex, endIndex: endIndex + SOAI_PATH_TOKEN_SUFFIX.length });
        cursor = endIndex + SOAI_PATH_TOKEN_SUFFIX.length;
    }
    return tokens;
};

const replaceSoaiPathTokensWithLabels = (value: string): string => {
    if (!containsSoaiPathToken(value)) {
        return value;
    }
    const tokens = extractSoaiPathTokenTexts(value);
    if (tokens.length === 0) {
        return value;
    }
    const parts: string[] = [];
    let cursor = 0;
    for (const token of tokens) {
        parts.push(value.slice(cursor, token.startIndex));
        parts.push(token.label);
        cursor = token.endIndex;
    }
    parts.push(value.slice(cursor));
    return parts.join('');
};

const stripSoaiPathTokensForDisplay = (value: string): string => {
    if (!containsSoaiPathToken(value)) {
        return value;
    }
    const tokens = extractSoaiPathTokenTexts(value);
    if (tokens.length === 0) {
        return value;
    }
    const parts: string[] = [];
    let cursor = 0;
    for (const token of tokens) {
        parts.push(value.slice(cursor, token.startIndex));
        cursor = token.endIndex;
    }
    parts.push(value.slice(cursor));
    return parts.join('');
};

export { appendedTextIntroducesSoaiPathToken, buildSoaiPathToken, containsSoaiPathToken, extractSoaiPathTokenTexts, replaceSoaiPathTokensWithLabels, stripSoaiPathTokensForDisplay };
export type { SoaiPathTokenText };
