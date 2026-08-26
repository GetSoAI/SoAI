/* SoAI - Agent mode MCP settings synchronization [frontend/assets/ts/features/chat/conversationsettings/agentModeMcpSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { normalizeMcpConfigValues, syncMcpToolChangeSurfaces } from '@core/mcp/toolChangeSurfaces.ts';
import { resolveAgentModeFromModelSettings } from '@features/chat/agent/agentModeState.ts';
import { doesAgentModeRequireMcpTools } from '@core/chat/agentModeMcpMapping.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { hasMcpConfigChanges } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/configComparison.ts';
import { readMcpFormValues } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/state.ts';
import { syncToolsEnabledControl } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/view.ts';
import type { McpConfig } from '@features/chat/conversationsettings/settingsModels.ts';

interface AgentModeMcpSyncArguments {
    host: ConversationSettingsHost;
    modalRoot: Element;
    defaultToolsModalRoot: Element | null;
    config: McpConfig;
    writeMcpConfig(config: McpConfig): void;
}

const syncAgentModeMcpToolsEnabledState = (inputArguments: AgentModeMcpSyncArguments): boolean => {
    const conversation = inputArguments.host.data.getCurrentConversation();
    const modelSettings = conversation ? conversation.modelSettings : null;
    const modeRequiresTools = doesAgentModeRequireMcpTools(resolveAgentModeFromModelSettings(modelSettings));
    const toolsEnabledValue = modelSettings?.mcp?.toolsEnabled;
    const conversationToolsEnabled = toolsEnabledValue === true || toolsEnabledValue === false ? toolsEnabledValue : inputArguments.config.toolsEnabled;
    const toolsEnabled = modeRequiresTools ? true : conversationToolsEnabled;
    const nextConfig = toolsEnabled !== inputArguments.config.toolsEnabled ? { ...inputArguments.config, toolsEnabled: toolsEnabled } : inputArguments.config;
    if (nextConfig !== inputArguments.config) {
        inputArguments.writeMcpConfig(nextConfig);
    }
    syncToolsEnabledControl(inputArguments.host, inputArguments.modalRoot, nextConfig);
    const current = readMcpFormValues(inputArguments.host, inputArguments.modalRoot, nextConfig);
    syncMcpToolChangeSurfaces({
        modalRoot: inputArguments.modalRoot,
        defaultToolsModalRoot: inputArguments.defaultToolsModalRoot,
        baseline: normalizeMcpConfigValues(nextConfig),
        current,
        includeTopLevelSurfaces: true
    });
    return current ? hasMcpConfigChanges(current, nextConfig) : false;
};

export { syncAgentModeMcpToolsEnabledState };
