/* SoAI - Shared security protocols [frontend/assets/ts/core/security/protocols.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizeUrlOptions } from '@core/security/urlSanitizer.ts';

interface EscapeSanitizerApi {
    escapeHtml: <T>(value: T) => string;
    escapeAttribute: <T>(value: T) => string;
    sanitizeUrl: <T>(value: T, options?: SanitizeUrlOptions) => string | null;
    sanitizeAbsoluteHttpUrl: <T>(value: T) => string | null;
    resolveHttpsWebsiteUrl: <T>(value: T) => string | null;
}

export type { EscapeSanitizerApi };
