/* SoAI - Chat feature MCP conversation settings UI [frontend/assets/ts/features/chat/conversationsettings/mcpConversationSettingsUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isServerEnabled } from '@core/mcp/serverSettings.ts';
import { buildServerGroups, isToolAvailable, type BuildToggleSwitch, type McpToolGroupRenderHost } from '@core/mcp/toolGroupRendering.ts';
import { renderMcpToolModeGroups, resolveMcpToolModeLabel } from '@core/mcp/toolModeRendering.ts';
import { resolveMcpToolsForMode } from '@core/mcp/toolModeSelection.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { MCP_CONVERSATION_ACTION_TOOL_MODE_SELECT, MCP_CONVERSATION_ACTION_TOOL_SEARCH } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';
import { isKnowledgeToolSelectionLocked, resolveKnowledgeDefaultToolsHintText, resolveKnowledgeToolLockReason } from '@features/chat/conversationsettings/mcpKnowledgeState.ts';
import type { McpConfig, McpTool, McpToolMode } from '@features/chat/conversationsettings/settingsModels.ts';

interface McpConversationSettingsUiRenderHost extends McpToolGroupRenderHost {
    updateHTML(element: Element, html: string): void;
    toggleClassName(element: Element, className: string, add: boolean): void;
    dom: { getDocument(): Document };
}

const resolveModeToolSelection = (config: McpConfig, mode: McpToolMode): Set<string> => {
    return new Set<string>(resolveMcpToolsForMode(config, mode));
};

const countAvailableModeTools = (config: McpConfig, tools: McpTool[], mode: McpToolMode): number => {
    const selection = resolveModeToolSelection(config, mode);
    return tools.filter((tool) => selection.has(tool.name) && isToolAvailable(tool, config.serverConfigs)).length;
};

const renderConversationMcpToolModeGroups = (inputArguments: { host: McpConversationSettingsUiRenderHost; container: Element; emptyState: Element; config: McpConfig; tools: McpTool[]; activeToolTab: McpToolMode; toolModes?: readonly McpToolMode[] | undefined; toolModeAction?: string | undefined; buildToggleSwitch: BuildToggleSwitch; toggleClassName?: string | undefined; toggleIdPrefix?: string | undefined; collapsedToolGroups?: boolean | undefined; toolGroupToggleAction?: string | undefined; toolGroupToggleIcon?: TrustedHtml | undefined; expandedToolGroupIds?: ReadonlySet<string> | undefined; showServerToggles?: boolean | undefined; toolSearchAction?: string | undefined }): void => {
    renderMcpToolModeGroups({
        host: inputArguments.host,
        container: inputArguments.container,
        emptyState: inputArguments.emptyState,
        config: inputArguments.config,
        tools: inputArguments.tools,
        activeToolTab: inputArguments.activeToolTab,
        toolModes: inputArguments.toolModes,
        ...(inputArguments.toolModeAction ? { toolModeAction: inputArguments.toolModeAction } : {}),
        buildToggleSwitch: inputArguments.buildToggleSwitch,
        applyServerToolAvailability: () => {},
        toggleClassName: inputArguments.toggleClassName,
        toggleIdPrefix: inputArguments.toggleIdPrefix,
        collapsedToolGroups: inputArguments.collapsedToolGroups,
        toolGroupToggleAction: inputArguments.toolGroupToggleAction,
        toolGroupToggleIcon: inputArguments.toolGroupToggleIcon,
        expandedToolGroupIds: inputArguments.expandedToolGroupIds,
        showServerToggles: inputArguments.showServerToggles,
        toolSearchAction: inputArguments.toolSearchAction,
        isSelectionLocked: isKnowledgeToolSelectionLocked,
        resolveLockReason: resolveKnowledgeToolLockReason
    });
};

export const renderMcpDefaultToolsSummary = (inputArguments: { host: McpConversationSettingsUiRenderHost; summary: Element; config: McpConfig | null; tools: McpTool[]; activeToolTab: McpToolMode; toolModes?: readonly McpToolMode[] | undefined }): void => {
    const config = inputArguments.config;
    if (config === null) {
        inputArguments.host.updateText(inputArguments.summary, i18n.t('chat.configuration.mcp.defaultTools.summary', { count: 0 }));
        return;
    }
    const count = countAvailableModeTools(config, inputArguments.tools, inputArguments.activeToolTab);
    inputArguments.host.updateText(inputArguments.summary, i18n.t('chat.configuration.mcp.defaultTools.summary', { count }));
};

export const renderMcpServers = (inputArguments: { host: McpConversationSettingsUiRenderHost; container: Element; emptyState: Element; config: McpConfig; tools: McpTool[]; buildToggleSwitch: BuildToggleSwitch }): void => {
    inputArguments.host.updateHTML(inputArguments.container, '');
    const fragment = inputArguments.host.dom.getDocument().createDocumentFragment();
    const groups = buildServerGroups({
        serverConfigs: inputArguments.config.serverConfigs,
        tools: inputArguments.tools,
        includeBuiltin: true
    });
    if (groups.length === 0) {
        inputArguments.host.updateText(inputArguments.emptyState, i18n.t('chat.configuration.mcp.noServers'));
        inputArguments.host.toggleClassName(inputArguments.emptyState, 'u-hidden', false);
        return;
    }
    inputArguments.host.toggleClassName(inputArguments.emptyState, 'u-hidden', true);
    groups.forEach((group, index) => {
        const row = inputArguments.host.createElement('div', {
            class: 'mcp-server-card setting-change-surface',
            'data-server-id': group.id
        });
        const info = inputArguments.host.createElement('div', { class: 'mcp-server-info' });
        const name = inputArguments.host.createElement('div', { class: 'mcp-server-name' });
        inputArguments.host.updateText(name, group.name);
        setTooltipText(name, group.name);
        inputArguments.host.appendToElement(info, name);
        const toggleId = `mcp-server-toggle-${index}`;
        const toggle = inputArguments.buildToggleSwitch({
            id: toggleId,
            className: 'mcp-server-toggle mcp-input',
            checked: isServerEnabled(group.id, inputArguments.config.serverConfigs),
            data: { serverId: group.id },
            disabled: false
        });
        inputArguments.host.appendToElement(row, info);
        inputArguments.host.appendToElement(row, toggle);
        fragment.appendChild(row);
    });
    inputArguments.host.appendToElement(inputArguments.container, fragment);
};

export const renderMcpTools = (inputArguments: { host: McpConversationSettingsUiRenderHost; container: Element; emptyState: Element; config: McpConfig; tools: McpTool[]; activeToolTab: McpToolMode; toolModes?: readonly McpToolMode[] | undefined; buildToggleSwitch: BuildToggleSwitch; applyServerToolAvailability(serverConfigs: Record<string, boolean>): void; collapsedToolGroups?: boolean | undefined; toolGroupToggleAction?: string | undefined; toolGroupToggleIcon?: TrustedHtml | undefined; expandedToolGroupIds?: ReadonlySet<string> | undefined; showServerToggles?: boolean | undefined }): void => {
    renderConversationMcpToolModeGroups({
        host: inputArguments.host,
        container: inputArguments.container,
        emptyState: inputArguments.emptyState,
        config: inputArguments.config,
        tools: inputArguments.tools,
        activeToolTab: inputArguments.activeToolTab,
        toolModes: inputArguments.toolModes,
        toolModeAction: MCP_CONVERSATION_ACTION_TOOL_MODE_SELECT,
        buildToggleSwitch: inputArguments.buildToggleSwitch,
        collapsedToolGroups: inputArguments.collapsedToolGroups,
        toolGroupToggleAction: inputArguments.toolGroupToggleAction,
        toolGroupToggleIcon: inputArguments.toolGroupToggleIcon,
        expandedToolGroupIds: inputArguments.expandedToolGroupIds,
        showServerToggles: inputArguments.showServerToggles,
        toolSearchAction: MCP_CONVERSATION_ACTION_TOOL_SEARCH
    });
    inputArguments.applyServerToolAvailability(inputArguments.config.serverConfigs);
};

export const renderMcpDefaultToolsModal = (inputArguments: { host: McpConversationSettingsUiRenderHost; container: Element; emptyState: Element; config: McpConfig; tools: McpTool[]; activeToolTab: McpToolMode; toolModes?: readonly McpToolMode[] | undefined; buildToggleSwitch: BuildToggleSwitch; collapsedToolGroups?: boolean | undefined; toolGroupToggleAction?: string | undefined; toolGroupToggleIcon?: TrustedHtml | undefined; expandedToolGroupIds?: ReadonlySet<string> | undefined }): void => {
    renderConversationMcpToolModeGroups({
        host: inputArguments.host,
        container: inputArguments.container,
        emptyState: inputArguments.emptyState,
        config: inputArguments.config,
        tools: inputArguments.tools,
        activeToolTab: inputArguments.activeToolTab,
        toolModes: inputArguments.toolModes,
        toolModeAction: MCP_CONVERSATION_ACTION_TOOL_MODE_SELECT,
        buildToggleSwitch: inputArguments.buildToggleSwitch,
        toggleClassName: 'mcp-default-tool-toggle mcp-input',
        toggleIdPrefix: 'mcp-default-tool-toggle',
        collapsedToolGroups: inputArguments.collapsedToolGroups,
        toolGroupToggleAction: inputArguments.toolGroupToggleAction,
        toolGroupToggleIcon: inputArguments.toolGroupToggleIcon,
        expandedToolGroupIds: inputArguments.expandedToolGroupIds,
        toolSearchAction: MCP_CONVERSATION_ACTION_TOOL_SEARCH
    });
};

export const renderMcpKnowledgeManagedDefaultToolsHint = (inputArguments: { host: McpConversationSettingsUiRenderHost; element: Element; config: McpConfig | null }): void => {
    inputArguments.host.updateText(inputArguments.element, resolveKnowledgeDefaultToolsHintText(inputArguments.config));
};

export { resolveMcpToolModeLabel };
