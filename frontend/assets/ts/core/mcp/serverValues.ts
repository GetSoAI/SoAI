/* SoAI - Shared frontend MCP server values [frontend/assets/ts/core/mcp/serverValues.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isAllowedStringValue, readRequiredEnumValue } from '@core/types/payloadValueReaders.ts';

const MCP_SERVER_TRANSPORT_STDIO = 'stdio';
const MCP_SERVER_TRANSPORT_STREAMABLE_HTTP = 'streamable_http';
const MCP_SERVER_AUTH_NONE = 'none';
const MCP_SERVER_AUTH_API_KEY = 'api_key';
const MCP_SERVER_AUTH_OAUTH = 'oauth';

const MCP_SERVER_TRANSPORT_TYPES: readonly [typeof MCP_SERVER_TRANSPORT_STDIO, typeof MCP_SERVER_TRANSPORT_STREAMABLE_HTTP] = [MCP_SERVER_TRANSPORT_STDIO, MCP_SERVER_TRANSPORT_STREAMABLE_HTTP];
const MCP_SERVER_AUTH_TYPES: readonly [typeof MCP_SERVER_AUTH_NONE, typeof MCP_SERVER_AUTH_API_KEY, typeof MCP_SERVER_AUTH_OAUTH] = [MCP_SERVER_AUTH_NONE, MCP_SERVER_AUTH_API_KEY, MCP_SERVER_AUTH_OAUTH];

type McpServerTransportType = (typeof MCP_SERVER_TRANSPORT_TYPES)[number];
type McpServerAuthType = (typeof MCP_SERVER_AUTH_TYPES)[number];

const isMcpServerTransportType = (value: JsonValue): value is McpServerTransportType => isAllowedStringValue(value, MCP_SERVER_TRANSPORT_TYPES);

const isMcpServerAuthType = (value: JsonValue): value is McpServerAuthType => isAllowedStringValue(value, MCP_SERVER_AUTH_TYPES);

const readRequiredMcpServerTransportType = (value: JsonValue, label: string): McpServerTransportType => readRequiredEnumValue(value, label, MCP_SERVER_TRANSPORT_TYPES);

const readRequiredMcpServerAuthType = (value: JsonValue, label: string): McpServerAuthType => readRequiredEnumValue(value, label, MCP_SERVER_AUTH_TYPES);

const isMcpServerAuthCompatibleWithTransport = (transportType: McpServerTransportType, authType: McpServerAuthType): boolean => {
    return transportType === MCP_SERVER_TRANSPORT_STREAMABLE_HTTP || authType === MCP_SERVER_AUTH_NONE;
};

export { MCP_SERVER_AUTH_API_KEY, MCP_SERVER_AUTH_NONE, MCP_SERVER_AUTH_OAUTH, MCP_SERVER_TRANSPORT_STDIO, MCP_SERVER_TRANSPORT_STREAMABLE_HTTP, isMcpServerAuthCompatibleWithTransport, isMcpServerAuthType, isMcpServerTransportType, readRequiredMcpServerAuthType, readRequiredMcpServerTransportType };
export type { McpServerAuthType, McpServerTransportType };
