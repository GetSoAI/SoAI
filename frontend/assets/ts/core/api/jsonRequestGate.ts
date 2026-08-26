/* SoAI - Shared API JSON request gate [frontend/assets/ts/core/api/jsonRequestGate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, isAbortError, raceWithAbortSignal } from '@core/errors/abort.ts';
import { coerceErrorMessage } from '@core/errors/coerce.ts';
import { stableJsonStringify } from '@core/serialization/json.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';

interface JsonApiClient {
    request(method: string, endpoint: string, body?: ApiRequestBody, options?: { signal?: AbortSignal; headers?: Record<string, string> }): Promise<ApiResponsePayload>;
}

interface JsonRequestOptions {
    method?: string;
    body?: ApiRequestBody;
    signal: AbortSignal;
    headers?: Record<string, string>;
}

interface InFlightJsonRequest {
    controller: AbortController;
    promise: Promise<ApiResponsePayload>;
    waiterTotal: number;
}

class HttpRequestError extends Error {
    readonly status: number;
    readonly statusText: string;
    readonly url: string;

    constructor(inputArguments: { url: string; status: number; statusText: string }) {
        const suffix = inputArguments.statusText ? ` ${inputArguments.statusText}` : '';
        super(`Request failed (${inputArguments.status}${suffix})`);
        this.name = 'HttpRequestError';
        this.status = inputArguments.status;
        this.statusText = inputArguments.statusText;
        this.url = inputArguments.url;
    }
}

const isHttpRequestError = (error: Error): error is HttpRequestError => error instanceof HttpRequestError;

const resolveJsonRequestKey = (url: string, options: JsonRequestOptions): string => {
    return stableJsonStringify({
        method: (options.method ?? 'GET').toUpperCase(),
        url,
        headers: options.headers ?? {},
        body: options.body ?? null
    });
};

const fetchJson = async (apiClient: JsonApiClient, url: string, options: JsonRequestOptions): Promise<ApiResponsePayload> => {
    try {
        const requestOptions: { signal?: AbortSignal; headers?: Record<string, string> } = {
            signal: options.signal,
            headers: options.headers ?? {}
        };
        return await apiClient.request(options.method ?? 'GET', url, options.body, requestOptions);
    } catch (error) {
        if (isAbortError(error)) {
            throw error;
        }
        if (error instanceof Error && 'status' in error && typeof error['status'] === 'number') {
            throw new HttpRequestError({
                url,
                status: error['status'],
                statusText: coerceErrorMessage(error, '')
            });
        }
        throw error;
    }
};

class JsonRequestGate {
    readonly #inFlightByRequestKey = new Map<string, InFlightJsonRequest>();
    readonly #apiClient: JsonApiClient;

    constructor(options: { apiClient: JsonApiClient }) {
        this.#apiClient = options.apiClient;
    }

    async requestJson(url: string, options: JsonRequestOptions): Promise<ApiResponsePayload> {
        if (options.signal.aborted) {
            throw createAbortError();
        }
        const requestKey = resolveJsonRequestKey(url, options);
        const existing = this.#inFlightByRequestKey.get(requestKey);
        if (existing) {
            if (!existing.controller.signal.aborted) {
                return await this.#joinInFlightRequest(existing, options.signal);
            }
            this.#deleteInFlightRequest(requestKey, existing);
        }

        const controller = new AbortController();
        const requestOptions: JsonRequestOptions = {
            ...options,
            signal: controller.signal
        };
        const promise = fetchJson(this.#apiClient, url, requestOptions);
        const entry: InFlightJsonRequest = {
            controller,
            promise,
            waiterTotal: 0
        };
        void promise.then(
            () => this.#deleteInFlightRequest(requestKey, entry),
            () => this.#deleteInFlightRequest(requestKey, entry)
        );
        this.#inFlightByRequestKey.set(requestKey, entry);
        return await this.#joinInFlightRequest(entry, options.signal);
    }

    async #joinInFlightRequest(entry: InFlightJsonRequest, signal: AbortSignal): Promise<ApiResponsePayload> {
        entry.waiterTotal += 1;
        try {
            return await raceWithAbortSignal(entry.promise, signal);
        } finally {
            this.#removeWaiter(entry);
        }
    }

    #removeWaiter(entry: InFlightJsonRequest): void {
        entry.waiterTotal = Math.max(0, entry.waiterTotal - 1);
        if (entry.waiterTotal === 0 && !entry.controller.signal.aborted) {
            entry.controller.abort();
        }
    }

    #deleteInFlightRequest(requestKey: string, entry: InFlightJsonRequest): void {
        if (this.#inFlightByRequestKey.get(requestKey) === entry) {
            this.#inFlightByRequestKey.delete(requestKey);
        }
    }
}

export { fetchJson, isHttpRequestError, JsonRequestGate };
export type { JsonApiClient, JsonRequestOptions };
