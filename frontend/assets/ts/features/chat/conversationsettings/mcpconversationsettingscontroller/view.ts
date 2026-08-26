/* SoAI - MCP conversation settings rendering [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { isAutomationConversation } from '@features/chat/conversation/conversationSettingsEligibility.ts';
import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import { isKnowledgeToolsForceEnabled, resolveKnowledgeMcpHintText } from '@features/chat/conversationsettings/mcpKnowledgeState.ts';
import { isAgentModeRequiringTools } from '@features/chat/conversationsettings/mcpToolsActiveState.ts';
import { MCP_CONVERSATION_ACTION_TOOL_GROUP_TOGGLE } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';
import { queryDefaultToolsModalElements, queryModalElements, requireDefaultToolsModalElement, requireModalElement, requireModalInput, updateToggleState } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/dom.ts';
import type { McpToggleSwitchBuilder } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/types.ts';
import { renderMcpDefaultToolsModal, renderMcpDefaultToolsSummary, renderMcpKnowledgeManagedDefaultToolsHint, renderMcpTools, resolveMcpToolModeLabel } from '@features/chat/conversationsettings/mcpConversationSettingsUi.ts';
import type { McpCanonicalToolDefaults, McpConfig, McpTool, McpToolMode } from '@features/chat/conversationsettings/settingsModels.ts';

interface RenderMcpConfigOptions {
    host: ConversationSettingsHost;
    modalRoot: Element | null;
    config: McpConfig;
    tools: McpTool[];
    activeToolTab: McpToolMode;
    canonicalToolDefaults: McpCanonicalToolDefaults | null;
    buildToggleSwitch: McpToggleSwitchBuilder;
    applyServerToolAvailability: (serverConfigs: Record<string, boolean>) => void;
    renderDefaultToolsSummary: () => void;
    expandedToolGroupIds: ReadonlySet<string>;
}

interface RenderMcpDefaultToolsModalOptions {
    host: ConversationSettingsHost;
    defaultToolsModalRoot: Element | null;
    config: McpConfig;
    tools: McpTool[];
    activeToolTab: McpToolMode;
    canonicalToolDefaults: McpCanonicalToolDefaults | null;
    buildToggleSwitch: McpToggleSwitchBuilder;
    expandedToolGroupIds: ReadonlySet<string>;
}

interface RenderMcpDefaultToolsSummaryOptions {
    host: ConversationSettingsHost;
    modalRoot: Element | null;
    config: McpConfig | null;
    tools: McpTool[];
    activeToolTab: McpToolMode;
}

const resetMcpUi = (host: ConversationSettingsHost, modalRoot: Element | null, defaultToolsModalRoot: Element | null, onDirtyStateChange: (hasChanges: boolean) => void, renderDefaultToolsSummary: () => void): void => {
    syncAutomationHint(host, modalRoot);
    host.view.updateHTML(requireModalElement(modalRoot, '.mcp-servers-list'), '');
    host.view.toggleClassName(requireModalElement(modalRoot, '.mcp-servers-empty'), 'u-hidden', true);

    const tools = requireModalElement(modalRoot, '.mcp-tools-list');
    host.view.updateHTML(tools, '');
    const toolsEmpty = requireModalElement(modalRoot, '.mcp-tools-empty');
    host.view.updateText(toolsEmpty, i18n.t('chat.configuration.mcp.noTools'));
    host.view.toggleClassName(toolsEmpty, 'u-hidden', false);

    const defaultTools = requireDefaultToolsModalElement(defaultToolsModalRoot, '.mcp-tools-list');
    host.view.updateHTML(defaultTools, '');
    const defaultToolsEmpty = requireDefaultToolsModalElement(defaultToolsModalRoot, '.mcp-tools-empty');
    host.view.updateText(defaultToolsEmpty, i18n.t('chat.configuration.mcp.noTools'));
    host.view.toggleClassName(defaultToolsEmpty, 'u-hidden', false);

    onDirtyStateChange(false);

    const toolsEnabled = requireModalInput(modalRoot, '.mcp-tools-enabled-toggle');
    toolsEnabled.checked = false;
    toolsEnabled.disabled = false;
    delete toolsEnabled.dataset['toolsLockedEnabled'];
    delete toolsEnabled.dataset['toolsInteractionLocked'];
    updateToggleState(toolsEnabled);
    const toolApprovalRequired = requireModalInput(modalRoot, '.mcp-tool-approval-required-toggle');
    toolApprovalRequired.checked = false;
    toolApprovalRequired.disabled = false;
    updateToggleState(toolApprovalRequired);
    host.view.updateText(requireModalElement(modalRoot, '.mcp-tools-enabled-hint'), i18n.t('chat.configuration.mcp.toolsEnabledHint'));
    host.view.updateText(requireModalElement(modalRoot, '.mcp-default-tools-summary-hint'), i18n.t('chat.configuration.mcp.defaultTools.summaryHint'));
    syncResetButtons(host, modalRoot, defaultToolsModalRoot, 'default', false);
    renderDefaultToolsSummary();
};

const syncToolsEnabledControl = (host: ConversationSettingsHost, modalRoot: Element | null, config: McpConfig): void => {
    const toolsEnabled = requireModalInput(modalRoot, '.mcp-tools-enabled-toggle');
    const conversation = host.data.getCurrentConversation();
    const modelSettings = conversation?.modelSettings;
    const conversationModeRequiresTools = isAgentModeRequiringTools(modelSettings);
    const conversationExecuting = conversation?.id ? host.data.isConversationExecuting(conversation.id) : false;
    const toolsEnabledLocked = isKnowledgeToolsForceEnabled(config) || conversationModeRequiresTools || conversationExecuting;
    toolsEnabled.checked = config.toolsEnabled || conversationModeRequiresTools;
    toolsEnabled.disabled = toolsEnabledLocked;
    toolsEnabled.dataset['toolsLockedEnabled'] = toolsEnabledLocked && toolsEnabled.checked ? 'true' : 'false';
    toolsEnabled.dataset['toolsInteractionLocked'] = toolsEnabledLocked ? 'true' : 'false';
    updateToggleState(toolsEnabled);
    host.view.updateText(requireModalElement(modalRoot, '.mcp-tools-enabled-hint'), resolveToolsEnabledControlHint(config, conversationModeRequiresTools, conversationExecuting));
};

const syncAutomationHint = (host: ConversationSettingsHost, modalRoot: Element | null): void => {
    host.view.toggleClassName(requireModalElement(modalRoot, '.mcp-automation-ephemeral-hint'), 'u-hidden', !isAutomationConversation(host.data.getCurrentConversation()));
};

const resolveToolsEnabledControlHint = (config: McpConfig, conversationModeRequiresTools: boolean, conversationExecuting: boolean): string => {
    if (conversationModeRequiresTools) {
        return i18n.t('chat.configuration.mcp.toolsEnabledLockedForAgentModeHint');
    }
    if (conversationExecuting) {
        return i18n.t('chat.configuration.mcp.toolsEnabledLockedWhileConversationRunningHint');
    }
    return resolveKnowledgeMcpHintText(config);
};

const renderConfig = ({ host, modalRoot, config, tools, activeToolTab, canonicalToolDefaults, buildToggleSwitch, applyServerToolAvailability: applyToolAvailability, renderDefaultToolsSummary, expandedToolGroupIds }: RenderMcpConfigOptions): void => {
    syncAutomationHint(host, modalRoot);
    host.view.updateHTML(requireModalElement(modalRoot, '.mcp-servers-list'), '');
    host.view.toggleClassName(requireModalElement(modalRoot, '.mcp-servers-empty'), 'u-hidden', true);
    syncToolsEnabledControl(host, modalRoot, config);
    const toolApprovalRequired = requireModalInput(modalRoot, '.mcp-tool-approval-required-toggle');
    toolApprovalRequired.checked = config.toolApprovalRequired;
    updateToggleState(toolApprovalRequired);
    renderMcpTools({
        host: host.view,
        container: requireModalElement(modalRoot, '.mcp-tools-list'),
        emptyState: requireModalElement(modalRoot, '.mcp-tools-empty'),
        config,
        tools,
        activeToolTab,
        buildToggleSwitch,
        applyServerToolAvailability: applyToolAvailability,
        collapsedToolGroups: true,
        toolGroupToggleAction: MCP_CONVERSATION_ACTION_TOOL_GROUP_TOGGLE,
        toolGroupToggleIcon: host.view.getIconSync('chevron-left', { size: 14, strokeWidth: 2 }),
        expandedToolGroupIds,
        showServerToggles: true
    });
    renderDefaultToolsSummary();
    syncResetButtons(host, modalRoot, null, activeToolTab, canonicalToolDefaults !== null);
};

const renderDefaultToolsModal = ({ host, defaultToolsModalRoot, config, tools, activeToolTab, canonicalToolDefaults, buildToggleSwitch, expandedToolGroupIds }: RenderMcpDefaultToolsModalOptions): void => {
    renderMcpDefaultToolsModal({
        host: host.view,
        container: requireDefaultToolsModalElement(defaultToolsModalRoot, '.mcp-tools-list'),
        emptyState: requireDefaultToolsModalElement(defaultToolsModalRoot, '.mcp-tools-empty'),
        config,
        tools,
        activeToolTab,
        buildToggleSwitch,
        collapsedToolGroups: true,
        toolGroupToggleAction: MCP_CONVERSATION_ACTION_TOOL_GROUP_TOGGLE,
        toolGroupToggleIcon: host.view.getIconSync('chevron-left', { size: 14, strokeWidth: 2 }),
        expandedToolGroupIds
    });
    syncResetButtons(host, null, defaultToolsModalRoot, activeToolTab, canonicalToolDefaults !== null);
};

const renderDefaultToolsSummary = ({ host, modalRoot, config, tools, activeToolTab }: RenderMcpDefaultToolsSummaryOptions): void => {
    renderMcpDefaultToolsSummary({
        host: host.view,
        summary: requireModalElement(modalRoot, '.mcp-default-tools-summary'),
        config,
        tools,
        activeToolTab
    });
    renderMcpKnowledgeManagedDefaultToolsHint({
        host: host.view,
        element: requireModalElement(modalRoot, '.mcp-default-tools-summary-hint'),
        config
    });
};

const syncResetButtons = (host: ConversationSettingsHost, modalRoot: Element | null, defaultToolsModalRoot: Element | null, activeToolTab: McpToolMode, enabled: boolean): void => {
    const label = i18n.t('chat.configuration.mcp.resetToolsLabel');
    const description = i18n.t('chat.configuration.mcp.resetToolsDescription', { mode: resolveMcpToolModeLabel(activeToolTab) });
    const buttons = [...(modalRoot ? queryModalElements(modalRoot, '.mcp-tool-mode-reset-btn') : []), ...(defaultToolsModalRoot ? queryDefaultToolsModalElements(defaultToolsModalRoot, '.mcp-tool-mode-reset-btn') : [])];
    for (const element of buttons) {
        if (!(element instanceof HTMLButtonElement)) {
            throw new TypeError('MCP tool reset control must be a button');
        }
        host.view.updateText(element, label);
        element.setAttribute('aria-label', description);
        setTooltipText(element, description);
        element.disabled = !enabled;
    }
    for (const element of [...(modalRoot ? queryModalElements(modalRoot, '.mcp-tool-mode-reset-description') : []), ...(defaultToolsModalRoot ? queryDefaultToolsModalElements(defaultToolsModalRoot, '.mcp-tool-mode-reset-description') : [])]) {
        host.view.updateText(element, description);
    }
};

export { renderConfig, renderDefaultToolsModal, renderDefaultToolsSummary, resetMcpUi, syncToolsEnabledControl };
