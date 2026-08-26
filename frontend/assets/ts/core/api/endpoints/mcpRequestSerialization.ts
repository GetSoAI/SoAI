/* SoAI - Frontend MCP request serialization [frontend/assets/ts/core/api/endpoints/mcpRequestSerialization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpInteractionResolvePayload, McpRootEntry, McpServerCreatePayload, McpServerUpdatePayload } from '@core/mcp/contracts.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';

const serializeMcpServerCreatePayload = (payload: McpServerCreatePayload): JsonObject => {
    const serialized: JsonObject = {
        name: payload.name,
        'transport_type': payload.transportType,
        endpoint: payload.endpoint,
        'auto_reconnect': payload.autoReconnect
    };
    if (payload.inputArguments !== undefined) serialized['args'] = payload.inputArguments;
    if (payload.env !== undefined) serialized['env'] = payload.env;
    if (payload.headers !== undefined) serialized['headers'] = payload.headers;
    if (payload.apiKey !== undefined) serialized['api_key'] = payload.apiKey;
    if (payload.timeoutMs !== undefined) serialized['timeout_ms'] = payload.timeoutMs;
    return serialized;
};

const serializeMcpServerUpdatePayload = (payload: McpServerUpdatePayload): JsonObject => {
    const serialized: JsonObject = {};
    if (payload.name !== undefined) serialized['name'] = payload.name;
    if (payload.transportType !== undefined) serialized['transport_type'] = payload.transportType;
    if (payload.endpoint !== undefined) serialized['endpoint'] = payload.endpoint;
    if (payload.inputArguments !== undefined) serialized['args'] = payload.inputArguments;
    if (payload.env !== undefined) serialized['env'] = payload.env;
    if (payload.headers !== undefined) serialized['headers'] = payload.headers;
    if (payload.authType !== undefined) serialized['auth_type'] = payload.authType;
    if (payload.apiKey !== undefined) serialized['api_key'] = payload.apiKey;
    if (payload.oauthClientId !== undefined) serialized['oauth_client_id'] = payload.oauthClientId;
    if (payload.oauthClientSecret !== undefined) serialized['oauth_client_secret'] = payload.oauthClientSecret;
    if (payload.timeoutMs !== undefined) serialized['timeout_ms'] = payload.timeoutMs;
    if (payload.autoReconnect !== undefined) serialized['auto_reconnect'] = payload.autoReconnect;
    if (payload.enabled !== undefined) serialized['enabled'] = payload.enabled;
    return serialized;
};

const serializeMcpRoots = (roots: readonly McpRootEntry[]): JsonObject => ({
    roots: roots.map((root) => ({ uri: root.uri, name: root.name }))
});

const serializeMcpInteractionResolvePayload = (payload: McpInteractionResolvePayload): JsonObject => {
    const serialized: JsonObject = { action: payload.action };
    if (payload.content !== undefined) serialized['content'] = payload.content;
    return serialized;
};

const serializeMcpSearchApiKey = (apiKey: string): JsonObject => ({ 'api_key': apiKey });

export { serializeMcpInteractionResolvePayload, serializeMcpRoots, serializeMcpSearchApiKey, serializeMcpServerCreatePayload, serializeMcpServerUpdatePayload };
