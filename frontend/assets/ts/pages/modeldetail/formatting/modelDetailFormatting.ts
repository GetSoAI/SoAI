/* SoAI - Model detail page formatting implementation [frontend/assets/ts/pages/modeldetail/formatting/modelDetailFormatting.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { formatNullableEpochMsSecondOrNull } from '@core/primitives/dateTime.ts';
import { resolveHttpUrl } from '@core/security/public.ts';
import { isArray, isObject } from '@core/typeGuards.ts';

const maskModelDetailApiUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;
    try {
        const resolved = resolveHttpUrl(url) ?? url;
        const parsed = new URL(resolved);
        return `${parsed.protocol}//${parsed.host}${parsed.pathname ? '/...' : ''}`;
    } catch (error) {
        ensureError(error);
        return url.length > 30 ? `${url.substring(0, 30)}...` : url;
    }
};

const formatModelDetailDefaultValue = (value: JsonValue, valueType: string): string | null => {
    if (value === null || value === undefined) return null;
    if (valueType === 'boolean') return value ? 'true' : 'false';
    if (valueType === 'array') {
        return isArray(value) && value.length > 0 ? JSON.stringify(value) : null;
    }
    if (valueType === 'object') {
        return isObject(value) && Object.keys(value).length > 0 ? JSON.stringify(value) : null;
    }
    return valueType === 'string' && value === '' ? null : String(value);
};

const formatModelDetailDateTime = (timestampMs: number | null | undefined): string | null => formatNullableEpochMsSecondOrNull(timestampMs);

const extractCleanModelIdentifier = (identifier: string | undefined): string | undefined => {
    if (!identifier) return identifier;
    const parts = identifier.split('/');
    return parts.length > 1 ? parts.slice(1).join('/') : identifier;
};

export { extractCleanModelIdentifier, formatModelDetailDateTime, formatModelDetailDefaultValue, maskModelDetailApiUrl };
