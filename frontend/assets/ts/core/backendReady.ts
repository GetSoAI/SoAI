/* SoAI - Shared frontend backend ready [frontend/assets/ts/core/backendReady.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getConnectionState } from '@core/connectionstate/service.ts';
import { getApiClient } from '@core/api/service.ts';
import { isFunction } from '@core/typeGuards.ts';

interface ApiClient {
    whenReady: (options: { allowDiscovery: boolean; signal?: AbortSignal }) => Promise<string>;
}

interface EnsureBackendReadyOptions {
    allowDiscovery?: boolean | undefined;
    signal?: AbortSignal | undefined;
}

interface BackendReadyResult {
    api: ApiClient;
    baseUrl: string;
}

type ApiClientCandidate = {
    readonly whenReady?: ApiClient['whenReady'];
};

const isApiClientCandidate = <T>(value: T): value is T & ApiClientCandidate => typeof value === 'object' && value !== null;

const isApiClient = <T>(value: T): value is T & ApiClient => isApiClientCandidate(value) && isFunction(value.whenReady);

const resolveBackendApiClient = (): ApiClient => {
    const api = getApiClient();
    if (!isApiClient(api)) {
        throw new Error('API client must expose whenReady');
    }
    return api;
};

const ensureBackendReady = async (options: EnsureBackendReadyOptions = {}): Promise<BackendReadyResult> => {
    const allowDiscovery = options.allowDiscovery !== false;
    const signal = options.signal;

    const api = resolveBackendApiClient();
    const whenReadyOptions: { allowDiscovery: boolean; signal?: AbortSignal } = { allowDiscovery };
    if (signal !== undefined) {
        whenReadyOptions.signal = signal;
    }
    await api.whenReady(whenReadyOptions);

    const connectionState = getConnectionState();
    if (!isFunction(connectionState.hasBaseUrl) || !isFunction(connectionState.whenReady) || !isFunction(connectionState.getBaseUrl)) {
        throw new Error('Connection state must expose base URL accessors');
    }

    if (!connectionState.hasBaseUrl()) {
        const connReadyOptions: { signal?: AbortSignal } = {};
        if (signal !== undefined) {
            connReadyOptions.signal = signal;
        }
        await connectionState.whenReady(connReadyOptions);
    }

    const baseUrl = connectionState.getBaseUrl();
    if (!baseUrl) {
        throw new Error('Backend base URL is unavailable');
    }

    return { api, baseUrl };
};

export { ensureBackendReady };

export type { EnsureBackendReadyOptions, BackendReadyResult, ApiClient };
