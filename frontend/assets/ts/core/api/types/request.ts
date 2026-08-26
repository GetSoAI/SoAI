/* SoAI - Shared API request [frontend/assets/ts/core/api/types/request.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';

type ApiPathSegmentValue = string | number | null | undefined | void;
type ApiQueryScalar = string | number | boolean | null | undefined;
type ApiQueryValue = ApiQueryScalar | readonly ApiQueryScalar[];
type ApiQueryParameters = Record<string, ApiQueryValue>;
type ApiRequestBody = JsonValue | BodyInit | null | undefined | void;

interface RequestOptions {
    rawResponse?: boolean;
    bufferRawResponse?: boolean;
    headers?: Record<string, string>;
    query?: ApiQueryParameters | null;
    body?: ApiRequestBody;
    timeoutMs?: number;
    credentials?: RequestCredentials;
    cache?: RequestCache;
    keepalive?: boolean;
    signal?: AbortSignal | undefined;
    onUploadProgress?: (progress: UploadProgress) => void;
    authTransitionOwned?: boolean | undefined;
}

interface UploadProgress {
    loadedBytes: number;
    totalBytes: number | null;
    percent: number | null;
}

export type { UploadProgress };
export type { ApiPathSegmentValue, ApiQueryParameters, ApiQueryScalar, ApiQueryValue, ApiRequestBody, RequestOptions };
