/* SoAI - Shared frontend MCP server settings [frontend/assets/ts/core/mcp/serverSettings.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const BUILTIN_MCP_SERVER_ID = 'builtin';

const normalizeServerName = (value: string | null): string | null => {
    if (!value) {
        return null;
    }
    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }
    if (trimmed.toLowerCase() === 'unknown') {
        return null;
    }
    return trimmed;
};

const isBuiltinServerId = (value: string): boolean => {
    const normalized = value.trim().toLowerCase();
    return normalized === BUILTIN_MCP_SERVER_ID || normalized === 'unknown';
};

const normalizeMcpServerId = (value: string): string => {
    const trimmed = value.trim();
    return isBuiltinServerId(trimmed) ? BUILTIN_MCP_SERVER_ID : trimmed;
};

const isServerEnabled = (serverId: string, serverConfigs: Record<string, boolean>): boolean => serverConfigs[serverId] !== false;

const isMcpToolServerEnabled = (serverId: string, serverConfigs: Record<string, boolean>): boolean => {
    const normalized = normalizeMcpServerId(serverId);
    if (!normalized) {
        return false;
    }
    return isServerEnabled(normalized, serverConfigs);
};

export { BUILTIN_MCP_SERVER_ID, isBuiltinServerId, isMcpToolServerEnabled, isServerEnabled, normalizeMcpServerId, normalizeServerName };
