/* SoAI - Shared API mappers [frontend/assets/ts/core/api/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { readApiErrorField, type APIErrorMetadata, type APIErrorMetadataValue } from '@core/apiError.ts';
import { applyCsrfHeader } from '@core/api/csrf.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { toString, toTrimmedString } from '@core/normalize.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { hasOwn, isFiniteNumber, isFunction, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import { isJsonObject, isJsonValue, type JsonObject } from '@core/types/jsonValues.ts';
import { ERR_DETAIL_MAP, MESSAGE_KEYS, getApiRequestTimeoutMs, getDefaultContentType } from '@core/api/constants.ts';
import type { FetchConfig, FetchConfigInput } from '@core/api/types/apiClient.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';

const normalizeMethod = (method: string = 'GET'): string => (isString(method) && method ? method.toUpperCase() : 'GET');

const normalizeRequestTimeoutMs = <T>(value: T): number => {
    if (value === null || value === undefined) return getApiRequestTimeoutMs();
    if (typeof value === 'number' && Number.isFinite(value) && value > 0) return value;
    throw new Error('API request timeout must be a positive number');
};

const buildFetchConfig = (options: FetchConfigInput = {}): FetchConfig => {
    const { method = 'GET', headers = {}, body, signal, cache = 'no-store', credentials = 'include', keepalive, includeCsrfHeader = true } = options;
    const normalizedMethod = normalizeMethod(method);
    const requestHeaders: Record<string, string> = { ...headers };
    applyCsrfHeader(requestHeaders, normalizedMethod, credentials, includeCsrfHeader);
    const methodAllowsBody = normalizedMethod !== 'GET' && normalizedMethod !== 'HEAD';
    const config: FetchConfig = { method: normalizedMethod, headers: requestHeaders, credentials, cache };

    if (signal) config.signal = signal;
    if (keepalive === true) config.keepalive = true;

    if (!methodAllowsBody || isNullOrUndefined(body)) {
        if (!methodAllowsBody) delete requestHeaders['Content-Type'];
        return config;
    }

    const isRequestBody = (typeof body === 'object' && body !== null && (body instanceof FormData || body instanceof Blob || body instanceof ArrayBuffer || body instanceof URLSearchParams || (typeof ReadableStream === 'function' && body instanceof ReadableStream))) || isArrayBufferView(body);

    if (isRequestBody) {
        delete requestHeaders['Content-Type'];
        config.body = body;
        return config;
    }

    config.body = isString(body) ? body : JSON.stringify(body);
    if (!hasOwn(requestHeaders, 'Content-Type')) {
        requestHeaders['Content-Type'] = getDefaultContentType();
    }
    return config;
};

const isArrayBufferView = <T>(value: T): value is T & ArrayBufferView<ArrayBuffer> => {
    if (typeof ArrayBuffer !== 'function') {
        return false;
    }
    if (!isFunction(ArrayBuffer.isView)) {
        return false;
    }
    if (!ArrayBuffer.isView(value)) {
        return false;
    }
    return value.buffer instanceof ArrayBuffer;
};

const readResponseText = (response: Response): Promise<string> => response.text();

const parseJsonResponseText = (text: string): ApiResponsePayload => {
    if (!text.trim()) {
        return undefined;
    }
    return parseRequiredJsonText(text);
};

const parseResponsePayload = async (response: Response): Promise<ApiResponsePayload> => {
    const status = response?.status ?? 0;
    if (status === 204 || status === 205) return undefined;
    if (response.headers?.get('content-length') === '0') return undefined;

    const contentType = response.headers?.get('content-type') || '';
    const responseText = await readResponseText(response);
    if (!contentType) return responseText;
    if (contentType.includes('application/json')) {
        try {
            return parseJsonResponseText(responseText);
        } catch (error) {
            throw ensureError(error);
        }
    }
    return responseText;
};

const extractResponseMessage = (payload: ApiResponsePayload): string => {
    if (isString(payload)) {
        const message = toTrimmedString(payload);
        if (message) return message;
    }
    if (!isJsonObject(payload)) throw new Error('Response payload did not include an error message');

    const payloadError = payload['error'];
    if (hasOwn(payload, 'error') && isString(payloadError)) {
        const message = toTrimmedString(payloadError);
        if (message) return message;
    }

    const errorObject: JsonObject | null = hasOwn(payload, 'error') && isJsonObject(payloadError) ? payloadError : null;
    if (errorObject) {
        for (const key of MESSAGE_KEYS) {
            if (hasOwn(errorObject, key) && isString(errorObject[key])) {
                const message = toTrimmedString(errorObject[key]);
                if (message) return message;
            }
        }
    }

    for (const key of MESSAGE_KEYS) {
        if (hasOwn(payload, key) && isString(payload[key])) {
            const message = toTrimmedString(payload[key]);
            if (message) return message;
        }
    }

    throw new Error('Response payload did not include an error message');
};

const setApiErrorMetadataField = (metadata: APIErrorMetadata, key: keyof APIErrorMetadata, value: APIErrorMetadataValue): void => {
    switch (key) {
        case 'code': {
            if (isString(value) && value) metadata.code = value;
            return;
        }
        case 'reason': {
            if (isString(value) && value) metadata.reason = value;
            return;
        }
        case 'traceId': {
            if (isString(value) && value) metadata.traceId = value;
            return;
        }
        case 'endpoint': {
            if (isString(value) && value) metadata.endpoint = value;
            return;
        }
        case 'taskId': {
            if (isString(value) && value) metadata.taskId = value;
            return;
        }
        case 'retryAfterSeconds': {
            if (isFiniteNumber(value) && value > 0) metadata.retryAfterSeconds = value;
            return;
        }
        case 'detail': {
            metadata.detail = value;
            return;
        }
        case 'cause': {
            metadata.cause = value;
            return;
        }
        case 'data': {
            metadata.data = value;
            return;
        }
    }
};

const populateApiErrorDetail = (metadata: APIErrorMetadata, apiErrorDetail: JsonObject | null): void => {
    if (!apiErrorDetail) return;
    if (hasOwn(apiErrorDetail, 'type')) {
        setApiErrorMetadataField(metadata, 'code', apiErrorDetail['type']);
    }
    if (hasOwn(apiErrorDetail, 'code')) {
        const codeValue = apiErrorDetail['code'];
        const typeValue = hasOwn(apiErrorDetail, 'type') ? apiErrorDetail['type'] : null;
        if (isString(codeValue) && codeValue && (!isString(typeValue) || codeValue !== typeValue)) {
            setApiErrorMetadataField(metadata, 'reason', codeValue);
        }
    }
    for (const [sourceKey, targetKey] of ERR_DETAIL_MAP) {
        if (hasOwn(apiErrorDetail, sourceKey)) {
            const value = apiErrorDetail[sourceKey];
            const normalizedKey = sourceKey;
            const expectsString = normalizedKey === 'reason' || normalizedKey === 'code' || normalizedKey === 'trace_id' || normalizedKey === 'endpoint';
            if (expectsString && !isString(value)) {
                continue;
            }
            setApiErrorMetadataField(metadata, targetKey, value);
        }
    }
    const detailsValue = hasOwn(apiErrorDetail, 'details') ? apiErrorDetail['details'] : null;
    if (isJsonObject(detailsValue) && hasOwn(detailsValue, 'task_id')) {
        setApiErrorMetadataField(metadata, 'taskId', detailsValue['task_id']);
    }
};

const normalizeRuntimeErrorValue = <T>(error: T): APIErrorMetadataValue => {
    if (error === null) return null;
    if (error === undefined) return undefined;
    if (typeof error === 'string') return error;
    if (typeof error === 'number') return error;
    if (typeof error === 'bigint') return error;
    if (typeof error === 'boolean') return error;
    if (typeof error === 'symbol') return error;
    if (isObject(error) && error instanceof Error) {
        return error;
    }
    if (isJsonValue(error)) {
        return error;
    }
    return toString(error);
};

const enrichApiErrorMetadataFromValue = (metadata: APIErrorMetadata, error: APIErrorMetadataValue): void => {
    if (!error || !isObject(error)) return;
    if (hasOwn(error, 'code')) setApiErrorMetadataField(metadata, 'code', normalizeRuntimeErrorValue(readApiErrorField(error, 'code')));
    if (hasOwn(error, 'detail')) setApiErrorMetadataField(metadata, 'detail', normalizeRuntimeErrorValue(readApiErrorField(error, 'detail')));
    if (hasOwn(error, 'reason')) setApiErrorMetadataField(metadata, 'reason', normalizeRuntimeErrorValue(readApiErrorField(error, 'reason')));
    if (hasOwn(error, 'cause')) setApiErrorMetadataField(metadata, 'cause', normalizeRuntimeErrorValue(readApiErrorField(error, 'cause')));
    if (hasOwn(error, 'task_id')) setApiErrorMetadataField(metadata, 'taskId', normalizeRuntimeErrorValue(readApiErrorField(error, 'task_id')));
};

export { buildFetchConfig, extractResponseMessage, normalizeMethod, normalizeRequestTimeoutMs, normalizeRuntimeErrorValue, populateApiErrorDetail, parseResponsePayload, setApiErrorMetadataField, enrichApiErrorMetadataFromValue };
