/* SoAI - Chat SoAI path canonical value validation [frontend/assets/ts/features/chat/validation/soaiPathValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isString } from '@core/typeGuards.ts';

const hasCanonicalPathSegments = (value: string): boolean => {
    const parts = value.split('/');
    return parts.length > 0 && parts.every((part) => part.length > 0 && part !== '.' && part !== '..');
};

const normalizeConversationVirtualPathValue = (value: JsonValue | null | undefined): string | null => {
    if (!isString(value) || value !== value.trim()) {
        return null;
    }
    if (!value.startsWith('/') || value === '/' || value.includes('\\') || value.includes('\0')) {
        return null;
    }
    const withoutPrefix = value.slice(1);
    if (!hasCanonicalPathSegments(withoutPrefix)) {
        return null;
    }
    return value;
};

const normalizeWorkspaceRelativePathValue = (value: JsonValue | null | undefined): string | null => {
    if (!isString(value) || value !== value.trim()) {
        return null;
    }
    if (!value || value.startsWith('/') || value.includes('\\') || value.includes('\0')) {
        return null;
    }
    if (!hasCanonicalPathSegments(value)) {
        return null;
    }
    return value;
};

export { normalizeConversationVirtualPathValue, normalizeWorkspaceRelativePathValue };
