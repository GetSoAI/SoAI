/* SoAI - Shared API constants [frontend/assets/ts/core/api/constants.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { APIErrorMetadata } from '@core/apiError.ts';
import { assertNonNull } from '@core/assertions.ts';
import { getConstants, getCoreTimeout } from '@core/runtime/runtimeContext.ts';
import { hasOwn, isString } from '@core/typeGuards.ts';

const LOGOUT_ENDPOINT = '/api/v1/webui/auth/logout';

type HttpConstants = ReturnType<typeof getConstants>['HTTP'];

let coreModuleTimeoutCache: number | null = null;
let apiRequestTimeoutCache: number | null = null;
let httpConstantsCache: HttpConstants | null = null;
let defaultHeadersCache: Readonly<Record<string, string>> | null = null;
let defaultContentTypeCache: string | null = null;

const getCoreModuleTimeoutMs = (): number => {
    if (coreModuleTimeoutCache !== null) {
        return coreModuleTimeoutCache;
    }
    const value = getCoreTimeout('CORE_MODULES');
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
        throw new Error('CORE_MODULES timeout must be a finite positive number');
    }
    coreModuleTimeoutCache = value;
    return value;
};

const getApiRequestTimeoutMs = (): number => {
    if (apiRequestTimeoutCache !== null) {
        return apiRequestTimeoutCache;
    }
    const value = getCoreTimeout('API_REQUEST');
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) {
        throw new Error('API_REQUEST timeout must be a finite positive number');
    }
    apiRequestTimeoutCache = value;
    return value;
};

const getHttpConstants = (): HttpConstants => {
    if (httpConstantsCache !== null) {
        return httpConstantsCache;
    }
    httpConstantsCache = getConstants().HTTP;
    return httpConstantsCache;
};

const buildDefaultHeaders = (httpConstantsValue: HttpConstants): Record<string, string> => {
    const defaultsValue = httpConstantsValue.DEFAULT_HEADERS;
    const defaults = Object.entries(defaultsValue).reduce<Record<string, string>>((next, [key, rawValue]) => {
        assertNonNull(key, 'Header key');
        if (!isString(rawValue)) {
            throw new Error('DEFAULT_HEADERS must contain only string values');
        }
        next[key] = rawValue;
        return next;
    }, {});
    if (!hasOwn(defaults, 'Content-Type')) {
        throw new Error('DEFAULT_HEADERS must include Content-Type');
    }
    return defaults;
};

const getDefaultHeaders = (): Readonly<Record<string, string>> => {
    if (defaultHeadersCache) {
        return defaultHeadersCache;
    }
    const headers = Object.freeze(buildDefaultHeaders(getHttpConstants()));
    defaultHeadersCache = headers;
    return headers;
};

const getDefaultContentType = (): string => {
    if (defaultContentTypeCache) {
        return defaultContentTypeCache;
    }
    const contentType = getDefaultHeaders()['Content-Type'];
    if (!isString(contentType) || !contentType.trim()) {
        throw new Error('DEFAULT_HEADERS Content-Type must be a non-empty string');
    }
    defaultContentTypeCache = contentType;
    return defaultContentTypeCache;
};

const MESSAGE_KEYS: readonly string[] = ['message', 'error_message', 'error', 'detail', 'description', 'title', 'error_description'];
const ERR_DETAIL_MAP: readonly [string, keyof APIErrorMetadata][] = [
    ['message', 'detail'],
    ['reason', 'reason'],
    ['cause', 'cause'],
    ['data', 'data'],
    ['trace_id', 'traceId'],
    ['task_id', 'taskId']
];

const NETWORK_FAILURE_THRESHOLD = 2;

export { ERR_DETAIL_MAP, LOGOUT_ENDPOINT, MESSAGE_KEYS, NETWORK_FAILURE_THRESHOLD, getApiRequestTimeoutMs, getCoreModuleTimeoutMs, getDefaultContentType, getDefaultHeaders, type APIErrorMetadata };
