/* SoAI - Settings feature MCP server payloads [frontend/assets/ts/features/settings/mcp/mcpServerPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { deepEqual } from '@core/primitives/equality.ts';
import type { McpServer, McpServerCreatePayload, McpServerUpdatePayload } from '@core/mcp/contracts.ts';
import { isMcpServerApiKeyAuth, isMcpServerAuthTransitionFromApiKey, isMcpServerAuthTransitionFromOauth, isMcpServerAuthTransitionToApiKey, isMcpServerAuthTransitionToOauth, isMcpServerOauthAuth } from '@features/settings/mcp/mcpServerFormRules.ts';
import type { McpServerFormData } from '@features/settings/mcp/mcpManagerTypes.ts';

const buildMcpServerUpdates = (payload: McpServerFormData, baseline: McpServer): McpServerUpdatePayload => {
    const isAuthTypeTransitionToApiKey = isMcpServerAuthTransitionToApiKey(payload.authType, baseline.authType);
    const isAuthTypeTransitionFromApiKey = isMcpServerAuthTransitionFromApiKey(payload.authType, baseline.authType);
    const isAuthTypeTransitionToOauth = isMcpServerAuthTransitionToOauth(payload.authType, baseline.authType);
    const isAuthTypeTransitionFromOauth = isMcpServerAuthTransitionFromOauth(payload.authType, baseline.authType);

    const updates: McpServerUpdatePayload = {};
    if (payload.name !== baseline.name) updates.name = payload.name;
    if (payload.transportType !== baseline.transportType) updates.transportType = payload.transportType;
    if (payload.endpoint !== baseline.endpoint) updates.endpoint = payload.endpoint;
    if (payload.authType !== baseline.authType) updates.authType = payload.authType;
    if (!deepEqual(payload.timeoutMs, baseline.timeoutMs)) updates.timeoutMs = payload.timeoutMs;
    if (payload.autoReconnect !== baseline.autoReconnect) updates.autoReconnect = payload.autoReconnect;
    if (payload.enabled !== baseline.enabled) updates.enabled = payload.enabled;
    if (!deepEqual(payload.inputArguments, baseline.inputArguments)) updates.inputArguments = payload.inputArguments;
    if (!deepEqual(payload.env, baseline.env)) updates.env = payload.env;
    if (!deepEqual(payload.headers, baseline.headers)) updates.headers = payload.headers;

    if (isAuthTypeTransitionToApiKey) {
        if (payload.apiKey) updates.apiKey = payload.apiKey;
    } else if (isAuthTypeTransitionFromApiKey) {
        updates.apiKey = null;
    }

    if (isAuthTypeTransitionToOauth) {
        if (payload.oauthClientId) {
            updates.oauthClientId = payload.oauthClientId;
        }
        if (payload.oauthClientSecret) {
            updates.oauthClientSecret = payload.oauthClientSecret;
        }
        return updates;
    }

    if (isMcpServerApiKeyAuth(payload.authType)) {
        if (payload.apiKey) {
            updates.apiKey = payload.apiKey;
        }
    }

    if (isMcpServerOauthAuth(payload.authType)) {
        if (payload.oauthClientId !== baseline.oauthClientId) updates.oauthClientId = payload.oauthClientId;
        if (payload.oauthClientSecret) updates.oauthClientSecret = payload.oauthClientSecret;
    } else if (isAuthTypeTransitionFromOauth) {
        updates.oauthClientId = null;
        updates.oauthClientSecret = null;
    }
    return updates;
};

const buildMcpServerCreatePayload = (payload: McpServerFormData): McpServerCreatePayload => {
    const createPayload: McpServerCreatePayload = {
        name: payload.name,
        transportType: payload.transportType,
        endpoint: payload.endpoint,
        autoReconnect: payload.autoReconnect
    };
    if (payload.timeoutMs !== null) createPayload.timeoutMs = payload.timeoutMs;
    if (payload.inputArguments) createPayload.inputArguments = payload.inputArguments;
    if (payload.env) createPayload.env = payload.env;
    if (payload.headers) createPayload.headers = payload.headers;
    if (isMcpServerApiKeyAuth(payload.authType) && payload.apiKey) createPayload.apiKey = payload.apiKey;
    return createPayload;
};

type McpServerFormBaselineOptions = {
    status?: string | null;
    apiKeyMasked?: string | null;
    oauthStatus?: string | null;
    oauthHasClientSecret?: boolean;
    oauthHasAccessToken?: boolean;
    oauthHasRefreshToken?: boolean;
    oauthExpiresAtMs?: number | null;
    oauthScopes?: string[] | null;
    oauthRequiredScopes?: string[] | null;
    createdAtMs?: number | null;
    lastModifiedAtMs?: number | null;
    lastError?: string | null;
};

const buildMcpServerFormBaseline = (payload: McpServerFormData, serverId: string, options: McpServerFormBaselineOptions = {}): McpServer => {
    return {
        id: serverId,
        name: payload.name,
        transportType: payload.transportType,
        endpoint: payload.endpoint,
        inputArguments: payload.inputArguments,
        env: payload.env,
        headers: payload.headers,
        authType: payload.authType,
        apiKeyMasked: options.apiKeyMasked ?? null,
        oauthStatus: options.oauthStatus ?? null,
        oauthClientId: payload.oauthClientId,
        oauthHasClientSecret: options.oauthHasClientSecret ?? payload.oauthClientSecret !== null,
        oauthHasAccessToken: options.oauthHasAccessToken ?? false,
        oauthHasRefreshToken: options.oauthHasRefreshToken ?? false,
        oauthExpiresAtMs: options.oauthExpiresAtMs ?? null,
        oauthScopes: options.oauthScopes ?? null,
        oauthRequiredScopes: options.oauthRequiredScopes ?? null,
        timeoutMs: payload.timeoutMs,
        autoReconnect: payload.autoReconnect,
        enabled: payload.enabled,
        status: options.status ?? null,
        lastError: options.lastError ?? null,
        createdAtMs: options.createdAtMs ?? null,
        lastModifiedAtMs: options.lastModifiedAtMs ?? null
    };
};

export { buildMcpServerCreatePayload, buildMcpServerFormBaseline, buildMcpServerUpdates };
