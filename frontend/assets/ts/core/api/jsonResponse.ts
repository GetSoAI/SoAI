/* SoAI - Shared frontend API JSON response [frontend/assets/ts/core/api/jsonResponse.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody, RequestOptions } from '@core/api/types/request.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';

const requireJsonResponse = async (response: Promise<ApiResponsePayload>, method: string, endpoint: string): Promise<JsonValue> => {
    const payload = await response;
    if (!isJsonValue(payload)) {
        throw new Error(`Expected JSON response from ${method} ${endpoint}`);
    }
    return payload;
};

const getJsonResponse = (api: ApiClientContext, endpoint: string, options?: RequestOptions): Promise<JsonValue> => requireJsonResponse(api.get(endpoint, options), 'GET', endpoint);

const postJsonResponse = (api: ApiClientContext, endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<JsonValue> => requireJsonResponse(api.post(endpoint, data, options), 'POST', endpoint);

const putJsonResponse = (api: ApiClientContext, endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<JsonValue> => requireJsonResponse(api.put(endpoint, data, options), 'PUT', endpoint);

const patchJsonResponse = (api: ApiClientContext, endpoint: string, data?: ApiRequestBody, options?: RequestOptions): Promise<JsonValue> => requireJsonResponse(api.patch(endpoint, data, options), 'PATCH', endpoint);

export { getJsonResponse, patchJsonResponse, postJsonResponse, putJsonResponse, requireJsonResponse };
