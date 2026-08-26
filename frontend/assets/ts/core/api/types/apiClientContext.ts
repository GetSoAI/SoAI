/* SoAI - Shared API client context [frontend/assets/ts/core/api/types/apiClientContext.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiPathSegmentValue, ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';

interface ApiClientContext {
    get(endpoint: string, options?: RequestOptions): Promise<ApiResponsePayload>;
    post(endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<ApiResponsePayload>;
    put(endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<ApiResponsePayload>;
    patch(endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<ApiResponsePayload>;
    delete(endpoint: string, options?: RequestOptions): Promise<ApiResponsePayload>;
    uploadFile(endpoint: string, file: Blob, additionalData?: Record<string, string | Blob>, options?: RequestOptions, filenameOverride?: string | null): Promise<ApiResponsePayload>;
    encodePathSegment(value: ApiPathSegmentValue): string;
}

export type { ApiClientContext };
