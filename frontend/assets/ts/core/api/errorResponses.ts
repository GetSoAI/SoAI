/* SoAI - Shared API error responses [frontend/assets/ts/core/api/errorResponses.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, type APIErrorMetadata } from '@core/apiError.ts';
import { extractResponseMessage, parseResponsePayload, setApiErrorMetadataField } from '@core/api/mappers.ts';
import { parseRetryAfterHeaderSeconds } from '@core/api/retryAfterHeader.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isJsonObject, type JsonObject } from '@core/types/jsonValues.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';

interface ApiErrorResponseDependencies {
    populateApiErrorDetail: (metadata: APIErrorMetadata, apiErrorDetail: JsonObject | null) => void;
}

const readResponseHeader = (response: Response, name: string): string | null => {
    const value = response.headers?.get(name);
    return typeof value === 'string' && value.trim() ? value.trim() : null;
};

const populateResponseHeaderMetadata = (metadata: APIErrorMetadata, response: Response): void => {
    const retryAfterSeconds = parseRetryAfterHeaderSeconds(response.headers?.get('Retry-After') ?? null);
    if (retryAfterSeconds !== null) {
        metadata.retryAfterSeconds = retryAfterSeconds;
    }
    const taskIdHeader = readResponseHeader(response, 'X-SoAI-Task-Id');
    if (taskIdHeader !== null) {
        metadata.taskId = taskIdHeader;
    }
    const traceIdHeader = readResponseHeader(response, 'X-SoAI-Operation-Id');
    if (traceIdHeader !== null) {
        metadata.traceId = traceIdHeader;
    }
};

const populateResponsePayloadMetadata = (metadata: APIErrorMetadata, payload: ApiResponsePayload, dependencies: ApiErrorResponseDependencies): void => {
    if (!isJsonObject(payload)) {
        return;
    }
    metadata.payload = payload;
    const errorDetailValue = payload['error'];
    const apiErrorDetail: JsonObject | null = isJsonObject(errorDetailValue) ? errorDetailValue : null;
    dependencies.populateApiErrorDetail(metadata, apiErrorDetail);
    if (!apiErrorDetail) {
        setApiErrorMetadataField(metadata, 'code', payload['code']);
        if (!metadata.code) {
            setApiErrorMetadataField(metadata, 'code', payload['error_type']);
        }
    }
};

const extractApiErrorResponseMessage = (payload: ApiResponsePayload, fallback: string): string => {
    try {
        return extractResponseMessage(payload);
    } catch (extractionError) {
        const message = ensureError(extractionError).message.trim();
        return message || fallback;
    }
};

const buildApiErrorFromResponse = async (response: Response, dependencies: ApiErrorResponseDependencies): Promise<APIError> => {
    const metadata: APIErrorMetadata = {};
    populateResponseHeaderMetadata(metadata, response);
    let payload: ApiResponsePayload;
    try {
        payload = await parseResponsePayload(response);
    } catch (payloadError) {
        const runtimeError = ensureError(payloadError);
        metadata.cause = runtimeError;
        return new APIError(response.status, response.statusText || 'Request failed', metadata);
    }
    populateResponsePayloadMetadata(metadata, payload, dependencies);
    return new APIError(response.status, extractApiErrorResponseMessage(payload, response.statusText || 'Request failed'), metadata);
};

export { buildApiErrorFromResponse };
export type { ApiErrorResponseDependencies };
