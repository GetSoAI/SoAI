/* SoAI - Shared API MCP [frontend/assets/ts/core/api/endpoints/mcp.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeMcpConnections, decodeMcpInteractionResolve, decodeMcpInteractions, decodeMcpOauthClear, decodeMcpOauthStart, decodeMcpOauthStatus, decodeMcpPrompts, decodeMcpResources, decodeMcpRoots, decodeMcpSearchKey, decodeMcpSearchKeys, decodeMcpServer, decodeMcpServerConnection, decodeMcpServerCreate, decodeMcpServers, decodeMcpStatus, decodeMcpTools } from '@core/api/contracts/mcpManagementContracts.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import type { McpConnection, McpInteractionEntry, McpInteractionResolvePayload, McpOauthStartResponse, McpOauthStatusResponse, McpPromptEntry, McpResourceEntry, McpRootEntry, McpRootsResponse, McpSearchKeyEntry, McpSearchKeysResponse, McpServer, McpServerConnectionResponse, McpServerCreatePayload, McpServerCreateResponse, McpServerUpdatePayload, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import { serializeMcpInteractionResolvePayload, serializeMcpRoots, serializeMcpSearchApiKey, serializeMcpServerCreatePayload, serializeMcpServerUpdatePayload } from '@core/api/endpoints/mcpRequestSerialization.ts';

const createMcpEndpoints = (
    api: ApiClientContext
): {
    status: () => Promise<McpStatus>;
    servers: { list: () => Promise<McpServer[]>; create: (payload: McpServerCreatePayload) => Promise<McpServerCreateResponse>; update: (id: string, payload: McpServerUpdatePayload) => Promise<McpServer>; delete: (id: string) => Promise<void>; connect: (id: string) => Promise<McpServerConnectionResponse>; disconnect: (id: string) => Promise<McpServerConnectionResponse> };
    oauth: { start: (id: string) => Promise<McpOauthStartResponse>; clear: (id: string) => Promise<{ status: 'cleared' }>; status: (id: string) => Promise<McpOauthStatusResponse> };
    connections: { list: () => Promise<McpConnection[]> };
    tools: { list: () => Promise<McpToolEntry[]> };
    resources: { list: () => Promise<McpResourceEntry[]> };
    prompts: { list: () => Promise<McpPromptEntry[]> };
    roots: { get: () => Promise<McpRootsResponse>; update: (payload: { roots: McpRootEntry[] }) => Promise<McpRootsResponse> };
    interactions: { list: () => Promise<McpInteractionEntry[]>; resolve: (id: string, payload: McpInteractionResolvePayload) => Promise<OpaqueJsonObject> };
    searchApiKeys: { list: () => Promise<McpSearchKeysResponse>; set: (provider: string, payload: { apiKey: string }) => Promise<McpSearchKeyEntry>; delete: (provider: string) => Promise<void> };
} => {
    return {
        status: async (): Promise<McpStatus> => decodeMcpStatus(await api.get('/api/v1/mcp/status')),
        servers: {
            list: async (): Promise<McpServer[]> => decodeMcpServers(await api.get('/api/v1/mcp/servers')),
            create: async (payload): Promise<McpServerCreateResponse> => decodeMcpServerCreate(await api.post('/api/v1/mcp/servers', serializeMcpServerCreatePayload(payload))),
            update: async (id, payload): Promise<McpServer> => decodeMcpServer(await api.patch(`/api/v1/mcp/servers/${api.encodePathSegment(id)}`, serializeMcpServerUpdatePayload(payload)), 0),
            delete: async (id): Promise<void> => {
                decodeNoContentResponse(await api.delete(`/api/v1/mcp/servers/${api.encodePathSegment(id)}`), 'MCP server delete response');
            },
            connect: async (id): Promise<McpServerConnectionResponse> => decodeMcpServerConnection(await api.post(`/api/v1/mcp/servers/${api.encodePathSegment(id)}/connect`)),
            disconnect: async (id): Promise<McpServerConnectionResponse> => decodeMcpServerConnection(await api.post(`/api/v1/mcp/servers/${api.encodePathSegment(id)}/disconnect`))
        },
        oauth: {
            start: async (id): Promise<McpOauthStartResponse> => decodeMcpOauthStart(await api.post(`/api/v1/mcp/servers/${api.encodePathSegment(id)}/oauth/start`)),
            clear: async (id): Promise<{ status: 'cleared' }> => {
                return decodeMcpOauthClear(await api.post(`/api/v1/mcp/servers/${api.encodePathSegment(id)}/oauth/clear`));
            },
            status: async (id): Promise<McpOauthStatusResponse> => decodeMcpOauthStatus(await api.get(`/api/v1/mcp/servers/${api.encodePathSegment(id)}/oauth/status`))
        },
        connections: {
            list: async (): Promise<McpConnection[]> => decodeMcpConnections(await api.get('/api/v1/mcp/connections'))
        },
        tools: {
            list: async (): Promise<McpToolEntry[]> => decodeMcpTools(await api.get('/api/v1/mcp/tools'))
        },
        resources: {
            list: async (): Promise<McpResourceEntry[]> => decodeMcpResources(await api.get('/api/v1/mcp/resources'))
        },
        prompts: {
            list: async (): Promise<McpPromptEntry[]> => decodeMcpPrompts(await api.get('/api/v1/mcp/prompts'))
        },
        roots: {
            get: async (): Promise<McpRootsResponse> => decodeMcpRoots(await api.get('/api/v1/mcp/client/roots')),
            update: async (payload): Promise<McpRootsResponse> => decodeMcpRoots(await api.put('/api/v1/mcp/client/roots', serializeMcpRoots(payload.roots)))
        },
        interactions: {
            list: async (): Promise<McpInteractionEntry[]> => decodeMcpInteractions(await api.get('/api/v1/mcp/client/interactions')),
            resolve: async (id, payload): Promise<OpaqueJsonObject> => decodeMcpInteractionResolve(await api.post(`/api/v1/mcp/client/interactions/${api.encodePathSegment(id)}/resolve`, serializeMcpInteractionResolvePayload(payload)))
        },
        searchApiKeys: {
            list: async (): Promise<McpSearchKeysResponse> => decodeMcpSearchKeys(await api.get('/api/v1/mcp/search-api-keys')),
            set: async (provider, payload): Promise<McpSearchKeyEntry> => decodeMcpSearchKey(await api.put(`/api/v1/mcp/search-api-keys/${api.encodePathSegment(provider)}`, serializeMcpSearchApiKey(payload.apiKey)), 0),
            delete: async (provider): Promise<void> => {
                decodeNoContentResponse(await api.delete(`/api/v1/mcp/search-api-keys/${api.encodePathSegment(provider)}`), 'MCP search API key delete response');
            }
        }
    };
};

export { createMcpEndpoints };
