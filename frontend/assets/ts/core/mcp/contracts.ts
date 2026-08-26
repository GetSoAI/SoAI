/* SoAI - Shared MCP contracts [frontend/assets/ts/core/mcp/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpServerAuthType, McpServerTransportType } from '@core/mcp/serverValues.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { OauthStatus } from '@core/api/contracts/oauthContracts.ts';

interface McpStatus {
    enabled: boolean;
    hostMode: {
        enabled: boolean;
        connectedServers: number;
        totalServers: number;
        connectionEntries: number;
    };
    serverMode: {
        enabled: boolean;
        active: boolean;
        toolsCount: number;
        resourcesCount: number;
    };
}

interface McpServer {
    id: string;
    name: string;
    transportType: McpServerTransportType;
    endpoint: string;
    inputArguments: string[] | null;
    env: Record<string, string> | null;
    headers: Record<string, string> | null;
    authType: McpServerAuthType;
    apiKeyMasked: string | null;
    oauthStatus: string | null;
    oauthClientId: string | null;
    oauthHasClientSecret: boolean;
    oauthHasAccessToken: boolean;
    oauthHasRefreshToken: boolean;
    oauthExpiresAtMs: number | null;
    oauthScopes: string[] | null;
    oauthRequiredScopes: string[] | null;
    timeoutMs: number | null;
    autoReconnect: boolean;
    enabled: boolean;
    status: string | null;
    lastError: string | null;
    createdAtMs: number | null;
    lastModifiedAtMs: number | null;
}

interface McpConnection {
    id: string;
    name: string;
    transportType: McpServerTransportType;
    endpoint: string;
    status: string;
    toolsCount: number | null;
    resourcesCount: number | null;
    connectedAtMs: number | null;
    lastError: string | null;
}

interface McpSearchKeyEntry {
    provider: string;
    apiKeyMasked: string | null;
    source: string | null;
}

interface McpRootEntry {
    uri: string;
    name: string | null;
}

interface McpToolEntry {
    name: string;
    description: string | null;
    serverId: string | null;
    serverName: string;
    icons: JsonObject[];
}

interface McpResourceEntry {
    uri: string;
    name: string | null;
    description: string | null;
    mimeType: string | null;
    serverId: string | null;
    serverName: string;
    icons: JsonObject[];
}

type McpPromptEntry = McpToolEntry;

interface McpInteractionEntry {
    taskId: string;
    method: string | null;
    clientId: string | null;
    status: string | null;
    createdAtMs: number | null;
    parameters: JsonObject | null;
}

interface McpServerCreatePayload {
    name: string;
    transportType: McpServerTransportType;
    endpoint: string;
    inputArguments?: string[] | null;
    env?: Record<string, string> | null;
    headers?: Record<string, string> | null;
    apiKey?: string | null;
    timeoutMs?: number;
    autoReconnect: boolean;
}

interface McpServerUpdatePayload {
    name?: string | null;
    transportType?: McpServerTransportType | null;
    endpoint?: string | null;
    inputArguments?: string[] | null;
    env?: Record<string, string> | null;
    headers?: Record<string, string> | null;
    authType?: McpServerAuthType | null;
    apiKey?: string | null;
    oauthClientId?: string | null;
    oauthClientSecret?: string | null;
    timeoutMs?: number | null;
    autoReconnect?: boolean | null;
    enabled?: boolean | null;
}

interface McpServerCreateResponse {
    id: string;
    name: string;
    status: 'created';
}

interface McpServerConnectionResponse {
    status: 'connected' | 'disconnected';
    serverId: string;
}

interface McpOauthStatusResponse {
    oauthStatus: OauthStatus;
    expiresAtMs: number | null;
    requiredScopesPresent: boolean;
    lastError: string | null;
}

type McpOauthStartResponse = { status: 'not_required' } | { status: 'manual_required' } | { status: 'redirect'; redirectUrl: string } | { status: 'error'; error: JsonValue | null };

interface McpSearchKeysResponse {
    keys: McpSearchKeyEntry[];
    providers: string[];
}

interface McpRootsResponse {
    roots: McpRootEntry[];
}

interface McpInteractionResolvePayload {
    action: McpInteractionAction;
    content?: JsonObject | null;
}

type McpInteractionAction = 'approve' | 'accept' | 'decline' | 'cancel';
type McpInteractionMode = 'sampling' | 'elicitation-form' | 'elicitation-url' | 'unknown';

interface McpInteractionConfig {
    actions: McpInteractionAction[];
    mode: McpInteractionMode;
}

interface McpDataBundle {
    status: McpStatus | null;
    servers: McpServer[];
    connections: McpConnection[];
    searchKeys: McpSearchKeyEntry[];
    searchProviders: string[];
    roots: McpRootEntry[];
    interactions: McpInteractionEntry[];
    tools: McpToolEntry[];
    resources: McpResourceEntry[];
    prompts: McpPromptEntry[];
}

export type { McpConnection, McpDataBundle, McpInteractionAction, McpInteractionConfig, McpInteractionEntry, McpInteractionMode, McpInteractionResolvePayload, McpOauthStartResponse, McpOauthStatusResponse, McpPromptEntry, McpResourceEntry, McpRootEntry, McpRootsResponse, McpSearchKeyEntry, McpSearchKeysResponse, McpServer, McpServerConnectionResponse, McpServerCreatePayload, McpServerCreateResponse, McpServerUpdatePayload, McpStatus, McpToolEntry };
