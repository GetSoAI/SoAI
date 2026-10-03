/* SoAI - Shared API MCP [frontend/assets/ts/core/api/endpoints/mcp.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClientContext } from '@core/api/types/apiClientContext.ts';
import { decodeMcpConnections, decodeMcpInteractionResolve, decodeMcpInteractions, decodeMcpOauthClear, decodeMcpOauthStart, decodeMcpOauthStatus, decodeMcpPrompts, decodeMcpResources, decodeMcpRoots, decodeMcpSearchKey, decodeMcpSearchKeys, decodeMcpServer, decodeMcpServerConnection, decodeMcpServerCreate, decodeMcpServers, decodeMcpStatus, decodeMcpTools } from '@core/api/contracts/mcpManagementContracts.ts';
import { decodeNoContentResponse } from '@core/api/contracts/noContentContract.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import type { McpConnection, McpInteractionEntry, McpInteractionResolvePayload, McpOauthStartResponse, McpOauthStatusResponse, McpPromptEntry, McpResourceEntry, McpRootEntry, McpRootsResponse, McpSearchKeyEntry, McpSearchKeysResponse, McpServer, McpServerConnectionResponse, McpServerCreatePayload, McpServerCreateResponse, McpServerUpdatePayload, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import { serializeMcpInteractionResolvePayload, serializeMcpRoots, serializeMcpSearchApiKey, serializeMcpServerCreatePayload, serializeMcpServerUpdatePayload } from '@core/api/endpoints/mcpRequestSerialization.ts';
import { buildSignalRequestOptions, type SignalOptions } from '@core/api/requestOptions.ts';

const createMcpEndpoints = (
    api: ApiClientContext
): {
    status: (options?: SignalOptions) => Promise<McpStatus>;
    servers: { list: (options?: SignalOptions) => Promise<McpServer[]>; create: (payload: McpServerCreatePayload) => Promise<McpServerCreateResponse>; update: (id: string, payload: McpServerUpdatePayload) => Promise<McpServer>; delete: (id: string) => Promise<void>; connect: (id: string) => Promise<McpServerConnectionResponse>; disconnect: (id: string) => Promise<McpServerConnectionResponse> };
    oauth: { start: (id: string) => Promise<McpOauthStartResponse>; clear: (id: string) => Promise<{ status: 'cleared' }>; status: (id: string) => Promise<McpOauthStatusResponse> };
    connections: { list: (options?: SignalOptions) => Promise<McpConnection[]> };
    tools: { list: (options?: SignalOptions) => Promise<McpToolEntry[]> };
    resources: { list: (options?: SignalOptions) => Promise<McpResourceEntry[]> };
    prompts: { list: (options?: SignalOptions) => Promise<McpPromptEntry[]> };
    roots: { get: (options?: SignalOptions) => Promise<McpRootsResponse>; update: (payload: { roots: McpRootEntry[] }) => Promise<McpRootsResponse> };
    interactions: { list: (options?: SignalOptions) => Promise<McpInteractionEntry[]>; resolve: (id: string, payload: McpInteractionResolvePayload) => Promise<OpaqueJsonObject> };
    searchApiKeys: { list: (options?: SignalOptions) => Promise<McpSearchKeysResponse>; set: (provider: string, payload: { apiKey: string }) => Promise<McpSearchKeyEntry>; delete: (provider: string) => Promise<void> };
} => {
    return {
        status: async (options: SignalOptions = {}): Promise<McpStatus> => decodeMcpStatus(await api.get('/api/v1/mcp/status', buildSignalRequestOptions(options))),
        servers: {
            list: async (options: SignalOptions = {}): Promise<McpServer[]> => decodeMcpServers(await api.get('/api/v1/mcp/servers', buildSignalRequestOptions(options))),
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
            list: async (options: SignalOptions = {}): Promise<McpConnection[]> => decodeMcpConnections(await api.get('/api/v1/mcp/connections', buildSignalRequestOptions(options)))
        },
        tools: {
            list: async (options: SignalOptions = {}): Promise<McpToolEntry[]> => decodeMcpTools(await api.get('/api/v1/mcp/tools', buildSignalRequestOptions(options)))
        },
        resources: {
            list: async (options: SignalOptions = {}): Promise<McpResourceEntry[]> => decodeMcpResources(await api.get('/api/v1/mcp/resources', buildSignalRequestOptions(options)))
        },
        prompts: {
            list: async (options: SignalOptions = {}): Promise<McpPromptEntry[]> => decodeMcpPrompts(await api.get('/api/v1/mcp/prompts', buildSignalRequestOptions(options)))
        },
        roots: {
            get: async (options: SignalOptions = {}): Promise<McpRootsResponse> => decodeMcpRoots(await api.get('/api/v1/mcp/client/roots', buildSignalRequestOptions(options))),
            update: async (payload): Promise<McpRootsResponse> => decodeMcpRoots(await api.put('/api/v1/mcp/client/roots', serializeMcpRoots(payload.roots)))
        },
        interactions: {
            list: async (options: SignalOptions = {}): Promise<McpInteractionEntry[]> => decodeMcpInteractions(await api.get('/api/v1/mcp/client/interactions', buildSignalRequestOptions(options))),
            resolve: async (id, payload): Promise<OpaqueJsonObject> => decodeMcpInteractionResolve(await api.post(`/api/v1/mcp/client/interactions/${api.encodePathSegment(id)}/resolve`, serializeMcpInteractionResolvePayload(payload)))
        },
        searchApiKeys: {
            list: async (options: SignalOptions = {}): Promise<McpSearchKeysResponse> => decodeMcpSearchKeys(await api.get('/api/v1/mcp/search-api-keys', buildSignalRequestOptions(options))),
            set: async (provider, payload): Promise<McpSearchKeyEntry> => decodeMcpSearchKey(await api.put(`/api/v1/mcp/search-api-keys/${api.encodePathSegment(provider)}`, serializeMcpSearchApiKey(payload.apiKey)), 0),
            delete: async (provider): Promise<void> => {
                decodeNoContentResponse(await api.delete(`/api/v1/mcp/search-api-keys/${api.encodePathSegment(provider)}`), 'MCP search API key delete response');
            }
        }
    };
};

export { createMcpEndpoints };
