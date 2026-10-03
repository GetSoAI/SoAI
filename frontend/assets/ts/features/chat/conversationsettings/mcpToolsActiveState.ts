/* SoAI - Chat feature MCP tools active state [frontend/assets/ts/features/chat/conversationsettings/mcpToolsActiveState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveAgentModeFromModelSettings } from '@features/chat/agent/agentModeState.ts';
import { doesAgentModeRequireMcpTools, resolveMcpToolFieldForAgentMode } from '@core/chat/agentModeMcpMapping.ts';
import type { ConversationMcpSettings, ConversationModelSettings } from '@core/chat/executionSettingsTypes.ts';

const resolveActiveToolListForMode = (mcpSettings: ConversationMcpSettings, modelSettings: ConversationModelSettings): readonly string[] => {
    const mode = resolveAgentModeFromModelSettings(modelSettings);
    const field = resolveMcpToolFieldForAgentMode(mode);
    return mcpSettings[field];
};

const isToolsEffectivelyEnabled = (modelSettings: ConversationModelSettings | undefined): boolean => {
    const mcpSettings = modelSettings?.mcp;
    if (!mcpSettings || mcpSettings.toolsEnabled !== true) {
        return false;
    }
    return hasSelectedToolsForActiveMode(modelSettings);
};

const hasSelectedToolsForActiveMode = (modelSettings: ConversationModelSettings | undefined): boolean => {
    if (!modelSettings?.mcp) return false;
    return resolveActiveToolListForMode(modelSettings.mcp, modelSettings).length > 0;
};

const isAgentModeRequiringTools = (modelSettings: ConversationModelSettings | undefined): boolean => {
    const mode = resolveAgentModeFromModelSettings(modelSettings);
    return doesAgentModeRequireMcpTools(mode);
};

const isAgentModeRequiringToolsWithToolsDisabled = (modelSettings: ConversationModelSettings | undefined): boolean => {
    const mcpSettings = modelSettings?.mcp;
    if (!mcpSettings) {
        return false;
    }
    const mode = resolveAgentModeFromModelSettings(modelSettings);
    return doesAgentModeRequireMcpTools(mode) && mcpSettings.toolsEnabled !== true;
};

export { hasSelectedToolsForActiveMode, isAgentModeRequiringTools, isAgentModeRequiringToolsWithToolsDisabled, isToolsEffectivelyEnabled };
