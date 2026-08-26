/* SoAI - Shared frontend asset paths [frontend/assets/ts/core/assetPaths.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { getDocument, getGlobalScope } from '@core/environment/public.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isString } from '@core/typeGuards.ts';

const ABSOLUTE_PATTERN = /^(?:[a-z][a-z\d+\-.]*:|\/\/)/i;
const SAFE_SCHEME_PATTERN = /^https?:/i;
const INTERNAL_PREFIXES: readonly string[] = Object.freeze(['img/', 'css/', 'js/', 'lang/', 'webui/']);

const isAbsolute = (value: string): boolean => ABSOLUTE_PATTERN.test(value);
const isSafeAbsolute = (value: string): boolean => SAFE_SCHEME_PATTERN.test(value);
const isInternalPath = (value: string): boolean => INTERNAL_PREFIXES.some((prefix) => value.startsWith(prefix));
const resolveBaseUrl = (explicit?: string): string => {
    const override = toTrimmedString(explicit);
    if (override) {
        return override;
    }
    const documentRef = getDocument();
    const documentBase = toTrimmedString(documentRef?.baseURI);
    if (documentBase) {
        return documentBase;
    }
    const scope = getGlobalScope();
    const href = scope?.location?.href;
    const scopeHref = toTrimmedString(href);
    if (scopeHref) {
        return scopeHref;
    }
    return '';
};

const resolveSoaiBase = (): string => {
    const scope = getGlobalScope();
    const candidate = scope?.soaiBasePath;
    if (isString(candidate) && candidate.trim()) {
        return candidate.trim();
    }
    return '';
};

const resolveAssetBase = (explicit?: string): string => {
    const existing = resolveSoaiBase();
    if (existing) {
        return existing;
    }
    const base = resolveBaseUrl(explicit) || './';
    return new URL('./assets/', base).href;
};

interface ResolveAssetPathOptions {
    baseUrl?: string;
}

const resolveAssetPath = <T>(input: T, { baseUrl }: ResolveAssetPathOptions = {}): string => {
    if (typeof input !== 'string') {
        return '';
    }
    const trimmed = input.trim();
    if (!trimmed) {
        return '';
    }
    if (isAbsolute(trimmed)) {
        if (isSafeAbsolute(trimmed)) {
            return trimmed;
        }
        return '';
    }
    const withoutLeadingSlash = trimmed.replace(/^\/+/, '');
    const normalized = withoutLeadingSlash.startsWith('assets/') ? withoutLeadingSlash.slice(7) : withoutLeadingSlash;
    const base = resolveAssetBase(baseUrl);
    if (/(?:^|\/)\.\.(?:\/|$)/.test(normalized)) {
        return '';
    }
    try {
        const resolved = new URL(normalized, base).href;
        if (!resolved.startsWith('about:')) {
            return resolved;
        }
    } catch (error) {
        ensureError(error);
    }
    if (isInternalPath(normalized)) {
        return `${base.replace(/\/+$/, '')}/${normalized}`;
    }
    return normalized;
};

export { resolveAssetPath };

export type { ResolveAssetPathOptions };
