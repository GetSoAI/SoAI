/* SoAI - Frontend MCP management boundary contracts [frontend/assets/ts/core/api/contracts/mcpManagementContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { OpaqueJsonObject } from '@core/api/contracts/opaquePayload.ts';
import { decodeOauthStatus } from '@core/api/contracts/oauthContracts.ts';
import type { McpConnection, McpInteractionEntry, McpOauthStartResponse, McpOauthStatusResponse, McpPromptEntry, McpResourceEntry, McpRootEntry, McpRootsResponse, McpSearchKeyEntry, McpSearchKeysResponse, McpServer, McpServerConnectionResponse, McpServerCreateResponse, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import { readRequiredMcpServerAuthType, readRequiredMcpServerTransportType } from '@core/mcp/serverValues.ts';
import { readRequiredStringArrayValue, readNullableStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { readNullableFiniteNumberValue, readRequiredFiniteNumberValue } from '@core/types/payloadNumberReaders.ts';
import { readJsonObjectArrayOrEmptyValue, readNullableJsonObjectValue, readNullableStringRecordValue, readRequiredJsonObjectArrayValue, requireRecord } from '@core/types/payloadRecordReaders.ts';
import { readNullableTrimmedStringValue, readRequiredBooleanValue, readRequiredEnumValue, readRequiredNonEmptyStringValue, readRequiredTrimmedString, readRequiredTrimmedStringValue } from '@core/types/payloadValueReaders.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

const decodeRecordArray = (value: ApiResponsePayload, label: string): JsonObject[] => readRequiredJsonObjectArrayValue(value, label);

const decodeMcpStatus = (value: ApiResponsePayload): McpStatus => {
    const record = requireRecord(value, 'MCP status response');
    const hostMode = requireRecord(record['host_mode'], 'MCP status.host_mode');
    const serverMode = requireRecord(record['server_mode'], 'MCP status.server_mode');
    return {
        enabled: readRequiredBooleanValue(record['enabled'], 'MCP status.enabled'),
        hostMode: {
            enabled: readRequiredBooleanValue(hostMode['enabled'], 'MCP status.host_mode.enabled'),
            connectedServers: readRequiredFiniteNumberValue(hostMode['connected_servers'], 'MCP status.host_mode.connected_servers'),
            totalServers: readRequiredFiniteNumberValue(hostMode['total_servers'], 'MCP status.host_mode.total_servers'),
            connectionEntries: readRequiredFiniteNumberValue(hostMode['connection_entries'], 'MCP status.host_mode.connection_entries')
        },
        serverMode: {
            enabled: readRequiredBooleanValue(serverMode['enabled'], 'MCP status.server_mode.enabled'),
            active: readRequiredBooleanValue(serverMode['active'], 'MCP status.server_mode.active'),
            toolsCount: readRequiredFiniteNumberValue(serverMode['tools_count'], 'MCP status.server_mode.tools_count'),
            resourcesCount: readRequiredFiniteNumberValue(serverMode['resources_count'], 'MCP status.server_mode.resources_count')
        }
    };
};

const decodeMcpServer = (value: ApiResponsePayload, index: number): McpServer => {
    const label = `MCP server[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        id: readRequiredNonEmptyStringValue(record['id'], `${label}.id`),
        name: readRequiredNonEmptyStringValue(record['name'], `${label}.name`),
        transportType: readRequiredMcpServerTransportType(record['transport_type'] ?? null, `${label}.transport_type`),
        endpoint: readRequiredNonEmptyStringValue(record['endpoint'], `${label}.endpoint`),
        inputArguments: readNullableStringArrayValue(record['args'] ?? null, `${label}.args`),
        env: readNullableStringRecordValue(record['env'] ?? null, `${label}.env`),
        headers: readNullableStringRecordValue(record['headers'] ?? null, `${label}.headers`),
        authType: readRequiredMcpServerAuthType(record['auth_type'] ?? null, `${label}.auth_type`),
        apiKeyMasked: readNullableTrimmedStringValue(record['api_key_masked'], `${label}.api_key_masked`),
        oauthStatus: readNullableTrimmedStringValue(record['oauth_status'], `${label}.oauth_status`),
        oauthClientId: readNullableTrimmedStringValue(record['oauth_client_id'], `${label}.oauth_client_id`),
        oauthHasClientSecret: readRequiredBooleanValue(record['oauth_has_client_secret'], `${label}.oauth_has_client_secret`),
        oauthHasAccessToken: readRequiredBooleanValue(record['oauth_has_access_token'], `${label}.oauth_has_access_token`),
        oauthHasRefreshToken: readRequiredBooleanValue(record['oauth_has_refresh_token'], `${label}.oauth_has_refresh_token`),
        oauthExpiresAtMs: readNullableFiniteNumberValue(record['oauth_expires_at_ms'], `${label}.oauth_expires_at_ms`),
        oauthScopes: readNullableStringArrayValue(record['oauth_scopes'], `${label}.oauth_scopes`),
        oauthRequiredScopes: readNullableStringArrayValue(record['oauth_required_scopes'], `${label}.oauth_required_scopes`),
        timeoutMs: readNullableFiniteNumberValue(record['timeout_ms'], `${label}.timeout_ms`),
        autoReconnect: readRequiredBooleanValue(record['auto_reconnect'], `${label}.auto_reconnect`),
        enabled: readRequiredBooleanValue(record['enabled'], `${label}.enabled`),
        status: readNullableTrimmedStringValue(record['status'], `${label}.status`),
        lastError: readNullableTrimmedStringValue(record['last_error'], `${label}.last_error`),
        createdAtMs: readNullableFiniteNumberValue(record['created_at_ms'], `${label}.created_at_ms`),
        lastModifiedAtMs: readNullableFiniteNumberValue(record['last_modified_at_ms'], `${label}.last_modified_at_ms`)
    };
};

const decodeMcpServers = (value: ApiResponsePayload): McpServer[] => decodeRecordArray(value, 'MCP servers response').map(decodeMcpServer);

const decodeMcpConnection = (value: JsonValue, index: number): McpConnection => {
    const label = `MCP connection[${String(index)}]`;
    const record = requireRecord(value, label);
    return {
        id: readRequiredNonEmptyStringValue(record['id'], `${label}.id`),
        name: readRequiredNonEmptyStringValue(record['name'], `${label}.name`),
        transportType: readRequiredMcpServerTransportType(record['transport_type'] ?? null, `${label}.transport_type`),
        endpoint: readRequiredNonEmptyStringValue(record['endpoint'], `${label}.endpoint`),
        status: readRequiredNonEmptyStringValue(record['status'], `${label}.status`),
        toolsCount: readNullableFiniteNumberValue(record['tools_count'], `${label}.tools_count`),
        resourcesCount: readNullableFiniteNumberValue(record['resources_count'], `${label}.resources_count`),
        connectedAtMs: readNullableFiniteNumberValue(record['connected_at_ms'], `${label}.connected_at_ms`),
        lastError: readNullableTrimmedStringValue(record['last_error'], `${label}.last_error`)
    };
};

const decodeMcpConnections = (value: ApiResponsePayload): McpConnection[] => decodeRecordArray(value, 'MCP connections response').map(decodeMcpConnection);

const decodeMcpSearchKey = (value: ApiResponsePayload, index: number): McpSearchKeyEntry => {
    const label = `MCP search key[${String(index)}]`;
    const record = requireRecord(value, label);
    return { provider: readRequiredNonEmptyStringValue(record['provider'], `${label}.provider`), apiKeyMasked: readNullableTrimmedStringValue(record['api_key_masked'], `${label}.api_key_masked`), source: readNullableTrimmedStringValue(record['source'], `${label}.source`) };
};

const decodeMcpSearchKeys = (value: ApiResponsePayload): McpSearchKeysResponse => {
    const record = requireRecord(value, 'MCP search keys response');
    return { keys: readRequiredJsonObjectArrayValue(record['keys'], 'MCP search keys response.keys').map(decodeMcpSearchKey), providers: readRequiredStringArrayValue(record['providers'], 'MCP search keys response.providers') };
};

const decodeMcpRoot = (value: JsonValue, index: number): McpRootEntry => {
    const label = `MCP root[${String(index)}]`;
    const record = requireRecord(value, label);
    return { uri: readRequiredNonEmptyStringValue(record['uri'], `${label}.uri`), name: readNullableTrimmedStringValue(record['name'], `${label}.name`) };
};

const decodeMcpRoots = (value: ApiResponsePayload): McpRootsResponse => {
    const record = requireRecord(value, 'MCP roots response');
    return { roots: readRequiredJsonObjectArrayValue(record['roots'], 'MCP roots response.roots').map(decodeMcpRoot) };
};

const decodeMcpInteraction = (value: JsonValue, index: number): McpInteractionEntry => {
    const label = `MCP interaction[${String(index)}]`;
    const record = requireRecord(value, label);
    return { taskId: readRequiredNonEmptyStringValue(record['task_id'], `${label}.task_id`), method: readNullableTrimmedStringValue(record['method'], `${label}.method`), clientId: readNullableTrimmedStringValue(record['client_id'], `${label}.client_id`), status: readNullableTrimmedStringValue(record['status'], `${label}.status`), createdAtMs: readNullableFiniteNumberValue(record['created_at_ms'], `${label}.created_at_ms`), parameters: readNullableJsonObjectValue(record['params'], `${label}.params`) };
};

const decodeMcpInteractions = (value: ApiResponsePayload): McpInteractionEntry[] => decodeRecordArray(value, 'MCP interactions response').map(decodeMcpInteraction);

const decodeMcpInteractionResolve = (value: ApiResponsePayload): OpaqueJsonObject => requireRecord(value, 'MCP interaction resolve response');

const decodeCatalogEntry = (value: JsonValue, index: number, type: 'tool' | 'prompt'): McpToolEntry => {
    const label = `MCP ${type}[${String(index)}]`;
    const record = requireRecord(value, label);
    return { name: readRequiredNonEmptyStringValue(record['name'], `${label}.name`), description: readNullableTrimmedStringValue(record['description'], `${label}.description`), serverId: readNullableTrimmedStringValue(record['server_id'], `${label}.server_id`), serverName: readRequiredTrimmedStringValue(record['server_name'], `${label}.server_name`), icons: readJsonObjectArrayOrEmptyValue(record['icons'], `${label}.icons`) };
};

const decodeMcpTools = (value: ApiResponsePayload): McpToolEntry[] => decodeRecordArray(value, 'MCP tools response').map((entry, index) => decodeCatalogEntry(entry, index, 'tool'));
const decodeMcpPrompts = (value: ApiResponsePayload): McpPromptEntry[] => decodeRecordArray(value, 'MCP prompts response').map((entry, index) => decodeCatalogEntry(entry, index, 'prompt'));

const decodeMcpResource = (value: JsonValue, index: number): McpResourceEntry => {
    const label = `MCP resource[${String(index)}]`;
    const record = requireRecord(value, label);
    return { uri: readRequiredNonEmptyStringValue(record['uri'], `${label}.uri`), name: readNullableTrimmedStringValue(record['name'], `${label}.name`), description: readNullableTrimmedStringValue(record['description'], `${label}.description`), mimeType: readNullableTrimmedStringValue(record['mime_type'], `${label}.mime_type`), serverId: readNullableTrimmedStringValue(record['server_id'], `${label}.server_id`), serverName: readRequiredTrimmedStringValue(record['server_name'], `${label}.server_name`), icons: readJsonObjectArrayOrEmptyValue(record['icons'], `${label}.icons`) };
};

const decodeMcpResources = (value: ApiResponsePayload): McpResourceEntry[] => decodeRecordArray(value, 'MCP resources response').map(decodeMcpResource);

const decodeMcpServerCreate = (value: ApiResponsePayload): McpServerCreateResponse => {
    const record = requireRecord(value, 'MCP server create response');
    return { id: readRequiredTrimmedString(record, 'id', 'MCP server create response.id'), name: readRequiredTrimmedString(record, 'name', 'MCP server create response.name'), status: readRequiredEnumValue(record['status'], 'MCP server create response.status', ['created']) };
};

const decodeMcpServerConnection = (value: ApiResponsePayload): McpServerConnectionResponse => {
    const record = requireRecord(value, 'MCP server connection response');
    return { status: readRequiredEnumValue(record['status'], 'MCP server connection response.status', ['connected', 'disconnected']), serverId: readRequiredTrimmedString(record, 'server_id', 'MCP server connection response.server_id') };
};

const decodeMcpOauthStart = (value: ApiResponsePayload): McpOauthStartResponse => {
    const record = requireRecord(value, 'MCP OAuth start response');
    const status = readRequiredEnumValue(record['status'], 'MCP OAuth start response.status', ['not_required', 'manual_required', 'redirect', 'error']);
    if (status === 'redirect') return { status, redirectUrl: readRequiredTrimmedString(record, 'redirect_url', 'MCP OAuth start response.redirect_url') };
    if (status === 'error') return { status, error: record['error'] === undefined ? null : record['error'] };
    return { status };
};

const decodeMcpOauthStatus = (value: ApiResponsePayload): McpOauthStatusResponse => {
    const record = requireRecord(value, 'MCP OAuth status response');
    return { oauthStatus: decodeOauthStatus(record['oauth_status'], 'MCP OAuth status response.oauth_status'), expiresAtMs: readNullableFiniteNumberValue(record['expires_at_ms'], 'MCP OAuth status response.expires_at_ms'), requiredScopesPresent: readRequiredBooleanValue(record['required_scopes_present'], 'MCP OAuth status response.required_scopes_present'), lastError: readNullableTrimmedStringValue(record['last_error'], 'MCP OAuth status response.last_error') };
};

const decodeMcpOauthClear = (value: ApiResponsePayload): { status: 'cleared' } => {
    const record = requireRecord(value, 'MCP OAuth clear response');
    return { status: readRequiredEnumValue(record['status'], 'MCP OAuth clear response.status', ['cleared']) };
};

export { decodeMcpConnections, decodeMcpInteractionResolve, decodeMcpInteractions, decodeMcpOauthClear, decodeMcpOauthStart, decodeMcpOauthStatus, decodeMcpPrompts, decodeMcpResources, decodeMcpRoots, decodeMcpSearchKey, decodeMcpSearchKeys, decodeMcpServer, decodeMcpServerConnection, decodeMcpServerCreate, decodeMcpServers, decodeMcpStatus, decodeMcpTools };
