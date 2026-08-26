/* SoAI - Shared API client [frontend/assets/ts/core/api/types/apiClient.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiRequestBody } from '@core/api/types/request.ts';

interface DiscoveryServiceRef {
    discoverEndpoint(
        hostname?: string,
        targetInstanceId?: string | null
    ): Promise<{
        readonly baseUrl: string;
        readonly instanceId: string;
    }>;
    reset?(): void;
}

interface AuthManagerContract {
    isAuthenticated: boolean;
    logout?: () => void | Promise<void>;
}

interface FetchConfigInput {
    method?: string;
    headers?: Record<string, string>;
    body?: ApiRequestBody;
    signal?: AbortSignal | undefined;
    cache?: RequestCache | undefined;
    credentials?: RequestCredentials | undefined;
    keepalive?: boolean | undefined;
    includeCsrfHeader?: boolean | undefined;
}

interface FetchConfig {
    method: string;
    headers: Record<string, string>;
    credentials: RequestCredentials;
    cache: RequestCache;
    keepalive?: boolean;
    signal?: AbortSignal;
    body?: BodyInit;
}

export type { AuthManagerContract, DiscoveryServiceRef, FetchConfig, FetchConfigInput };
