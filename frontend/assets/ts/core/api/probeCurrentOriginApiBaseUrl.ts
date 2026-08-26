/* SoAI - API health probing for configured and current origins [frontend/assets/ts/core/api/probeCurrentOriginApiBaseUrl.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortSignalScope, isAbortError } from '@core/errors/abort.ts';
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
    const { timeoutMs = 1500, healthEndpoint = DEFAULT_HEALTH_ENDPOINT, signal } = options;
    const originBaseUrl = normalizeProbeBaseUrl(baseUrl);
    if (originBaseUrl === null) return null;

    const controller = new AbortController();
    const signalScope = createAbortSignalScope([controller.signal, signal]);
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(`${originBaseUrl}${healthEndpoint}`, {
            method: 'GET',
            credentials: 'include',
            cache: 'no-store',
            signal: signalScope.signal
        });
        if (!response.ok) {
            return null;
        }
        const contentType = response.headers.get('content-type') || '';
        if (!contentType.includes('application/json')) {
            return null;
        }
        const payload = parseRequiredJsonText(await response.text());
        if (!payload || !isObject(payload)) return null;
        try {
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
        if (signal?.aborted) throw ensureError(error);
        if (isAbortError(error)) return null;
        throw ensureError(error);
    } finally {
        clearTimeout(timeoutId);
        signalScope.cleanup();
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
