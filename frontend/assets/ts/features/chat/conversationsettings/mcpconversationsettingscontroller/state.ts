/* SoAI - MCP conversation settings state [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isMcpToolServerEnabled } from '@core/mcp/serverSettings.ts';
import { isMcpToolMode } from '@core/mcp/toolModeSelection.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { queryDefaultToolsModalElements, queryModalElements, readData, requireModalInput, requireToggleCheckbox, updateToggleState } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/dom.ts';
import type { McpConfig, McpFormValues, McpToolMode } from '@features/chat/conversationsettings/settingsModels.ts';

const readServerConfigMap = (host: ConversationSettingsHost, modalRoot: Element | null): Record<string, boolean> => {
    const serverConfigs: Record<string, boolean> = {};
    for (const inputElement of queryModalElements(modalRoot, '.mcp-server-toggle')) {
        const input = requireToggleCheckbox(inputElement);
        const serverId = readData(host, input, 'server_id');
        if (!serverId) {
            continue;
        }
        serverConfigs[serverId] = input.checked;
    }
    return serverConfigs;
};

const applyServerToolAvailability = (host: ConversationSettingsHost, modalRoot: Element | null, serverConfigs: Record<string, boolean>): void => {
    let allowedToolCount = 0;
    for (const inputElement of queryModalElements(modalRoot, '.mcp-tool-toggle')) {
        const input = requireToggleCheckbox(inputElement);
        const serverId = readData(host, input, 'server_id');
        if (!serverId) {
            continue;
        }
        const lockedSelection = readData(host, input, 'selectionLocked') === 'true';
        const toolAllowed = readData(host, input, 'toolAllowed') !== 'false';
        if (toolAllowed) {
            allowedToolCount += 1;
        }
        const available = toolAllowed && isMcpToolServerEnabled(serverId, serverConfigs);
        input.disabled = lockedSelection || !available;
        if (!available && !lockedSelection && input.checked) {
            input.checked = false;
            updateToggleState(input);
        }
    }
    syncToolsEnabledAvailability(modalRoot, allowedToolCount > 0);
};

const readMcpFormValues = (host: ConversationSettingsHost, modalRoot: Element | null, baseline: McpConfig | null): McpFormValues | null => {
    if (!baseline) {
        return null;
    }
    const defaultSelections: string[] = [];
    const planSelections: string[] = [];
    const executeSelections: string[] = [];
    const selections = {
        default: defaultSelections,
        plan: planSelections,
        execute: executeSelections
    };
    for (const inputElement of queryModalElements(modalRoot, '.mcp-tool-toggle')) {
        const input = requireToggleCheckbox(inputElement);
        const toolName = readData(host, input, 'toolName');
        const toolMode = readData(host, input, 'toolMode');
        const lockedSelection = readData(host, input, 'selectionLocked') === 'true';
        if (!toolName || !isMcpToolMode(toolMode)) {
            continue;
        }
        if (!input.checked || (input.disabled && !lockedSelection)) {
            continue;
        }
        if (!selections[toolMode].includes(toolName)) {
            selections[toolMode].push(toolName);
        }
    }
    const toolsEnabled = requireModalInput(modalRoot, '.mcp-tools-enabled-toggle');
    const toolApprovalRequired = requireModalInput(modalRoot, '.mcp-tool-approval-required-toggle');
    return {
        defaultTools: selections.default,
        planTools: selections.plan,
        executeTools: selections.execute,
        serverConfigs: normalizeServerConfigValues(readServerConfigMap(host, modalRoot)),
        toolsEnabled: Boolean(toolsEnabled.checked),
        toolApprovalRequired: Boolean(toolApprovalRequired.checked)
    };
};

const syncToolsEnabledAvailability = (modalRoot: Element | null, hasAvailableTools: boolean): void => {
    const toolsEnabled = requireModalInput(modalRoot, '.mcp-tools-enabled-toggle');
    const lockedEnabled = toolsEnabled.dataset['toolsLockedEnabled'] === 'true';
    const interactionLocked = toolsEnabled.dataset['toolsInteractionLocked'] === 'true';
    if (interactionLocked) {
        toolsEnabled.disabled = true;
        if (lockedEnabled) {
            toolsEnabled.checked = true;
        }
        updateToggleState(toolsEnabled);
        return;
    }
    if (!hasAvailableTools) {
        toolsEnabled.checked = lockedEnabled;
        toolsEnabled.disabled = true;
        updateToggleState(toolsEnabled);
        return;
    }
    if (lockedEnabled) {
        toolsEnabled.checked = true;
        toolsEnabled.disabled = true;
        updateToggleState(toolsEnabled);
        return;
    }
    if (toolsEnabled.disabled && !toolsEnabled.checked) {
        toolsEnabled.disabled = false;
        updateToggleState(toolsEnabled);
    }
};

const syncDefaultToolsToggles = (host: ConversationSettingsHost, defaultToolsModalRoot: Element | null, mode: McpToolMode, selectedTools: Set<string>): void => {
    syncToolToggles(host, queryDefaultToolsModalElements(defaultToolsModalRoot, '.mcp-default-tool-toggle'), mode, selectedTools);
};

const syncConversationToolToggles = (host: ConversationSettingsHost, modalRoot: Element | null, mode: McpToolMode, selectedTools: Set<string>): void => {
    syncToolToggles(host, queryModalElements(modalRoot, '.mcp-tool-toggle'), mode, selectedTools);
};

const syncConversationServersForToolSelection = (host: ConversationSettingsHost, modalRoot: Element | null, mode: McpToolMode, selectedTools: Set<string>): Record<string, boolean> => {
    const selectedServers = new Set<string>();
    for (const element of queryModalElements(modalRoot, '.mcp-tool-toggle')) {
        const input = requireToggleCheckbox(element);
        const toolMode = readData(host, input, 'toolMode');
        const toolName = readData(host, input, 'toolName');
        const serverId = readData(host, input, 'server_id');
        if (toolMode === mode && toolName && serverId && selectedTools.has(toolName)) {
            selectedServers.add(serverId);
        }
    }
    for (const element of queryModalElements(modalRoot, '.mcp-server-toggle')) {
        const input = requireToggleCheckbox(element);
        const serverId = readData(host, input, 'server_id');
        if (serverId && selectedServers.has(serverId) && !input.checked) {
            input.checked = true;
            updateToggleState(input);
        }
    }
    return readServerConfigMap(host, modalRoot);
};

const normalizeServerConfigValues = (serverConfigMap: Record<string, boolean>): Record<string, boolean> => {
    const serverConfigs: Record<string, boolean> = {};
    for (const [serverId, enabled] of Object.entries(serverConfigMap)) {
        if (!enabled) {
            serverConfigs[serverId] = false;
        }
    }
    return serverConfigs;
};

const syncToolToggles = (host: ConversationSettingsHost, elements: Element[], mode: McpToolMode, selectedTools: Set<string>): void => {
    for (const element of elements) {
        const input = requireToggleCheckbox(element);
        const toolMode = readData(host, input, 'toolMode');
        const toolName = readData(host, input, 'toolName');
        const lockedSelection = readData(host, input, 'selectionLocked') === 'true';
        if (toolMode !== mode || !toolName) {
            continue;
        }
        const nextChecked = lockedSelection ? true : !input.disabled && selectedTools.has(toolName);
        if (input.checked === nextChecked) {
            continue;
        }
        input.checked = nextChecked;
        updateToggleState(input);
    }
};

export { applyServerToolAvailability, isMcpToolMode, readMcpFormValues, readServerConfigMap, syncConversationServersForToolSelection, syncConversationToolToggles, syncDefaultToolsToggles };
