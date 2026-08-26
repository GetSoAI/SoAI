/* SoAI - Shared security SVG markup sanitizer [frontend/assets/ts/core/security/svgMarkupSanitizer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { requireDocument } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { escapeHtml, sanitizeText } from '@core/security/textSanitizer.ts';
import { getSecurityPurifierFromDocument, DISALLOWED_ELEMENTS } from '@core/security/domPurifySecurity.ts';

let hasWarnedMissingDocumentForSanitizeSvg = false;

const STANDALONE_SVG_REGEX = new RegExp('^\\s*<' + 'svg[\\s>]', 'i');
const isStandaloneSvgMarkup = (markup: string): boolean => STANDALONE_SVG_REGEX.test(markup);

const sanitizeSvgMarkup = (markup: string): string => {
    if (!markup) {
        return '';
    }

    if (!isStandaloneSvgMarkup(markup)) {
        throw new Error('sanitizeSvg requires standalone svg markup');
    }

    let doc: Document | null = null;
    try {
        doc = requireDocument();
    } catch (error) {
        if (!hasWarnedMissingDocumentForSanitizeSvg) {
            hasWarnedMissingDocumentForSanitizeSvg = true;
            errorHandler.warn('Security', 'sanitizeSvg called without Document; returning escaped markup', ensureError(error));
        }
        doc = null;
    }
    if (!doc) {
        return escapeHtml(markup);
    }

    const purify = getSecurityPurifierFromDocument(doc);
    if (!purify) {
        return escapeHtml(markup);
    }

    const forbidTags = [...Array.from(DISALLOWED_ELEMENTS), 'foreignobject'];
    const config = {
        USE_PROFILES: { svg: true, svgFilters: true },
        FORBID_TAGS: forbidTags,
        ADD_TAGS: ['style'],
        ADD_ATTR: ['nonce']
    };

    return purify.sanitize(markup, config);
};

const sanitizeSvg = <T>(value?: T): string => {
    const markup = sanitizeText(value, { trim: false });
    return sanitizeSvgMarkup(markup);
};

export { sanitizeSvg };
