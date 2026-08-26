/* SoAI - Shared realtime stream manager effects [frontend/assets/ts/core/realtime/streammanager/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeEndpoint } from '@core/realtime/streammanager/streamEndpoint.ts';
import type { EnsureApiReadyOptions } from '@core/realtime/streammanager/types.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';

interface StreamApiHost {
    ensureApiReady: (options: EnsureApiReadyOptions) => Promise<string>;
    request: (method: string, endpoint: string, body: ApiRequestBody, options: { headers: Record<string, string>; signal?: AbortSignal; rawResponse: boolean }) => Promise<ApiResponsePayload>;
}

interface StreamRequestOptions {
    method?: string;
    body?: ApiRequestBody;
    headers?: Record<string, string>;
    allowDiscovery?: boolean;
    signal?: AbortSignal | null;
}

const requestStreamTransport = async (host: StreamApiHost, endpoint: string, options: StreamRequestOptions, rawResponse: boolean): Promise<ApiResponsePayload> => {
    const normalizedEndpoint = normalizeEndpoint(endpoint);
    if (!normalizedEndpoint.absolute) {
        const ensureOptions: EnsureApiReadyOptions = {
            ...(typeof options.allowDiscovery === 'boolean' ? { allowDiscovery: options.allowDiscovery } : {}),
            ...(options.signal ? { signal: options.signal } : {})
        };
        await host.ensureApiReady(ensureOptions);
    }
    const requestOptions: { headers: Record<string, string>; signal?: AbortSignal; rawResponse: boolean } = {
        headers: options.headers || {},
        rawResponse,
        ...(options.signal ? { signal: options.signal } : {})
    };
    return host.request(options.method || 'GET', normalizedEndpoint.endpoint, options.body ?? null, requestOptions);
};

const requestStreamResponse = async (host: StreamApiHost, endpoint: string, options: StreamRequestOptions = {}): Promise<Response> => {
    const response = await requestStreamTransport(host, endpoint, options, true);
    if (!(response instanceof Response)) {
        throw new Error('Expected raw Response from ApiClient.request({ rawResponse: true })');
    }
    return response;
};

const fetchStreamPayload = (host: StreamApiHost, endpoint: string, options: StreamRequestOptions = {}): Promise<ApiResponsePayload> => requestStreamTransport(host, endpoint, options, false);

export { fetchStreamPayload, requestStreamResponse };
export type { StreamApiHost, StreamRequestOptions };
