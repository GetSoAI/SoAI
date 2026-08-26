/* SoAI - Chat feature MCP knowledge state [frontend/assets/ts/features/chat/conversationsettings/mcpKnowledgeState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpConfig, McpKnowledgeState, McpTool } from '@features/chat/conversationsettings/settingsModels.ts';

const readKnowledgeState = (config: McpConfig | null): McpKnowledgeState | null => (config ? config.knowledgeState : null);

const isKnowledgeToolsLocked = (config: McpConfig | null): boolean => readKnowledgeState(config)?.toolsLocked === true;

const isKnowledgeToolsForceEnabled = (config: McpConfig | null): boolean => readKnowledgeState(config)?.forceToolsEnabled === true;

const isRequiredKnowledgeTool = (tool: McpTool): boolean => tool.knowledgeRole === 'required_access';

const isKnowledgeToolSelectionLocked = (config: McpConfig | null, tool: McpTool): boolean => isKnowledgeToolsLocked(config) && isRequiredKnowledgeTool(tool);

const resolveKnowledgeToolLockReason = (config: McpConfig | null, tool: McpTool): string | null => {
    if (!isKnowledgeToolSelectionLocked(config, tool)) {
        return null;
    }
    return i18n.t('chat.configuration.mcp.knowledgeManagedToolHint');
};

const resolveKnowledgeMcpHintText = (config: McpConfig | null): string => {
    if (isKnowledgeToolsForceEnabled(config)) {
        return i18n.t('chat.configuration.mcp.knowledgeManagedToolsEnabledHint');
    }
    return i18n.t('chat.configuration.mcp.toolsEnabledHint');
};

const resolveKnowledgeDefaultToolsHintText = (config: McpConfig | null): string => {
    if (isKnowledgeToolsLocked(config)) {
        return i18n.t('chat.configuration.mcp.knowledgeManagedDefaultToolsHint');
    }
    return i18n.t('chat.configuration.mcp.defaultTools.summaryHint');
};

export { isKnowledgeToolSelectionLocked, isKnowledgeToolsForceEnabled, isKnowledgeToolsLocked, isRequiredKnowledgeTool, readKnowledgeState, resolveKnowledgeDefaultToolsHintText, resolveKnowledgeMcpHintText, resolveKnowledgeToolLockReason };
