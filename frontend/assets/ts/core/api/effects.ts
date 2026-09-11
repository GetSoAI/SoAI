/* SoAI - Shared API effects [frontend/assets/ts/core/api/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { APIError, type APIErrorMetadata, type APIErrorMetadataValue } from '@core/apiError.ts';
import { createAbortScope, type ApiAbortScope } from '@core/api/abortScope.ts';
import { BufferedApiResponse } from '@core/api/bufferedResponse.ts';
import { shouldAttachCsrfHeader, syncCsrfTokenFromResponse } from '@core/api/csrf.ts';
import { buildApiErrorFromResponse } from '@core/api/errorResponses.ts';
import { buildFetchConfig, enrichApiErrorMetadataFromValue, normalizeMethod, normalizeRequestTimeoutMs, normalizeRuntimeErrorValue, parseResponsePayload } from '@core/api/mappers.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { clampPercent } from '@core/primitives/clampNumber.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isAbsoluteHttpUrl } from '@core/security/public.ts';
import { isNullOrUndefined } from '@core/typeGuards.ts';
import type { ApiQueryParameters, ApiRequestBody, RequestOptions, UploadProgress } from '@core/api/types/request.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { observeServerTimeResponse } from '@core/time/serverTimeClock.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { createScopedRawResponse } from '@core/api/scopedRawResponse.ts';

interface ApiRequestExecutorDependencies {
    defaultHeaders: Record<string, string>;
    whenReady: (options: { allowDiscovery: boolean; signal?: AbortSignal }) => Promise<string>;
    buildUrl: (endpoint: string, query: ApiQueryParameters | null) => string;
    getBaseUrl: () => string | null;
    resetNetworkErrorState: () => void;
    registerNetworkError: () => void;
    handleAuthenticationError: (error: APIErrorMetadataValue, endpoint: string) => Promise<void>;
    populateApiErrorDetail: (metadata: APIErrorMetadata, apiErrorDetail: JsonObject | null) => void;
}

const parseXmlHttpRequestHeaders = (headerValue: string): Headers => {
    const headers = new Headers();
    const lines = headerValue.split('\r\n');
    for (const line of lines) {
        const separatorIndex = line.indexOf(':');
        if (separatorIndex <= 0) {
            continue;
        }
        const key = line.slice(0, separatorIndex).trim();
        const value = line.slice(separatorIndex + 1).trim();
        if (!key) {
            continue;
        }
        headers.append(key, value);
    }
    return headers;
};

const resolveUploadProgressPayload = (event: ProgressEvent<EventTarget>): UploadProgress => {
    const totalBytes = event.lengthComputable && Number.isFinite(event.total) && event.total > 0 ? event.total : null;
    const loadedBytes = Number.isFinite(event.loaded) && event.loaded >= 0 ? event.loaded : 0;
    return {
        loadedBytes: loadedBytes,
        totalBytes: totalBytes,
        percent: totalBytes !== null ? clampPercent((loadedBytes / totalBytes) * 100) : null
    };
};

const executeXmlHttpRequestUpload = async (requestUrl: string, fetchConfig: RequestInit, requestBody: FormData, scope: ApiAbortScope, onUploadProgress: (progress: UploadProgress) => void): Promise<Response> => {
    const xhr = new XMLHttpRequest();
    const handleAbort = (): void => {
        xhr.abort();
    };
    if (scope.signal.aborted) {
        throw new DOMException('The operation was aborted.', 'AbortError');
    }
    scope.signal.addEventListener('abort', handleAbort, { once: true });
    try {
        return await new Promise<Response>((resolve, reject) => {
            xhr.open(String(fetchConfig.method), requestUrl, true);
            xhr.withCredentials = fetchConfig.credentials === 'include';
            const headers = new Headers(fetchConfig.headers);
            headers.forEach((value, key) => {
                xhr.setRequestHeader(key, value);
            });
            xhr.upload.onprogress = (event): void => {
                onUploadProgress(resolveUploadProgressPayload(event));
            };
            xhr.upload.onload = (event): void => {
                const progress = resolveUploadProgressPayload(event);
                onUploadProgress({ ...progress, percent: 100 });
            };
            xhr.onerror = (): void => {
                reject(new Error('Network request failed'));
            };
            xhr.onabort = (): void => {
                reject(new DOMException('The operation was aborted.', 'AbortError'));
            };
            xhr.onload = (): void => {
                resolve(
                    new Response(xhr.responseText, {
                        status: xhr.status,
                        statusText: xhr.statusText,
                        headers: parseXmlHttpRequestHeaders(xhr.getAllResponseHeaders())
                    })
                );
            };
            xhr.send(requestBody);
        });
    } finally {
        scope.signal.removeEventListener('abort', handleAbort);
    }
};

const executeApiRequest = async (method: string, endpoint: string, data: ApiRequestBody, options: RequestOptions, dependencies: ApiRequestExecutorDependencies): Promise<ApiResponsePayload> => {
    const { rawResponse = false, bufferRawResponse = false, headers: optionHeaders = {}, query = null, body: explicitBody, timeoutMs, onUploadProgress, authTransitionOwned = false, ...restOptions } = options;

    if (bufferRawResponse && !rawResponse) {
        throw new Error('Buffered raw responses require rawResponse');
    }

    const timeoutValue = normalizeRequestTimeoutMs(timeoutMs);
    const scope = createAbortScope(restOptions.signal, timeoutValue);
    let rawBodyOwnsScope = false;

    try {
        const observesServerTime = endpoint.startsWith('/api/');
        const isAbsoluteEndpoint = isAbsoluteHttpUrl(endpoint);
        if (!isAbsoluteEndpoint) {
            await dependencies.whenReady({ allowDiscovery: true, signal: scope.signal });
        }

        const requestUrl = dependencies.buildUrl(endpoint, query);
        const normalizedMethod = normalizeMethod(method);
        const methodAllowsBody = normalizedMethod !== 'GET' && normalizedMethod !== 'HEAD';
        const requestBody = explicitBody !== undefined ? explicitBody : methodAllowsBody && !isNullOrUndefined(data) ? data : undefined;
        const fetchConfig = buildFetchConfig({
            method: normalizedMethod,
            headers: { ...dependencies.defaultHeaders, ...optionHeaders },
            body: requestBody,
            credentials: restOptions.credentials,
            cache: restOptions.cache,
            keepalive: restOptions.keepalive,
            includeCsrfHeader: shouldAttachCsrfHeader(requestUrl, dependencies.getBaseUrl()),
            signal: scope.signal
        });
        const requestStartedAtMonotonicMs = monotonicMs();
        const response = fetchConfig.body instanceof FormData && typeof onUploadProgress === 'function' && fetchConfig.keepalive !== true ? await executeXmlHttpRequestUpload(requestUrl, fetchConfig, fetchConfig.body, scope, onUploadProgress) : await fetch(requestUrl, fetchConfig);
        if (scope.signal.aborted) {
            throw new DOMException('The operation was aborted.', 'AbortError');
        }
        const responseReceivedAtMonotonicMs = monotonicMs();
        syncCsrfTokenFromResponse(response);
        if (!isAbsoluteEndpoint && observesServerTime) observeServerTimeResponse(response, { requestStartedAtMonotonicMs, responseReceivedAtMonotonicMs });
        dependencies.resetNetworkErrorState();
        if (!response.ok) {
            throw await buildApiErrorFromResponse(response, dependencies);
        }
        if (!rawResponse) {
            return await parseResponsePayload(response);
        }
        if (!bufferRawResponse) {
            if (response.body === null) {
                return response;
            }
            const scopedResponse = createScopedRawResponse(response, scope, {
                registerNetworkError: dependencies.registerNetworkError
            });
            rawBodyOwnsScope = true;
            return scopedResponse;
        }
        const responseBody = await response.blob();
        if (scope.signal.aborted) {
            throw new DOMException('The operation was aborted.', 'AbortError');
        }
        return new BufferedApiResponse(response, responseBody);
    } catch (error) {
        if (error instanceof APIError) {
            if (error.status !== 0) {
                dependencies.resetNetworkErrorState();
            }
            if (!authTransitionOwned) {
                try {
                    await dependencies.handleAuthenticationError(error, endpoint);
                } catch (authError) {
                    errorHandler.warn('ApiClient', 'Authentication error handler failed', ensureError(authError));
                }
            }
            throw error;
        }

        const runtimeError = normalizeRuntimeErrorValue(error);
        const metadata: APIErrorMetadata = {};
        enrichApiErrorMetadataFromValue(metadata, runtimeError);
        if (!metadata.cause && runtimeError instanceof Error) {
            metadata.cause = runtimeError;
        }
        const aborted = scope.signal.aborted || isAbortError(runtimeError);
        if (!aborted || scope.timeoutTriggered) {
            dependencies.registerNetworkError();
        }
        const errorMessage = scope.timeoutTriggered ? 'Request timed out' : runtimeError instanceof Error && runtimeError.message ? runtimeError.message : 'Network request failed';
        const apiError = new APIError(0, errorMessage, metadata);
        if (aborted && !scope.timeoutTriggered) {
            apiError.name = 'AbortError';
        }
        throw apiError;
    } finally {
        if (!rawBodyOwnsScope) {
            scope.cleanup();
        }
    }
};

const fetchApiAsset = async (path: string, options: { timeout?: number; responseType?: 'text' | 'json' | 'blob'; signal?: AbortSignal } = {}): Promise<ApiResponsePayload> => {
    const { timeout = 30000, responseType = 'text', signal: externalSignal } = options;
    const scope = createAbortScope(externalSignal, normalizeRequestTimeoutMs(timeout));
    try {
        const response = await fetch(path, {
            method: 'GET',
            credentials: 'same-origin',
            cache: 'no-store',
            signal: scope.signal
        });
        if (!response.ok) {
            throw new APIError(response.status, `Asset fetch failed: ${path}`);
        }
        if (responseType === 'json') {
            return parseRequiredJsonText(await response.text());
        }
        if (responseType === 'blob') {
            return response.blob();
        }
        return response.text();
    } catch (error) {
        if (error instanceof APIError) {
            throw error;
        }
        if (isAbortError(error)) {
            throw error;
        }
        const runtimeError = normalizeRuntimeErrorValue(error);
        const errorMessage = runtimeError instanceof Error && runtimeError.message ? runtimeError.message : 'Asset fetch failed';
        throw new APIError(0, errorMessage, { cause: runtimeError });
    } finally {
        scope.cleanup();
    }
};

export { executeApiRequest, fetchApiAsset };
export type { ApiRequestExecutorDependencies };
