/* SoAI - Shared security HTML sanitizer [frontend/assets/ts/core/security/htmlSanitizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireDocument } from '@core/environment/public.ts';
import { parseTableBodyElement } from '@core/dom/tableBodyParsing.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { escapeHtml, sanitizeText } from '@core/security/textSanitizer.ts';
import { DISALLOWED_ELEMENTS, getSecurityPurifierFromDocument } from '@core/security/domPurifySecurity.ts';
import { isObject } from '@core/typeGuards.ts';
import { sanitizeSvg } from '@core/security/svgMarkupSanitizer.ts';

const TRUSTED_HTML_BRAND: unique symbol = Symbol('SoAI.TrustedHtml');
const trustedHtmlBrandValue = (): true => true;

interface TrustedHtml {
    readonly [TRUSTED_HTML_BRAND]: true;
    html: string;
}

interface TrustedHtmlValue extends TrustedHtml {
    readonly toString: () => string;
    readonly valueOf: () => string;
    readonly [Symbol.toPrimitive]: () => string;
}

interface TrustedHtmlCandidate {
    readonly html?: string;
}

const trustedHtmlBrands = new WeakSet<TrustedHtmlCandidate>();

const isTrustedHtmlCandidate = <T>(value: T): value is T & TrustedHtmlCandidate => isObject(value);

const createTrustedHtmlValue = (html: string): TrustedHtml => {
    const stringify = (): string => html;
    const trustedHtml: TrustedHtmlValue = Object.freeze({
        [TRUSTED_HTML_BRAND]: trustedHtmlBrandValue(),
        html,
        toString: stringify,
        valueOf: stringify,
        [Symbol.toPrimitive]: stringify
    });
    trustedHtmlBrands.add(trustedHtml);
    return trustedHtml;
};

let hasWarnedMissingDocumentForSanitizeHtml = false;

const getSanitizationDocument = (): Document | null => {
    try {
        return requireDocument();
    } catch (error) {
        if (!hasWarnedMissingDocumentForSanitizeHtml) {
            hasWarnedMissingDocumentForSanitizeHtml = true;
            errorHandler.warn('Security', 'HTML sanitization called without Document; falling back to escaping markup', ensureError(error));
        }
        return null;
    }
};

const sanitizeHtmlMarkup = (markup: string): string => {
    if (!markup) {
        return '';
    }
    const doc = getSanitizationDocument();
    if (!doc) {
        return escapeHtml(markup);
    }

    const purify = getSecurityPurifierFromDocument(doc);
    if (!purify) {
        return escapeHtml(markup);
    }

    const forbidTags = Array.from(DISALLOWED_ELEMENTS);
    const config = {
        USE_PROFILES: { html: true },
        FORBID_TAGS: [...forbidTags, 'style', 'svg'],
        ADD_ATTR: ['directory', 'nonce', 'webkitdirectory']
    };

    return purify.sanitize(markup, config);
};

const sanitizeHtml = <T>(value?: T): string => {
    const markup = sanitizeText(value, { trim: false });
    return sanitizeHtmlMarkup(markup);
};

const toTrustedHtml = (value: string): TrustedHtml => {
    return createTrustedHtmlValue(sanitizeHtml(value));
};

const toTrustedSvg = (value: string): TrustedHtml => {
    return createTrustedHtmlValue(sanitizeSvg(value));
};

const createUiHtmlSanitizerConfig = () => ({
    USE_PROFILES: { html: true, svg: true, svgFilters: true },
    FORBID_TAGS: [...Array.from(DISALLOWED_ELEMENTS), 'foreignobject', 'style'],
    ADD_ATTR: ['directory', 'nonce', 'webkitdirectory']
});

const sanitizeUiHtmlMarkup = (markup: string): string => {
    if (!markup) {
        return '';
    }
    const doc = getSanitizationDocument();
    if (!doc) {
        return escapeHtml(markup);
    }
    const purify = getSecurityPurifierFromDocument(doc);
    if (!purify) {
        return escapeHtml(markup);
    }
    return purify.sanitize(markup, createUiHtmlSanitizerConfig());
};

const sanitizeTableBodyMarkup = (markup: string): string => {
    if (!markup) {
        return '';
    }
    const doc = requireDocument();
    const purify = getSecurityPurifierFromDocument(doc);
    if (!purify) {
        throw new Error('Table body sanitization requires a security purifier');
    }
    const tableBody = parseTableBodyElement({ documentRef: doc, html: markup });
    purify.sanitize(tableBody, { ...createUiHtmlSanitizerConfig(), IN_PLACE: true });
    for (const child of Array.from(tableBody.childNodes)) {
        if (child instanceof Text && !child.data.trim()) {
            continue;
        }
        if (child instanceof Element && child.tagName === 'TR') {
            continue;
        }
        throw new Error('Table body markup must contain only table rows');
    }
    return tableBody.innerHTML;
};

const toTrustedUiHtml = (value: string): TrustedHtml => {
    const normalized = value.trim();
    if (normalized && !normalized.startsWith('<')) {
        throw new Error('toTrustedUiHtml requires a complete HTML fragment');
    }
    if (/^<(?:caption|col|colgroup|tbody|td|tfoot|th|thead|tr)(?:\s|>)/iu.test(normalized)) {
        throw new Error('Table structure requires a table-specific TrustedHtml boundary');
    }
    return createTrustedHtmlValue(sanitizeUiHtmlMarkup(value));
};

const toTrustedTableBodyHtml = (value: string): TrustedHtml => {
    const normalized = value.trim();
    if (normalized && !/^<tr(?:\s|>)/iu.test(normalized)) {
        throw new Error('toTrustedTableBodyHtml requires table row markup');
    }
    return createTrustedHtmlValue(sanitizeTableBodyMarkup(value));
};

const isTrustedHtml = <T>(value: T): value is T & TrustedHtml => {
    if (!isTrustedHtmlCandidate(value)) {
        return false;
    }
    return trustedHtmlBrands.has(value) && typeof value.html === 'string';
};

export { createTrustedHtmlValue, sanitizeHtml, toTrustedHtml, toTrustedSvg, toTrustedTableBodyHtml, toTrustedUiHtml, isTrustedHtml };
export type { TrustedHtml };
