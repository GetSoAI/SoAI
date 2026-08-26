/* SoAI - Shared agent mode MCP tool selection mapping [frontend/assets/ts/core/chat/agentModeMcpMapping.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AgentMode } from '@core/chat/agentMode.ts';
import type { McpToolMode } from '@core/mcp/configTypes.ts';

type AgentModeMcpToolField = 'defaultTools' | 'planTools' | 'executeTools';

type AgentModeMcpToolMapping = {
    toolMode: McpToolMode;
    toolField: AgentModeMcpToolField;
    requiresTools: boolean;
};

const AGENT_MODE_MCP_TOOL_MAPPING: Readonly<Record<AgentMode, AgentModeMcpToolMapping>> = Object.freeze({
    chat: Object.freeze({
        toolMode: 'default',
        toolField: 'defaultTools',
        requiresTools: false
    }),
    plan: Object.freeze({
        toolMode: 'plan',
        toolField: 'planTools',
        requiresTools: true
    }),
    execute: Object.freeze({
        toolMode: 'execute',
        toolField: 'executeTools',
        requiresTools: true
    })
});

const resolveMcpToolModeForAgentMode = (mode: AgentMode): McpToolMode => AGENT_MODE_MCP_TOOL_MAPPING[mode].toolMode;

const resolveMcpToolFieldForAgentMode = (mode: AgentMode): AgentModeMcpToolField => AGENT_MODE_MCP_TOOL_MAPPING[mode].toolField;

const doesAgentModeRequireMcpTools = (mode: AgentMode): boolean => AGENT_MODE_MCP_TOOL_MAPPING[mode].requiresTools;

export { doesAgentModeRequireMcpTools, resolveMcpToolFieldForAgentMode, resolveMcpToolModeForAgentMode };
export type { AgentModeMcpToolField, AgentModeMcpToolMapping };
