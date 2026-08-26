/* SoAI - Authoritative MCP knowledge-managed state refresh [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/knowledgeStateRefresh.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationMcpConfigResponse, ConversationMcpToolCatalogResponse } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { requireConversationSettingsChatApi, type ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { parseMcpCanonicalToolDefaults, parseMcpConfig, parseMcpTools } from '@features/chat/conversationsettings/conversationSettingsParsing.ts';
import type { McpConfig, McpTool } from '@features/chat/conversationsettings/settingsModels.ts';

interface McpKnowledgeState {
    config: McpConfig;
    tools: McpTool[];
}

interface McpKnowledgeRefresh extends McpKnowledgeState {
    configResult: PromiseFulfilledResult<ConversationMcpConfigResponse>;
    toolsResult: PromiseFulfilledResult<ConversationMcpToolCatalogResponse>;
}

const loadMcpKnowledgeManagedState = async (host: ConversationSettingsHost, conversationId: string): Promise<McpKnowledgeRefresh> => {
    const chatApi = requireConversationSettingsChatApi(host);
    const [configResult, toolsResult] = await Promise.allSettled([chatApi.mcp.getConfig(conversationId), chatApi.mcp.getTools(conversationId)]);
    if (configResult.status === 'rejected' || toolsResult.status === 'rejected') {
        throw new Error('Authoritative MCP refresh failed.');
    }
    const config = parseMcpConfig(configResult.value);
    const tools = parseMcpTools(toolsResult.value);
    parseMcpCanonicalToolDefaults(toolsResult.value);
    return { config, tools, configResult, toolsResult };
};

export { loadMcpKnowledgeManagedState };
export type { McpKnowledgeState };
