/* SoAI - Chat feature agent mode controller [frontend/assets/ts/features/chat/agent/agentModeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hasOwn } from '@core/typeGuards.ts';
import { resolveMcpToolFieldForAgentMode } from '@core/chat/agentModeMcpMapping.ts';
import { cycleAgentMode, isToolAgentMode, resolveAgentMode } from '@features/chat/agent/agentModeState.ts';
import { isChatConversationSettingsWritable } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import type { AgentMode } from '@core/chat/agentMode.ts';
import type { ConversationSettingsAuthorityEligibility } from '@core/chat/conversationSettingsAuthority.ts';
import type { ConversationAgentSettings, ConversationMcpSettings, ConversationMcpSettingsUpdate, ConversationModelSettings, ConversationModelSettingsUpdate } from '@core/chat/executionSettingsTypes.ts';

interface AgentModeConversation {
    id: string;
    isAutomation?: boolean;
    settingsAuthority?: ConversationSettingsAuthorityEligibility;
    modelSettings: ConversationModelSettings;
}

interface AgentModeControllerHost {
    getCurrentConversation(): AgentModeConversation | null;
    updateConversationSettings(conversationId: string, patch: ConversationModelSettingsUpdate): Promise<void>;
    onModeChanged(conversationId: string, mode: AgentMode): void;
}

interface ExternalAgentModeChangeHost {
    getCurrentConversation(): AgentModeConversation | null;
    onModeChanged(conversationId: string, mode: AgentMode): void;
}

const createDefaultMcpSettings = (): ConversationMcpSettings => ({
    defaultTools: [],
    planTools: [],
    executeTools: [],
    serverConfigs: {},
    toolsEnabled: true,
    toolApprovalRequired: true
});

const ensureAgentSettings = (conversation: AgentModeConversation): ConversationAgentSettings => {
    const settings = conversation.modelSettings.agent ?? {};
    conversation.modelSettings.agent = settings;
    return settings;
};

const ensureMcpSettings = (conversation: AgentModeConversation): ConversationMcpSettings => {
    const settings = conversation.modelSettings.mcp ?? createDefaultMcpSettings();
    conversation.modelSettings.mcp = settings;
    return settings;
};

const shouldResetModeToolSelection = (mcpSettings: ConversationMcpSettings | null, mode: AgentMode): boolean => {
    const toolField = resolveMcpToolFieldForAgentMode(mode);
    const selectedTools = mcpSettings ? mcpSettings[toolField] : null;
    return selectedTools === null || selectedTools.length === 0;
};

const mergeMcpPatch = (patch: ConversationModelSettingsUpdate, updates: ConversationMcpSettingsUpdate): void => {
    patch.mcp = { ...(patch.mcp ?? {}), ...updates };
};

const selectAndPersistAgentMode = async (host: AgentModeControllerHost, targetMode: AgentMode | null): Promise<void> => {
    const conversation = host.getCurrentConversation();
    if (!isChatConversationSettingsWritable(conversation)) {
        return;
    }
    const currentMode = resolveAgentMode(conversation);
    const nextMode = targetMode ?? cycleAgentMode(currentMode);
    if (nextMode === currentMode) {
        return;
    }
    const currentAgentSettings = conversation.modelSettings.agent ?? null;
    const hadAgentSettings = currentAgentSettings !== null;
    const hadAgentModeValue = currentAgentSettings ? hasOwn(currentAgentSettings, 'mode') : false;
    const previousAgentModeValue = currentAgentSettings?.mode;
    const agentSettings = ensureAgentSettings(conversation);
    agentSettings.mode = nextMode;
    const currentMcpSettings = conversation.modelSettings.mcp ?? null;
    const currentToolsEnabled = currentMcpSettings?.toolsEnabled ?? null;
    const shouldEnableTools = isToolAgentMode(nextMode) && currentToolsEnabled !== true;
    const targetToolsEnabled = shouldEnableTools || currentToolsEnabled === true;
    const shouldResetToolsForNextMode = isToolAgentMode(nextMode) && targetToolsEnabled && shouldResetModeToolSelection(currentMcpSettings, nextMode);
    const hadMcpSettings = currentMcpSettings !== null;
    const previousToolsEnabled = currentMcpSettings?.toolsEnabled;
    if (shouldEnableTools) {
        ensureMcpSettings(conversation).toolsEnabled = true;
    }
    host.onModeChanged(conversation.id, nextMode);
    try {
        const patch: ConversationModelSettingsUpdate = {
            agent: { mode: nextMode }
        };
        if (shouldEnableTools) {
            mergeMcpPatch(patch, { toolsEnabled: true });
        }
        if (shouldResetToolsForNextMode) {
            mergeMcpPatch(patch, { [resolveMcpToolFieldForAgentMode(nextMode)]: null });
        }
        await host.updateConversationSettings(conversation.id, patch);
    } catch (error) {
        if (!hadAgentSettings) {
            delete conversation.modelSettings.agent;
        } else if (!hadAgentModeValue) {
            delete agentSettings.mode;
        } else if (previousAgentModeValue === undefined) {
            delete agentSettings.mode;
        } else {
            agentSettings.mode = previousAgentModeValue;
        }
        if (shouldEnableTools) {
            if (!hadMcpSettings) {
                delete conversation.modelSettings.mcp;
            } else {
                ensureMcpSettings(conversation).toolsEnabled = previousToolsEnabled ?? true;
            }
        }
        host.onModeChanged(conversation.id, currentMode);
        throw error;
    }
};

const handleExternalModeChange = (host: ExternalAgentModeChangeHost, conversationId: string, newMode: AgentMode): void => {
    const conversation = host.getCurrentConversation();
    if (!conversation || conversation.id !== conversationId) {
        return;
    }
    if (!isChatConversationSettingsWritable(conversation)) {
        host.onModeChanged(conversationId, newMode);
        return;
    }
    const agentSettings = ensureAgentSettings(conversation);
    agentSettings.mode = newMode;
    if (isToolAgentMode(newMode)) {
        ensureMcpSettings(conversation).toolsEnabled = true;
    }
    host.onModeChanged(conversationId, newMode);
};

export { handleExternalModeChange, selectAndPersistAgentMode };
export type { AgentModeControllerHost, AgentModeConversation, ExternalAgentModeChangeHost };
