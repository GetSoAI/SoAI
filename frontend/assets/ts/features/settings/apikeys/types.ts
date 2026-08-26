/* SoAI - Settings feature apikeys contracts [frontend/assets/ts/features/settings/apikeys/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiKeyAssignmentResponse, ApiKeyCreateRequest, ApiKeyDeleteAllResponse, ApiKeyRevokeResponse, ApiKeySecretResponse } from '@core/api/contracts/apiKeyContracts.ts';
import type { ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import type { ToggleLabelState } from '@core/toggleSwitch.ts';
import type { DomEventHost, DomMutationHost, DomQueryHost, ExecutionHost, NotificationHost, SearchHost } from '@core/ui/controllerHosts.ts';
import type { ApiKey, ApiKeyQuotaSummary } from '@core/settings/contracts.ts';

interface ApiKeysManagerDependencies {
    host: ApiKeysManagerHost;
}

type ApiKeyOperation = 'revoke' | 'rotate' | 'delete';

interface ApiKeysManagerApiHost {
    isAdmin: () => boolean;
    listApiKeys: (includeRevoked: boolean) => Promise<ApiKey[]>;
    createApiKey: (payload: ApiKeyCreateRequest) => Promise<ApiKeySecretResponse>;
    revokeApiKey: (keyId: string) => Promise<ApiKeyRevokeResponse>;
    rotateApiKey: (keyId: string) => Promise<ApiKeySecretResponse>;
    deleteApiKey: (keyId: string) => Promise<void>;
    deleteAllApiKeys: () => Promise<ApiKeyDeleteAllResponse>;
    getApiKeyQuota: (keyId: string) => Promise<ApiKeyQuotaSummary>;
    updateApiKeyQuota: (keyId: string, payload: ApiKeyQuotaUpdateRequest) => Promise<ApiKeyQuotaSummary>;
    listApiKeyQuotaStatus: () => Promise<Record<string, ApiKeyQuotaSummary>>;
    assignApiKeyToUser: (keyId: string, userId: number) => Promise<ApiKeyAssignmentResponse>;
    unassignApiKeyFromUser: (keyId: string) => Promise<void>;
    listUsers: () => Promise<Array<{ id: number; username: string }>>;
    sanitizeHtml: (value: string) => string;
    sanitizeAttribute: (value: string | number) => string;
}

interface ApiKeysManagerDomHost extends DomQueryHost, DomEventHost, DomMutationHost {
    updatePreferenceToggleLabel: (element: Element, checked?: boolean) => void;
    setTimer: (callback: () => void, delayMs: number) => number | null;
    clearTimer: (timerId: number | null) => void;
}

interface ApiKeysManagerExecutionHost extends ExecutionHost {
    confirmAndExecute: NonNullable<ExecutionHost['confirmAndExecute']>;
}

interface ApiKeysManagerStateHost {
    getApiKeys: () => ApiKey[];
    setApiKeys: (keys: ApiKey[]) => void;
    getApiKeyQuotaSummaries: () => Record<string, ApiKeyQuotaSummary>;
    setApiKeyQuotaSummaries: (summaries: Record<string, ApiKeyQuotaSummary>) => void;
    getApiKeyQuotaSummary: (keyId: string) => ApiKeyQuotaSummary | null;
    getShowRevokedKeys: () => boolean;
    setShowRevokedKeys: (show: boolean) => void;
}

interface ApiKeysManagerHost {
    api: ApiKeysManagerApiHost;
    view: ApiKeysManagerDomHost;
    execution: ApiKeysManagerExecutionHost;
    notifications: NotificationHost;
    search: SearchHost;
    state: ApiKeysManagerStateHost;
}

interface ApiKeysViewRenderHost {
    api: Pick<ApiKeysManagerApiHost, 'isAdmin' | 'sanitizeHtml' | 'sanitizeAttribute'>;
    state: Pick<ApiKeysManagerStateHost, 'getApiKeys' | 'getShowRevokedKeys' | 'getApiKeyQuotaSummary'>;
}

type ApiKeysDomResolverHost = DomQueryHost;

export type { ApiKeysManagerDependencies, ApiKeyOperation, ApiKeysManagerHost, ApiKeysViewRenderHost, ApiKeysDomResolverHost, ApiKey, ToggleLabelState };
