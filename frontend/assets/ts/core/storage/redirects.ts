/* SoAI - Shared storage redirects [frontend/assets/ts/core/storage/redirects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isString } from '@core/typeGuards.ts';

const DANGEROUS_REDIRECT_PATTERN = /^(javascript|data|vbscript|file):|^\/\//i;

const isSafeRedirectPath = (path: string): boolean => {
    if (!isString(path) || !path.trim()) {
        return false;
    }
    const trimmed = path.trim();
    if (DANGEROUS_REDIRECT_PATTERN.test(trimmed)) {
        return false;
    }
    if (trimmed.includes(':') && !trimmed.startsWith('/')) {
        return false;
    }
    return true;
};

export { isSafeRedirectPath };
