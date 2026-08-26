/* SoAI - Shared security URL sanitizer [frontend/assets/ts/core/security/urlSanitizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { stripControlCharacters, sanitizeText } from '@core/security/textSanitizer.ts';

let urlParseFailuresLogged = 0;

const EXPLICIT_SCHEME_PATTERN = /^[a-z][a-z0-9+.-]*:/i;
const HOST_PORT_PREFIX_PATTERN = /^[^/?#\s:]+:\d+(?:[/?#]|$)/;

const ensureDataPrefix = (data: string): string | null => {
    if (!data) {
        return null;
    }
    if (data.toLowerCase().startsWith('data:image/')) {
        return data;
    }
    return null;
};

interface SanitizeUrlOptions {
    allowDataImage?: boolean;
    allowBlob?: boolean;
    allowRelative?: boolean;
}

const sanitizeUrl = <T>(input: T, options: SanitizeUrlOptions = {}): string | null => {
    if (typeof input !== 'string') {
        return null;
    }
    const trimmed = sanitizeText(input);
    if (!trimmed) {
        return null;
    }
    const lower = trimmed.toLowerCase();
    if (trimmed.includes('\\')) {
        return null;
    }
    if (lower.startsWith('javascript:')) {
        return null;
    }
    if (lower.startsWith('vbscript:')) {
        return null;
    }
    if (lower.startsWith('file:')) {
        return null;
    }
    if (lower.startsWith('data:')) {
        if (options.allowDataImage !== true) {
            return null;
        }
        return ensureDataPrefix(trimmed);
    }
    if (lower.startsWith('blob:')) {
        if (options.allowBlob === false) {
            return null;
        }
        return trimmed;
    }
    if (trimmed.startsWith('//')) {
        const currentProtocol = globalThis.location?.protocol;
        const protocol = currentProtocol === 'http:' || currentProtocol === 'https:' ? currentProtocol : 'https:';
        return `${protocol}${trimmed}`;
    }
    const allowRelative = options.allowRelative !== false;
    if (allowRelative) {
        if (/^\/(?!\/)/.test(trimmed)) {
            return trimmed;
        }
        if (trimmed.startsWith('./') || trimmed.startsWith('../')) {
            return trimmed;
        }
        if (!trimmed.includes(':')) {
            return trimmed;
        }
    }
    try {
        const url = new URL(trimmed);
        if (url.protocol !== 'https:' && url.protocol !== 'http:') {
            return null;
        }
        return stripControlCharacters(url.href);
    } catch (error) {
        if (urlParseFailuresLogged < 3) {
            urlParseFailuresLogged += 1;
            errorHandler.debug('Security', 'sanitizeUrl failed to parse URL', { input: trimmed, error: ensureError(error) });
        }
        return null;
    }
};

const sanitizeImageSource = <T>(input: T): string | null => sanitizeUrl(input, { allowRelative: true, allowDataImage: true, allowBlob: true });

const sanitizeAbsoluteHttpUrl = <T>(input: T): string | null => {
    if (!isAbsoluteHttpUrl(input)) {
        return null;
    }
    return resolveHttpUrl(input);
};

const isAbsoluteHttpUrl = <T>(input: T): input is T & string => {
    if (typeof input !== 'string') return false;
    const sanitized = sanitizeText(input);
    return !sanitized.includes('\\') && /^https?:\/\//i.test(sanitized);
};

const requireHttpsResolvedUrl = (url: string | null): string | null => (url !== null && url.startsWith('https://') ? url : null);

const resolveHttpUrl = <T>(input: T, baseUrl?: string): string | null => {
    if (typeof input !== 'string') {
        return null;
    }
    const trimmed = sanitizeText(input);
    if (!trimmed || trimmed.includes('\\')) {
        return null;
    }
    try {
        const resolved = baseUrl ? new URL(trimmed, baseUrl) : new URL(trimmed);
        if (resolved.protocol !== 'http:' && resolved.protocol !== 'https:') {
            return null;
        }
        return stripControlCharacters(resolved.href);
    } catch (error) {
        if (urlParseFailuresLogged < 3) {
            urlParseFailuresLogged += 1;
            errorHandler.debug('Security', 'resolveHttpUrl failed to parse URL', { input: trimmed, error: ensureError(error) });
        }
        return null;
    }
};

const resolveHttpsWebsiteUrl = <T>(input: T): string | null => {
    if (typeof input !== 'string') {
        return null;
    }
    const trimmed = sanitizeText(input);
    if (!trimmed) {
        return null;
    }
    if (trimmed.startsWith('//')) {
        return requireHttpsResolvedUrl(resolveHttpUrl(`https:${trimmed}`));
    }
    if (trimmed.includes(':') && EXPLICIT_SCHEME_PATTERN.test(trimmed) && !HOST_PORT_PREFIX_PATTERN.test(trimmed)) {
        return requireHttpsResolvedUrl(resolveHttpUrl(trimmed));
    }
    return requireHttpsResolvedUrl(resolveHttpUrl(`https://${trimmed}`));
};

export { isAbsoluteHttpUrl, resolveHttpUrl, resolveHttpsWebsiteUrl, sanitizeUrl, sanitizeImageSource, sanitizeAbsoluteHttpUrl };
export type { SanitizeUrlOptions };
