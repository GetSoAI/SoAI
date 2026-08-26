/* SoAI - Shared frontend MCP tool catalog [frontend/assets/ts/core/mcp/toolCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { getCurrentLocale } from '@core/languageservice/service.ts';
import type { McpServerGroup, McpTool } from '@core/mcp/configTypes.ts';
import { isMcpToolServerEnabled, normalizeMcpServerId, normalizeServerName } from '@core/mcp/serverSettings.ts';

const isToolAvailable = (tool: McpTool, serverConfigs: Record<string, boolean>): boolean => {
    if (!tool.allowed) {
        return false;
    }
    return isMcpToolServerEnabled(tool.serverId, serverConfigs);
};

const buildServerGroups = (inputArguments: { serverConfigs: Record<string, boolean>; tools: readonly McpTool[]; includeBuiltin: boolean }): McpServerGroup[] => {
    const groups = new Map<string, McpServerGroup>();
    inputArguments.tools.forEach((tool) => {
        const serverId = normalizeMcpServerId(tool.serverId);
        if ((tool.isBuiltin || serverId === 'builtin') && !inputArguments.includeBuiltin) {
            return;
        }
        const serverName = normalizeServerName(tool.serverName);
        const name = serverName ? serverName : serverId === 'builtin' ? i18n.t('chat.configuration.mcp.builtinServer') : serverId;
        const existing = groups.get(serverId);
        if (existing) {
            existing.tools.push(tool);
            return;
        }
        groups.set(serverId, { id: serverId, name, tools: [tool] });
    });
    Object.keys(inputArguments.serverConfigs).forEach((serverId) => {
        const trimmed = serverId.trim();
        if (!trimmed) {
            return;
        }
        const normalizedId = normalizeMcpServerId(trimmed);
        if (!inputArguments.includeBuiltin && normalizedId === 'builtin') {
            return;
        }
        if (groups.has(normalizedId)) {
            return;
        }
        const name = normalizedId === 'builtin' ? i18n.t('chat.configuration.mcp.builtinServer') : normalizedId;
        groups.set(normalizedId, { id: normalizedId, name, tools: [] });
    });
    return Array.from(groups.values()).sort((left, right) => left.name.localeCompare(right.name, getCurrentLocale()));
};

export { buildServerGroups, isToolAvailable };
