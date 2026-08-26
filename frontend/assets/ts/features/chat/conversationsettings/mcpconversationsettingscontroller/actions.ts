/* SoAI - MCP conversation settings actions [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveMcpToolFieldForMode, resolveMcpToolsForMode } from '@core/mcp/toolModeSelection.ts';
import { normalizeMcpConfigValues } from '@core/mcp/toolChangeSurfaces.ts';
import type { ConversationMcpConfigUpdateRequest } from '@core/api/contracts/webuiChatOperationContracts.ts';
import { compareParameterValues } from '@features/chat/conversationsettings/valueComparison.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { resolveAgentModeFromModelSettings } from '@features/chat/agent/agentModeState.ts';
import { resolveMcpToolModeForAgentMode } from '@core/chat/agentModeMcpMapping.ts';
import { hasMcpConfigChanges } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/configComparison.ts';
import { readData, requireToggleCheckbox, updateToggleState } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/dom.ts';
import { isMcpToolMode, syncConversationServersForToolSelection, syncConversationToolToggles, syncDefaultToolsToggles } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/state.ts';
import type { McpCanonicalToolDefaults, McpConfig, McpFormValues, McpToolMode } from '@features/chat/conversationsettings/settingsModels.ts';
import type { Conversation } from '@features/chat/storage/storageModels.ts';

interface McpConfigUpdatePlan {
    updates: ConversationMcpConfigUpdateRequest;
}

interface ApplyDefaultToolsToggleChangeOptions {
    host: ConversationSettingsHost;
    element: Element;
    activeToolTab: McpToolMode;
    modalRoot: Element | null;
    defaultToolsModalRoot: Element | null;
    readMcpConfig: () => McpConfig | null;
    readFormValues: () => McpFormValues | null;
    updateApplyState: () => void;
}

interface ApplyToolModeTabChangeOptions {
    host: ConversationSettingsHost;
    tabElement: Element;
    activeToolTab: McpToolMode;
    setActiveToolTab: (mode: McpToolMode) => void;
    readMcpConfig: () => McpConfig | null;
    readFormValues: () => McpFormValues | null;
    renderConfig: (config: McpConfig) => void;
    handleDefaultToolsModalOpen: () => void;
    updateApplyState: () => void;
}

interface ApplyToolModeResetOptions {
    host: ConversationSettingsHost;
    activeToolTab: McpToolMode;
    modalRoot: Element | null;
    defaultToolsModalRoot: Element | null;
    canonicalToolDefaults: McpCanonicalToolDefaults | null;
    applyServerToolAvailability: (serverConfigs: Record<string, boolean>) => void;
    readFormValues: () => McpFormValues | null;
    updateApplyState: () => void;
}

const cloneMcpConfig = (config: Pick<McpFormValues, 'defaultTools' | 'planTools' | 'executeTools' | 'serverConfigs' | 'toolsEnabled' | 'toolApprovalRequired'>): McpConfig => ({
    defaultTools: [...config.defaultTools],
    planTools: [...config.planTools],
    executeTools: [...config.executeTools],
    serverConfigs: { ...config.serverConfigs },
    toolsEnabled: config.toolsEnabled,
    toolApprovalRequired: config.toolApprovalRequired,
    knowledgeState: null
});

const resolveMcpConfigSnapshot = (baselineConfig: McpConfig | null, currentConfig: McpFormValues | null): McpConfig | null => {
    if (!baselineConfig) {
        return null;
    }
    if (!currentConfig) {
        return baselineConfig;
    }
    return {
        ...cloneMcpConfig(currentConfig),
        knowledgeState: baselineConfig.knowledgeState
    };
};

const resolveInitialToolTab = (conversation: Conversation | null | undefined): McpToolMode => {
    if (!conversation) {
        return 'default';
    }
    const mode = resolveAgentModeFromModelSettings(conversation.modelSettings);
    return resolveMcpToolModeForAgentMode(mode);
};

const resolveCanonicalToolsForMode = (canonicalToolDefaults: McpCanonicalToolDefaults | null, mode: McpToolMode): string[] | null => {
    if (!canonicalToolDefaults) {
        return null;
    }
    return resolveMcpToolsForMode(canonicalToolDefaults, mode);
};

const resolveToolUpdateValue = (currentValues: McpFormValues, canonicalToolDefaults: McpCanonicalToolDefaults | null, mode: McpToolMode): string[] | null => {
    const currentTools = resolveMcpToolsForMode(currentValues, mode);
    const canonicalTools = resolveCanonicalToolsForMode(canonicalToolDefaults, mode);
    if (canonicalTools && compareParameterValues(currentTools, canonicalTools)) {
        return null;
    }
    return currentTools;
};

const buildMcpConfigUpdatePlan = (currentValues: McpFormValues, baselineConfig: McpConfig, canonicalToolDefaults: McpCanonicalToolDefaults | null): McpConfigUpdatePlan => {
    const normalizedBaseline = normalizeMcpConfigValues(baselineConfig);
    const updates: ConversationMcpConfigUpdateRequest = {};

    if (!compareParameterValues(currentValues.defaultTools, normalizedBaseline.defaultTools)) {
        updates.defaultTools = resolveToolUpdateValue(currentValues, canonicalToolDefaults, 'default');
    }
    if (!compareParameterValues(currentValues.planTools, normalizedBaseline.planTools)) {
        updates.planTools = resolveToolUpdateValue(currentValues, canonicalToolDefaults, 'plan');
    }
    if (!compareParameterValues(currentValues.executeTools, normalizedBaseline.executeTools)) {
        updates.executeTools = resolveToolUpdateValue(currentValues, canonicalToolDefaults, 'execute');
    }
    if (!compareParameterValues(currentValues.serverConfigs, normalizedBaseline.serverConfigs)) {
        updates.serverConfigs = currentValues.serverConfigs;
    }
    if (!compareParameterValues(currentValues.toolsEnabled, normalizedBaseline.toolsEnabled)) {
        updates.toolsEnabled = currentValues.toolsEnabled;
    }
    if (!compareParameterValues(currentValues.toolApprovalRequired, normalizedBaseline.toolApprovalRequired)) {
        updates.toolApprovalRequired = currentValues.toolApprovalRequired;
    }
    return { updates };
};

const applyDefaultToolsToggleChange = ({ host, element, activeToolTab, modalRoot, defaultToolsModalRoot, readMcpConfig, readFormValues, updateApplyState }: ApplyDefaultToolsToggleChangeOptions): void => {
    updateToggleState(element);
    const input = requireToggleCheckbox(element);
    const toolName = readData(host, input, 'toolName');
    if (!toolName) {
        return;
    }

    const modeValue = readData(host, input, 'toolMode');
    const mode: McpToolMode = isMcpToolMode(modeValue) ? modeValue : activeToolTab;
    const configSnapshot = resolveMcpConfigSnapshot(readMcpConfig(), readFormValues());
    if (!configSnapshot) {
        return;
    }

    const selection = new Set<string>(resolveMcpToolsForMode(configSnapshot, mode));
    if (input.checked) {
        selection.add(toolName);
    } else {
        selection.delete(toolName);
    }

    syncConversationToolToggles(host, modalRoot, mode, selection);
    const currentValues = readFormValues();
    const syncedSelection = currentValues ? new Set<string>(resolveMcpToolsForMode(currentValues, mode)) : selection;
    syncDefaultToolsToggles(host, defaultToolsModalRoot, mode, syncedSelection);
    updateApplyState();
};

const applyToolModeTabChange = ({ host, tabElement, activeToolTab, setActiveToolTab, readMcpConfig, readFormValues, renderConfig, handleDefaultToolsModalOpen, updateApplyState }: ApplyToolModeTabChangeOptions): void => {
    const modeValue = readData(host, tabElement, 'toolMode');
    if (!isMcpToolMode(modeValue) || activeToolTab === modeValue) {
        return;
    }

    setActiveToolTab(modeValue);
    const renderConfigValue = resolveMcpConfigSnapshot(readMcpConfig(), readFormValues());
    if (renderConfigValue) {
        renderConfig(renderConfigValue);
    }
    handleDefaultToolsModalOpen();
    updateApplyState();
};

const applyToolModeReset = ({ host, activeToolTab, modalRoot, defaultToolsModalRoot, canonicalToolDefaults, applyServerToolAvailability: applyToolAvailability, readFormValues, updateApplyState }: ApplyToolModeResetOptions): void => {
    const canonicalTools = resolveCanonicalToolsForMode(canonicalToolDefaults, activeToolTab);
    if (!canonicalTools) {
        return;
    }
    const selectedTools = new Set<string>(canonicalTools);
    applyToolAvailability(syncConversationServersForToolSelection(host, modalRoot, activeToolTab, selectedTools));
    syncConversationToolToggles(host, modalRoot, activeToolTab, selectedTools);
    const currentValues = readFormValues();
    const syncedSelection = currentValues ? new Set<string>(currentValues[resolveMcpToolFieldForMode(activeToolTab)]) : selectedTools;
    syncDefaultToolsToggles(host, defaultToolsModalRoot, activeToolTab, syncedSelection);
    updateApplyState();
};

export { applyDefaultToolsToggleChange, applyToolModeReset, applyToolModeTabChange, buildMcpConfigUpdatePlan, hasMcpConfigChanges, resolveInitialToolTab, resolveMcpConfigSnapshot };
export type { McpConfigUpdatePlan };
