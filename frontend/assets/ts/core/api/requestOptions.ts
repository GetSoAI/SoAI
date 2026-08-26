/* SoAI - Shared API request options [frontend/assets/ts/core/api/requestOptions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrimmedString } from '@core/normalize.ts';
import type { ApiQueryParameters } from '@core/api/types/request.ts';

type SignalOptions = { signal?: AbortSignal | undefined };
type AuthTransitionSignalOptions = { signal?: AbortSignal | undefined; authTransitionOwned?: boolean | undefined };

const buildSignalRequestOptions = (options: AuthTransitionSignalOptions = {}): { signal?: AbortSignal; authTransitionOwned?: boolean } => ({
    ...(options.signal ? { signal: options.signal } : {}),
    ...(options.authTransitionOwned === true ? { authTransitionOwned: true } : {})
});

const requireNonEmptyRequestString = (value: string, field: string, prefix: string): string => {
    const normalized = toTrimmedString(value);
    if (!normalized) {
        throw new Error(`${prefix}.${field} is required`);
    }
    return normalized;
};

const normalizeNonEmptyRequestStrings = (values: readonly string[], field: string, prefix: string): string[] => {
    if (values.length <= 0) {
        throw new Error(`${prefix}.${field} requires at least one path`);
    }
    return values.map((value, index) => requireNonEmptyRequestString(value, `${field}[${String(index)}]`, prefix));
};

const buildQueryRequestOptions = (options: ApiQueryParameters | null | undefined = null, signal: AbortSignal | null | undefined = null): { query: ApiQueryParameters | null; signal?: AbortSignal } => {
    if (!options) {
        return { query: null };
    }
    const query: ApiQueryParameters = { ...options };
    return signal ? { query, signal } : { query };
};

export { buildQueryRequestOptions, buildSignalRequestOptions, normalizeNonEmptyRequestStrings, requireNonEmptyRequestString };
export type { AuthTransitionSignalOptions, SignalOptions };
