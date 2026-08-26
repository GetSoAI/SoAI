/* SoAI - Frontend security API ownership [frontend/assets/ts/core/security/securityApi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { escapeAttribute, escapeHtml, sanitizeText, type SanitizeTextOptions } from '@core/security/textSanitizer.ts';
import { isAbsoluteHttpUrl, resolveHttpUrl, resolveHttpsWebsiteUrl, sanitizeAbsoluteHttpUrl, sanitizeImageSource, sanitizeUrl, type SanitizeUrlOptions } from '@core/security/urlSanitizer.ts';
import { isTrustedHtml, sanitizeHtml, toTrustedHtml, toTrustedSvg, toTrustedTableBodyHtml, toTrustedUiHtml, type TrustedHtml } from '@core/security/htmlSanitizer.ts';
import { sanitizeSvg } from '@core/security/svgMarkupSanitizer.ts';
import { renderLabelAttributes } from '@core/security/labelAttributes.ts';

interface SecurityAPI {
    escapeHtml: <T>(value?: T) => string;
    escapeAttribute: <T>(value?: T) => string;
    sanitizeText: <T>(value?: T, options?: SanitizeTextOptions) => string;
    sanitizeHtml: <T>(value?: T) => string;
    sanitizeSvg: <T>(value?: T) => string;
    sanitizeUrl: <T>(input: T, options?: SanitizeUrlOptions) => string | null;
    sanitizeAbsoluteHttpUrl: <T>(input: T) => string | null;
    sanitizeImageSource: <T>(input: T) => string | null;
    isAbsoluteHttpUrl: <T>(input: T) => input is T & string;
    resolveHttpUrl: <T>(input: T, baseUrl?: string) => string | null;
    resolveHttpsWebsiteUrl: <T>(input: T) => string | null;
}

const securityApi: SecurityAPI = Object.freeze({
    escapeHtml,
    escapeAttribute,
    sanitizeText,
    sanitizeHtml,
    sanitizeSvg,
    sanitizeUrl,
    sanitizeAbsoluteHttpUrl,
    sanitizeImageSource,
    isAbsoluteHttpUrl,
    resolveHttpUrl,
    resolveHttpsWebsiteUrl
});

export { securityApi };
export { isAbsoluteHttpUrl, resolveHttpUrl, resolveHttpsWebsiteUrl };
export { toTrustedHtml };
export { toTrustedUiHtml };
export { toTrustedTableBodyHtml };
export { isTrustedHtml };
export { renderLabelAttributes };
export type { SanitizeTextOptions, SanitizeUrlOptions, SecurityAPI, TrustedHtml };

export { toTrustedSvg };
