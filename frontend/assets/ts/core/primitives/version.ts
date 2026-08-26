/* SoAI - Shared primitives version [frontend/assets/ts/core/primitives/version.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { securityApi } from '@core/security/public.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';

export const normalizeVersion = (value: JsonValue): { raw: string | null; safe: string | null } => {
    if (isNullOrUndefined(value)) return { raw: null, safe: null };
    const raw = String(value);
    const trimmed = raw.trim();
    if (!trimmed) return { raw, safe: null };
    return { raw, safe: securityApi.escapeHtml(trimmed) };
};
