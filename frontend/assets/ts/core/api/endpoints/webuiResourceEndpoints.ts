/* SoAI - Shared API WebUI resource endpoints [frontend/assets/ts/core/api/endpoints/webuiResourceEndpoints.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodePromptBatchDeleteResponse, decodePromptListResponse, decodePromptResponse, serializePromptBatchDeleteRequest, serializePromptRequest, type PromptBatchDeleteResponse, type PromptRequest, type PromptResponse } from '@core/api/contracts/promptContracts.ts';
import { decodeMcpAccessTokenCreateResponse, decodeMcpAccessTokenRevokeResponse, decodeMcpAccessTokensListResponse, serializeMcpAccessTokenCreateRequest, type McpAccessTokenCreateRequest, type McpAccessTokenCreateResponse, type McpAccessTokenRevokeResponse, type McpAccessTokensListResponse } from '@core/api/contracts/mcpAccessTokenContracts.ts';
import { decodeWallpaperDownloadResponse, decodeWallpaperInfoResponse, decodeWallpaperUploadResponse, type WallpaperDownloadResponse, type WallpaperInfoResponse, type WallpaperUploadResponse } from '@core/api/contracts/wallpaperContracts.ts';
import { decodeAclPolicyResponse, serializeAclPolicyUpdateRequest, type AclPolicyOverrides, type AclPolicyResponse } from '@core/api/contracts/aclPolicyContracts.ts';
import { decodeApiKeyAssignmentResponse, decodeApiKeyDeleteAllResponse, decodeApiKeyListResponse, decodeApiKeyRevokeResponse, decodeApiKeySecretResponse, serializeApiKeyAssignmentRequest, serializeApiKeyCreateRequest, type ApiKeyAssignmentResponse, type ApiKeyCreateRequest, type ApiKeyDeleteAllResponse, type ApiKeyRevokeResponse, type ApiKeySecretResponse } from '@core/api/contracts/apiKeyContracts.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import { decodeApiKeyQuotaResponse, decodeApiKeyQuotaStatusListResponse, serializeApiKeyQuotaUpdateRequest, type ApiKeyQuotaUpdateRequest } from '@core/api/contracts/apiKeyQuotaContracts.ts';
import type { ApiKey, ApiKeyQuotaSummary } from '@core/settings/contracts.ts';
import { buildSignalRequestOptions, type SignalOptions } from '@core/api/requestOptions.ts';
import { FILE_TRANSFER_REQUEST_TIMEOUT_MS } from '@core/api/fileTransferTimeout.ts';
import { decodeNotificationRecord, type NotificationRecord } from '@core/api/contracts/notificationContracts.ts';
import { notificationOpenPath } from '@core/api/endpoints/uiPaths.ts';

interface WebuiResourceEndpoints {
    prompts: {
        list(): Promise<PromptResponse[]>;
        create(data: PromptRequest): Promise<PromptResponse>;
        get(id: string): Promise<PromptResponse>;
        update(id: string, data: PromptRequest): Promise<PromptResponse>;
        delete(id: string): Promise<void>;
        batchDelete(ids: string[]): Promise<PromptBatchDeleteResponse>;
    };
    wallpaper: {
        getStatus(): Promise<WallpaperInfoResponse>;
        upload(file: Blob): Promise<WallpaperUploadResponse>;
        download(url: string): Promise<WallpaperDownloadResponse>;
        delete(): Promise<void>;
    };
    apiKeys: {
        list(includeRevoked?: boolean): Promise<ApiKey[]>;
        create(payload: ApiKeyCreateRequest): Promise<ApiKeySecretResponse>;
        revoke(keyId: string): Promise<ApiKeyRevokeResponse>;
        rotate(keyId: string, payload?: ApiKeyCreateRequest): Promise<ApiKeySecretResponse>;
        delete(keyId: string): Promise<void>;
        deleteAll(): Promise<ApiKeyDeleteAllResponse>;
        getQuota(keyId: string): Promise<ApiKeyQuotaSummary>;
        updateQuota(keyId: string, payload: ApiKeyQuotaUpdateRequest): Promise<ApiKeyQuotaSummary>;
        listQuotaStatus(): Promise<Record<string, ApiKeyQuotaSummary>>;
        assignUser(keyId: string, userId: number): Promise<ApiKeyAssignmentResponse>;
        unassignUser(keyId: string): Promise<void>;
    };
    mcpAccessTokens: {
        list(): Promise<McpAccessTokensListResponse>;
        create(payload: McpAccessTokenCreateRequest): Promise<McpAccessTokenCreateResponse>;
        revoke(tokenId: string): Promise<McpAccessTokenRevokeResponse>;
    };
    acl: {
        getPolicy(options?: SignalOptions): Promise<AclPolicyResponse>;
        updatePolicy(overrides: AclPolicyOverrides): Promise<AclPolicyResponse>;
        resetPolicy(): Promise<void>;
    };
    notifications: {
        open(notificationId: string): Promise<NotificationRecord>;
    };
}

const createWebuiResourceEndpoints = (api: ApiClientContext): WebuiResourceEndpoints => ({
    prompts: {
        list: async (): Promise<PromptResponse[]> => decodePromptListResponse(await api.get('/api/v1/webui/prompts')),
        create: async (data): Promise<PromptResponse> => decodePromptResponse(await api.post('/api/v1/webui/prompts', serializePromptRequest(data))),
        get: async (id): Promise<PromptResponse> => decodePromptResponse(await api.get(`/api/v1/webui/prompts/${api.encodePathSegment(id)}`)),
        update: async (id, data): Promise<PromptResponse> => decodePromptResponse(await api.patch(`/api/v1/webui/prompts/${api.encodePathSegment(id)}`, serializePromptRequest(data))),
        delete: async (id): Promise<void> => {
            decodeNoContentResponse(await api.delete(`/api/v1/webui/prompts/${api.encodePathSegment(id)}`), 'Prompt delete response');
        },
        batchDelete: async (ids): Promise<PromptBatchDeleteResponse> => decodePromptBatchDeleteResponse(await api.post('/api/v1/webui/prompts/batch-delete', serializePromptBatchDeleteRequest(ids)))
    },
    wallpaper: {
        getStatus: async (): Promise<WallpaperInfoResponse> => decodeWallpaperInfoResponse(await api.get('/api/v1/webui/wallpaper')),
        upload: async (file): Promise<WallpaperUploadResponse> => decodeWallpaperUploadResponse(await api.uploadFile('/api/v1/webui/wallpaper/upload', file, { 'size_bytes': String(file.size) }, { timeoutMs: FILE_TRANSFER_REQUEST_TIMEOUT_MS })),
        download: async (url): Promise<WallpaperDownloadResponse> => decodeWallpaperDownloadResponse(await api.post('/api/v1/webui/wallpaper/download', { url })),
        delete: async (): Promise<void> => {
            decodeNoContentResponse(await api.delete('/api/v1/webui/wallpaper'), 'Wallpaper delete response');
        }
    },
    apiKeys: {
        list: async (includeRevoked = false): Promise<ApiKey[]> => decodeApiKeyListResponse(await api.get('/api/v1/webui/openai-api-keys', { query: { 'include_revoked': includeRevoked } })),
        create: async (payload): Promise<ApiKeySecretResponse> => decodeApiKeySecretResponse(await api.post('/api/v1/webui/openai-api-keys', serializeApiKeyCreateRequest(payload)), 'API key create response'),
        revoke: async (keyId): Promise<ApiKeyRevokeResponse> => decodeApiKeyRevokeResponse(await api.post(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/revoke`)),
        rotate: async (keyId, payload = {}): Promise<ApiKeySecretResponse> => decodeApiKeySecretResponse(await api.post(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/rotate`, serializeApiKeyCreateRequest(payload)), 'API key rotate response'),
        delete: async (keyId): Promise<void> => {
            decodeNoContentResponse(await api.delete(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}`), 'API key delete response');
        },
        deleteAll: async (): Promise<ApiKeyDeleteAllResponse> => decodeApiKeyDeleteAllResponse(await api.delete('/api/v1/webui/openai-api-keys')),
        getQuota: async (keyId): Promise<ApiKeyQuotaSummary> => decodeApiKeyQuotaResponse(await api.get(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/quota`)),
        updateQuota: async (keyId, payload): Promise<ApiKeyQuotaSummary> => decodeApiKeyQuotaResponse(await api.patch(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/quota`, serializeApiKeyQuotaUpdateRequest(payload))),
        listQuotaStatus: async (): Promise<Record<string, ApiKeyQuotaSummary>> => decodeApiKeyQuotaStatusListResponse(await api.get('/api/v1/webui/openai-api-keys/quota/status')),
        assignUser: async (keyId, userId): Promise<ApiKeyAssignmentResponse> => decodeApiKeyAssignmentResponse(await api.patch(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/assignment`, serializeApiKeyAssignmentRequest(userId))),
        unassignUser: async (keyId): Promise<void> => {
            decodeNoContentResponse(await api.delete(`/api/v1/webui/openai-api-keys/${api.encodePathSegment(keyId)}/assignment`), 'API key assignment delete response');
        }
    },
    mcpAccessTokens: {
        list: async (): Promise<McpAccessTokensListResponse> => decodeMcpAccessTokensListResponse(await api.get('/api/v1/webui/mcp-access-tokens')),
        create: async (payload): Promise<McpAccessTokenCreateResponse> => decodeMcpAccessTokenCreateResponse(await api.post('/api/v1/webui/mcp-access-tokens', serializeMcpAccessTokenCreateRequest(payload))),
        revoke: async (tokenId): Promise<McpAccessTokenRevokeResponse> => decodeMcpAccessTokenRevokeResponse(await api.post(`/api/v1/webui/mcp-access-tokens/${api.encodePathSegment(tokenId)}/revoke`))
    },
    acl: {
        getPolicy: async (options: SignalOptions = {}): Promise<AclPolicyResponse> => decodeAclPolicyResponse(await api.get('/api/v1/system/access-control/policy', buildSignalRequestOptions(options))),
        updatePolicy: async (overrides): Promise<AclPolicyResponse> => {
            return decodeAclPolicyResponse(await api.put('/api/v1/system/access-control/policy', serializeAclPolicyUpdateRequest(overrides)));
        },
        resetPolicy: async (): Promise<void> => {
            decodeNoContentResponse(await api.delete('/api/v1/system/access-control/policy'), 'ACL policy reset response');
        }
    },
    notifications: {
        open: async (notificationId): Promise<NotificationRecord> => decodeNotificationRecord(await api.post(notificationOpenPath(notificationId), {}))
    }
});

export { createWebuiResourceEndpoints };
export type { WebuiResourceEndpoints };
