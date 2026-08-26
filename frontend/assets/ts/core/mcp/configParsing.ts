/* SoAI - Shared MCP configuration parsing [frontend/assets/ts/core/mcp/configParsing.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { assertNonEmptyString, requireBooleanValue } from '@core/assertions.ts';
import type { McpCanonicalToolDefaults, McpConfig, McpFormValues, McpTool } from '@core/mcp/configTypes.ts';
import { normalizeMcpServerId } from '@core/mcp/serverSettings.ts';
import { normalizeBooleanOrDefault, normalizeOptionalToolNameList, optionalStringValue, requireBooleanRecord, requireToolNameList } from '@core/mcp/valueNormalization.ts';
import { isNullOrUndefined, isString } from '@core/typeGuards.ts';
import { isJsonArray, isJsonObject, isJsonValue, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';

type OptionalJsonValue = JsonValue | undefined;
type McpKnowledgeStateParser<TKnowledgeState> = (value: OptionalJsonValue) => TKnowledgeState;

const requireMcpObject = (payload: OptionalJsonValue, message: string): JsonObject => {
    if (!isJsonObject(payload)) {
        throw new Error(message);
    }
    return payload;
};

const parseMcpConfigWithKnowledgeState = <TKnowledgeState>(payload: OptionalJsonValue, parseKnowledgeState: McpKnowledgeStateParser<TKnowledgeState>): McpConfig<TKnowledgeState> => {
    const record = requireMcpObject(payload, 'Invalid MCP config payload');
    const toolsEnabled = requireBooleanValue(record['tools_enabled'], 'TOOLS.MCP.tools_enabled', { message: 'Invalid TOOLS.MCP.tools_enabled' });
    return {
        defaultTools: requireToolNameList(record['default_tools'], 'TOOLS.MCP.default_tools'),
        planTools: normalizeOptionalToolNameList(record['plan_tools'], 'TOOLS.MCP.plan_tools'),
        executeTools: normalizeOptionalToolNameList(record['execute_tools'], 'TOOLS.MCP.execute_tools'),
        serverConfigs: requireBooleanRecord(record['server_configs'], 'TOOLS.MCP.server_configs'),
        toolsEnabled,
        toolApprovalRequired: normalizeBooleanOrDefault(record['tool_approval_required'], toolsEnabled, 'TOOLS.MCP.tool_approval_required'),
        knowledgeState: parseKnowledgeState(record['knowledge_state'])
    };
};

const parseMcpConfig = (payload: OptionalJsonValue): McpConfig => {
    return parseMcpConfigWithKnowledgeState(payload, (value) => {
        if (isNullOrUndefined(value)) {
            return null;
        }
        if (!isJsonValue(value)) {
            throw new Error('Invalid TOOLS.MCP.knowledge_state');
        }
        return value;
    });
};

const parseMcpFormValues = (payload: OptionalJsonValue): McpFormValues => {
    const record = requireMcpObject(payload, 'Invalid MCP config payload');
    const toolsEnabled = requireBooleanValue(record['tools_enabled'], 'TOOLS.MCP.tools_enabled', { message: 'Invalid TOOLS.MCP.tools_enabled' });
    return {
        defaultTools: requireToolNameList(record['default_tools'], 'TOOLS.MCP.default_tools'),
        planTools: normalizeOptionalToolNameList(record['plan_tools'], 'TOOLS.MCP.plan_tools'),
        executeTools: normalizeOptionalToolNameList(record['execute_tools'], 'TOOLS.MCP.execute_tools'),
        serverConfigs: requireBooleanRecord(record['server_configs'], 'TOOLS.MCP.server_configs'),
        toolsEnabled,
        toolApprovalRequired: normalizeBooleanOrDefault(record['tool_approval_required'], toolsEnabled, 'TOOLS.MCP.tool_approval_required')
    };
};

const parseMcpTool = (payload: OptionalJsonValue): McpTool => {
    const record = requireMcpObject(payload, 'Invalid MCP tool payload');
    const name = assertNonEmptyString(record['name'], 'TOOLS.MCP.tool.name', { message: 'Invalid TOOLS.MCP.tool.name' });
    const definition = isJsonObject(record['definition']) ? record['definition'] : null;
    const serverIdRaw = optionalStringValue(record['server_id'], 'TOOLS.MCP.tool.server_id');
    const source = optionalStringValue(record['source'], 'TOOLS.MCP.tool.source');
    let trimmedServerId: string | null = null;
    if (isString(serverIdRaw)) {
        const trimmed = serverIdRaw.trim();
        if (trimmed) {
            trimmedServerId = trimmed;
        }
    }
    const serverId = trimmedServerId ? normalizeMcpServerId(trimmedServerId) : 'builtin';
    const isBuiltin = source === 'builtin' || serverId === 'builtin';
    const serverName = optionalStringValue(record['server_name'], 'TOOLS.MCP.tool.server_name');
    const allowed = requireBooleanValue(record['allowed'], 'TOOLS.MCP.tool.allowed', { message: 'Invalid TOOLS.MCP.tool.allowed' });
    const blockedReason = optionalStringValue(record['blocked_reason'], 'TOOLS.MCP.tool.blocked_reason');
    const knowledgeRole = optionalStringValue(record['knowledge_role'], 'TOOLS.MCP.tool.knowledge_role');
    const iconsRaw = record['icons'];
    const icons: JsonObject[] = [];
    if (isJsonArray(iconsRaw)) {
        for (const icon of iconsRaw) {
            if (isJsonObject(icon)) {
                icons.push(icon);
            }
        }
    }
    return {
        name,
        definition,
        source,
        serverId,
        serverName,
        allowed,
        blockedReason,
        isBuiltin,
        knowledgeRole,
        icons
    };
};

const parseMcpToolList = (payload: OptionalJsonValue): McpTool[] => {
    const record = requireMcpObject(payload, 'Invalid MCP tools payload');
    const tools = record['tools'];
    if (!isJsonArray(tools)) {
        throw new Error('Invalid MCP tools payload');
    }
    return tools.map((entry) => parseMcpTool(entry));
};

const parseMcpCanonicalToolDefaults = (payload: OptionalJsonValue): McpCanonicalToolDefaults => {
    const record = requireMcpObject(payload, 'Invalid MCP tools payload');
    return {
        defaultTools: requireToolNameList(record['canonical_default_tools'], 'TOOLS.MCP.canonical_default_tools'),
        planTools: requireToolNameList(record['canonical_plan_tools'], 'TOOLS.MCP.canonical_plan_tools'),
        executeTools: requireToolNameList(record['canonical_execute_tools'], 'TOOLS.MCP.canonical_execute_tools')
    };
};

export { parseMcpCanonicalToolDefaults, parseMcpConfig, parseMcpConfigWithKnowledgeState, parseMcpFormValues, parseMcpToolList };
export type { McpKnowledgeStateParser };
