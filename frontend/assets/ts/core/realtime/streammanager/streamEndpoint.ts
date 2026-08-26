/* SoAI - Shared realtime stream endpoint [frontend/assets/ts/core/realtime/streammanager/streamEndpoint.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const ensureString = (value: JsonValue | null | undefined, label = 'Endpoint'): string => {
    const str = toTrimmedString(value);
    if (!str) throw new Error(`[StreamManager] ${label} required`);
    return str;
};

const ensureLeadingSlash = (value: string): string => {
    const trimmed = ensureString(value);
    return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
};

const normalizeEndpoint = (endpoint: string): { endpoint: string; absolute: boolean } => {
    const trimmed = ensureString(endpoint);
    const isAbsolute = isAbsoluteHttpUrl(trimmed);
    return { endpoint: isAbsolute ? trimmed : ensureLeadingSlash(trimmed), absolute: isAbsolute };
};

export { normalizeEndpoint };
