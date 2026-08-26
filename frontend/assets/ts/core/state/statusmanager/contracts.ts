/* SoAI - Shared state status manager contracts [frontend/assets/ts/core/state/statusmanager/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import type { DomService, ErrorHandler } from '@core/state/types.ts';
import type { StatusInput, StatusKey, StatusStreamSnapshot, StreamManagerForStatus } from '@core/state/statusTypes.ts';

type StreamManager = StreamManagerForStatus;

interface BackendPayload {
    states?: Record<
        string,
        Partial<{
            name: JsonValue;
            color: JsonValue;
            description: JsonValue;
            group: JsonValue;
        }>
    >;
    default?: string;
    allowedColors?: string[];
    tags?: {
        active?: JsonValue;
        error?: JsonValue;
        transition?: JsonValue;
    };
}

interface AuthService {
    onLogin(callback: () => void): () => void;
    onLogout(callback: () => void): () => void;
    isAuthenticated: boolean;
}

interface ApiClient {
    system?: {
        stateDefinitions?: () => Promise<BackendPayload | null>;
    };
}

interface StatusManagerOptions {
    dom: DomService;
    errorHandler: ErrorHandler;
    statusStreamId: string;
    apiClientProvider: () => Promise<ApiClient | null>;
    authServiceProvider: () => Promise<AuthService>;
    streamManagerProvider: () => StreamManager;
}

type StatusStreamCallback = (status: StatusInput) => void;

export type { BackendPayload, StatusManagerOptions, StreamManager, AuthService, ApiClient, StatusStreamCallback };
export type { StatusInput, StatusKey, StatusStreamSnapshot, StreamManagerForStatus };
