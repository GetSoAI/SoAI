/* SoAI - API health probing for configured and current origins [frontend/assets/ts/core/api/probeCurrentOriginApiBaseUrl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getApiRequestTimeoutMs } from '@core/api/constants.ts';
import { TimeoutTimer } from '@core/timers/timeoutTimer.ts';
import { throwIfAborted, createAbortSignalScope } from '@core/errors/abort.ts';
import { APIError, isNetworkError } from '@core/apiError.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { getLocation } from '@core/environment/public.ts';
import { parseRequiredJsonText } from '@core/serialization/json.ts';
import { isObject } from '@core/typeGuards.ts';
import { decodeRuntimeEndpointHealthPayload } from '@core/discoveryservice/runtimeEndpointPayload.ts';
import type { DiscoveredEndpoint } from '@core/discoveryservice/selection.ts';
import { assertBackendEdition, BackendEditionIntegrityError } from '@core/edition/backendEditionIntegrity.ts';

const DEFAULT_HEALTH_ENDPOINT = '/api/v1/system/health';

const normalizeProbeBaseUrl = (baseUrl: string): string | null => {
    try {
        const parsed = new URL(baseUrl);
        if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
            return null;
        }
        const pathname = parsed.pathname.replace(/\/+$/, '');
        return pathname ? `${parsed.origin}${pathname}` : parsed.origin;
    } catch (error) {
        errorHandler.debug('ApiClient', 'API base URL probe normalization failed', ensureError(error));
        return null;
    }
};

export const probeApiEndpoint = async (baseUrl: string, options: { timeoutMs?: number | undefined; healthEndpoint?: string | undefined; signal?: AbortSignal | undefined } = {}): Promise<DiscoveredEndpoint | null> => {
    const { timeoutMs = getApiRequestTimeoutMs(), healthEndpoint = DEFAULT_HEALTH_ENDPOINT, signal } = options;
    const originBaseUrl = normalizeProbeBaseUrl(baseUrl);
    if (originBaseUrl === null) return null;

    throwIfAborted(signal);
    const controller = new AbortController();
    const scope = createAbortSignalScope([controller.signal, signal]);
    let timeoutTriggered = false;
    const timer = new TimeoutTimer(timeoutMs, () => {
        timeoutTriggered = true;
        controller.abort();
    });
    timer.start();
    try {
        const response = await fetch(`${originBaseUrl}${healthEndpoint}`, {
            method: 'GET',
            credentials: 'include',
            cache: 'no-store',
            signal: scope.signal
        });
        if (!response.ok) {
            if (response.status === 401 || response.status === 403 || response.status === 408 || response.status === 429 || response.status >= 500) {
                throw new APIError(response.status, 'Endpoint health probe failed', { endpoint: originBaseUrl });
            }
            return null;
        }
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            return null;
        }
        const body = await response.text();
        try {
            const payload = parseRequiredJsonText(body);
            if (!payload || !isObject(payload)) return null;
            const endpoint = decodeRuntimeEndpointHealthPayload(payload);
            assertBackendEdition(endpoint.edition);
            return {
                ...endpoint,
                baseUrl: originBaseUrl
            };
        } catch (error) {
            const runtimeError = ensureError(error);
            if (runtimeError instanceof BackendEditionIntegrityError) throw runtimeError;
            errorHandler.debug('ApiClient', 'API health response runtime endpoint contract was invalid', runtimeError);
            return null;
        }
    } catch (error) {
        const runtimeError = ensureError(error);
        if (signal?.aborted) throw ensureError(error);
        if (timeoutTriggered) throw new APIError(0, 'Request timed out', { cause: runtimeError, endpoint: originBaseUrl });
        if (runtimeError instanceof TypeError || isNetworkError(runtimeError)) throw new APIError(0, runtimeError.message, { cause: runtimeError, endpoint: originBaseUrl });
        throw runtimeError;
    } finally {
        timer.stop();
        scope.cleanup();
    }
};

export const probeApiBaseUrl = async (baseUrl: string, options: { timeoutMs?: number | undefined; healthEndpoint?: string | undefined; signal?: AbortSignal | undefined } = {}): Promise<string | null> => {
    const endpoint = await probeApiEndpoint(baseUrl, options);
    return endpoint?.baseUrl ?? null;
};

export const probeCurrentOriginApiEndpoint = async (options: { timeoutMs?: number | undefined; healthEndpoint?: string | undefined; signal?: AbortSignal | undefined } = {}): Promise<DiscoveredEndpoint | null> => {
    const loc = getLocation();
    const protocol = loc.protocol;
    if (protocol !== 'http:' && protocol !== 'https:') return null;
    return probeApiEndpoint(`${protocol}//${loc.host}`, options);
};

export const probeCurrentOriginApiBaseUrl = async (options: { timeoutMs?: number | undefined; healthEndpoint?: string | undefined; signal?: AbortSignal | undefined } = {}): Promise<string | null> => {
    const endpoint = await probeCurrentOriginApiEndpoint(options);
    return endpoint?.baseUrl ?? null;
};
