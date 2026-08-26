/* SoAI - Settings feature MCP server form rules [frontend/assets/ts/features/settings/mcp/mcpServerFormRules.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { MCP_SERVER_AUTH_API_KEY, MCP_SERVER_AUTH_NONE, MCP_SERVER_AUTH_OAUTH, MCP_SERVER_TRANSPORT_STREAMABLE_HTTP, type McpServerAuthType, type McpServerTransportType } from '@core/mcp/serverValues.ts';

const MCP_SERVER_TIMEOUT_MIN_SECONDS = 5;
const MCP_SERVER_TIMEOUT_MAX_SECONDS = 300;
const MCP_SERVER_TIMEOUT_DEFAULT_SECONDS = 30;

const isMcpServerStreamableHttp = (transportType: string | null | undefined): boolean => transportType === MCP_SERVER_TRANSPORT_STREAMABLE_HTTP;

const isMcpServerOauthAuth = (authType: string | null | undefined): boolean => authType === MCP_SERVER_AUTH_OAUTH;

const isMcpServerApiKeyAuth = (authType: string | null | undefined): boolean => authType === MCP_SERVER_AUTH_API_KEY;

const isMcpServerNoneAuth = (authType: string | null | undefined): boolean => authType === MCP_SERVER_AUTH_NONE;

const isMcpServerOauthFlow = (transportType: string, authType: string): boolean => isMcpServerStreamableHttp(transportType) && isMcpServerOauthAuth(authType);

const isMcpServerApiKeyVisible = (transportType: string, authType: string): boolean => isMcpServerStreamableHttp(transportType) && isMcpServerApiKeyAuth(authType);

const resolveMcpServerDefaultAuthType = (transportType: string): McpServerAuthType => (isMcpServerStreamableHttp(transportType) ? MCP_SERVER_AUTH_OAUTH : MCP_SERVER_AUTH_NONE);

const isMcpServerAuthTransitionTo = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType, targetAuthType: McpServerAuthType): boolean => {
    return payloadAuthType === targetAuthType && baselineAuthType !== targetAuthType;
};

const isMcpServerAuthTransitionFrom = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType, sourceAuthType: McpServerAuthType): boolean => {
    return payloadAuthType !== sourceAuthType && baselineAuthType === sourceAuthType;
};

const isMcpServerAuthTransitionToApiKey = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType): boolean => {
    return isMcpServerAuthTransitionTo(payloadAuthType, baselineAuthType, MCP_SERVER_AUTH_API_KEY);
};

const isMcpServerAuthTransitionFromApiKey = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType): boolean => {
    return isMcpServerAuthTransitionFrom(payloadAuthType, baselineAuthType, MCP_SERVER_AUTH_API_KEY);
};

const isMcpServerAuthTransitionToOauth = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType): boolean => {
    return isMcpServerAuthTransitionTo(payloadAuthType, baselineAuthType, MCP_SERVER_AUTH_OAUTH);
};

const isMcpServerAuthTransitionFromOauth = (payloadAuthType: McpServerAuthType, baselineAuthType: McpServerAuthType): boolean => {
    return isMcpServerAuthTransitionFrom(payloadAuthType, baselineAuthType, MCP_SERVER_AUTH_OAUTH);
};

const resolveCreatedMcpServerAuthType = (authType: McpServerAuthType, apiKey: string | null): McpServerAuthType => {
    return isMcpServerApiKeyAuth(authType) && apiKey ? MCP_SERVER_AUTH_API_KEY : MCP_SERVER_AUTH_NONE;
};

const hasMcpServerNoneAuthApiKeyConflict = (transportType: McpServerTransportType, authType: McpServerAuthType, apiKey: string | null): boolean => {
    return isMcpServerStreamableHttp(transportType) && isMcpServerNoneAuth(authType) && apiKey !== null;
};

const isMcpServerApiKeyRequired = (transportType: McpServerTransportType, authType: McpServerAuthType, apiKey: string | null, baselineAuthType: McpServerAuthType | null): boolean => {
    return isMcpServerApiKeyVisible(transportType, authType) && apiKey === null && !isMcpServerApiKeyAuth(baselineAuthType);
};

export { MCP_SERVER_TIMEOUT_DEFAULT_SECONDS, MCP_SERVER_TIMEOUT_MAX_SECONDS, MCP_SERVER_TIMEOUT_MIN_SECONDS, hasMcpServerNoneAuthApiKeyConflict, isMcpServerApiKeyAuth, isMcpServerApiKeyRequired, isMcpServerApiKeyVisible, isMcpServerAuthTransitionFromApiKey, isMcpServerAuthTransitionFromOauth, isMcpServerAuthTransitionToApiKey, isMcpServerAuthTransitionToOauth, isMcpServerNoneAuth, isMcpServerOauthAuth, isMcpServerOauthFlow, isMcpServerStreamableHttp, resolveCreatedMcpServerAuthType, resolveMcpServerDefaultAuthType };
