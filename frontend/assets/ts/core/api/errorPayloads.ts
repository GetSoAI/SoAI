/* SoAI - Shared API error payloads [frontend/assets/ts/core/api/errorPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, type APIErrorMetadataRecord, type APIErrorMetadataValue } from '@core/apiError.ts';
import { extractApiErrorMessage } from '@core/errors/coerce.ts';

const isApiErrorMetadataRecord = <T>(value: T): value is T & APIErrorMetadataRecord => {
    if (value === null || value === undefined) {
        return false;
    }
    return typeof value === 'object' || typeof value === 'function';
};

const readApiErrorMetadataPath = <T>(value: T, path: readonly string[]): APIErrorMetadataValue => {
    if (path.length === 0) {
        return null;
    }
    if (!isApiErrorMetadataRecord(value)) {
        return null;
    }
    const firstSegment = path[0];
    if (firstSegment === undefined) {
        return null;
    }
    let current: APIErrorMetadataValue = value[firstSegment];
    for (const segment of path.slice(1)) {
        if (!isApiErrorMetadataRecord(current)) {
            return null;
        }
        current = current[segment];
    }
    return current;
};

const readApiRetryAfterSeconds = <T>(value: T): number | null => {
    const candidates: readonly APIErrorMetadataValue[] = [value instanceof APIError ? value.retryAfterSeconds : null, readApiErrorMetadataPath(value, ['payload', 'error', 'details', 'retry_after_seconds']), readApiErrorMetadataPath(value, ['payload', 'details', 'retry_after_seconds']), readApiErrorMetadataPath(value, ['response', 'data', 'error', 'details', 'retry_after_seconds']), readApiErrorMetadataPath(value, ['data', 'error', 'details', 'retry_after_seconds']), readApiErrorMetadataPath(value, ['retry_after_seconds'])];
    for (const candidate of candidates) {
        if (typeof candidate === 'number' && Number.isFinite(candidate) && candidate > 0) {
            return candidate;
        }
        if (typeof candidate === 'string') {
            const numeric = Number(candidate.trim());
            if (Number.isFinite(numeric) && numeric > 0) {
                return numeric;
            }
        }
    }
    return null;
};

const resolveApiErrorMessage = <T>(value: T): string | null => {
    if (value instanceof APIError) {
        return (extractApiErrorMessage(value) ?? value.message) || null;
    }
    return extractApiErrorMessage(value);
};

export { readApiRetryAfterSeconds, resolveApiErrorMessage };
