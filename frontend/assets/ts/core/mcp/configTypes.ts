/* SoAI - Shared MCP configuration types [frontend/assets/ts/core/mcp/configTypes.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';

type McpToolMode = 'default' | 'plan' | 'execute';

type McpConfigBase<TKnowledgeState = JsonValue | null> = {
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
    serverConfigs: Record<string, boolean>;
    toolsEnabled: boolean;
    toolApprovalRequired: boolean;
    knowledgeState: TKnowledgeState;
};

type McpConfig<TKnowledgeState = JsonValue | null> = McpConfigBase<TKnowledgeState>;

type McpFormValues = {
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
    serverConfigs: Record<string, boolean>;
    toolsEnabled: boolean;
    toolApprovalRequired: boolean;
};

type McpTool = {
    name: string;
    definition: JsonObject | null;
    source: string | null;
    serverId: string;
    serverName: string | null;
    allowed: boolean;
    blockedReason: string | null;
    isBuiltin: boolean;
    knowledgeRole: string | null;
    icons: JsonObject[];
};

type McpCanonicalToolDefaults = {
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
};

type McpFormCatalog = {
    tools: readonly McpTool[];
    defaultTools: readonly string[];
    planTools: readonly string[];
    executeTools: readonly string[];
};

type McpServerGroup = {
    id: string;
    name: string;
    tools: McpTool[];
};

export type { McpCanonicalToolDefaults, McpConfig, McpConfigBase, McpFormCatalog, McpFormValues, McpServerGroup, McpTool, McpToolMode };
