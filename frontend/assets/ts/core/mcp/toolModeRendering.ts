/* SoAI - Shared frontend MCP tool mode rendering [frontend/assets/ts/core/mcp/toolModeRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpConfig, McpTool, McpToolMode } from '@core/mcp/configTypes.ts';
import { renderToolGroups, type BuildToggleSwitch, type McpToolGroupRenderHost, type McpToolLockReasonResolver, type McpToolSelectionLockResolver } from '@core/mcp/toolGroupRendering.ts';
import { resolveMcpToolsForMode } from '@core/mcp/toolModeSelection.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface McpToolModeRenderHost extends McpToolGroupRenderHost {
    updateHTML(element: Element, html: string): void;
    toggleClassName(element: Element, className: string, add: boolean): void;
}

const MCP_TOOL_MODES: readonly McpToolMode[] = Object.freeze(['default', 'plan', 'execute']);

const resolveMcpToolModeLabel = (mode: McpToolMode): string => {
    switch (mode) {
        case 'default':
            return i18n.t('chat.agent.tools.tabDefault');
        case 'plan':
            return i18n.t('chat.agent.tools.tabPlan');
        case 'execute':
            return i18n.t('chat.agent.tools.tabExecute');
    }
};

const resolveModeToolSelection = (config: McpConfig<JsonValue | null>, mode: McpToolMode): Set<string> => {
    return new Set<string>(resolveMcpToolsForMode(config, mode));
};

const renderToolModeTabs = (inputArguments: { host: McpToolModeRenderHost; activeToolTab: McpToolMode; toolModes: readonly McpToolMode[]; toolModeAction?: string | undefined }): HTMLElement | null => {
    if (inputArguments.toolModes.length <= 1) {
        return null;
    }
    const tabs = inputArguments.host.createElement('div', {
        class: 'mcp-tool-mode-tabs tabs-container',
        role: 'tablist',
        'aria-label': i18n.t('chat.agent.tools.tabHint')
    });
    const wrapper = inputArguments.host.createElement('div', { class: 'tabs-nav-wrapper' });
    const nav = inputArguments.host.createElement('nav', { class: 'tabs-nav' });
    inputArguments.toolModes.forEach((mode) => {
        const isActive = mode === inputArguments.activeToolTab;
        const button = inputArguments.host.createElement('button', {
            type: 'button',
            class: `tabs-tab${isActive ? ' is-active' : ''}`,
            ...(inputArguments.toolModeAction ? { 'data-action': inputArguments.toolModeAction } : {}),
            'data-tab': mode,
            'data-tool-mode': mode,
            role: 'tab',
            'aria-selected': isActive ? 'true' : 'false',
            'aria-label': resolveMcpToolModeLabel(mode)
        });
        const label = inputArguments.host.createElement('span', { class: 'tabs-tab-label' });
        inputArguments.host.updateText(label, resolveMcpToolModeLabel(mode));
        inputArguments.host.appendToElement(button, label);
        inputArguments.host.appendToElement(nav, button);
    });
    inputArguments.host.appendToElement(wrapper, nav);
    inputArguments.host.appendToElement(tabs, wrapper);
    return tabs;
};

const renderMcpToolModeGroups = <TKnowledgeState extends JsonValue | null>(inputArguments: { host: McpToolModeRenderHost; container: Element; emptyState: Element; config: McpConfig<TKnowledgeState>; tools: readonly McpTool[]; activeToolTab: McpToolMode; toolModes?: readonly McpToolMode[] | undefined; toolModeAction?: string | undefined; buildToggleSwitch: BuildToggleSwitch; applyServerToolAvailability(serverConfigs: Record<string, boolean>): void; toggleClassName?: string | undefined; toggleIdPrefix?: string | undefined; collapsedToolGroups?: boolean | undefined; toolGroupToggleAction?: string | undefined; toolGroupToggleIcon?: TrustedHtml | undefined; expandedToolGroupIds?: ReadonlySet<string> | undefined; showServerToggles?: boolean | undefined; toolSearchAction?: string | undefined; isSelectionLocked?: McpToolSelectionLockResolver<TKnowledgeState>; resolveLockReason?: McpToolLockReasonResolver<TKnowledgeState> }): void => {
    inputArguments.host.updateHTML(inputArguments.container, '');
    if (inputArguments.tools.length === 0) {
        inputArguments.host.updateText(inputArguments.emptyState, i18n.t('chat.configuration.mcp.noTools'));
        inputArguments.host.toggleClassName(inputArguments.emptyState, 'u-hidden', false);
        return;
    }
    inputArguments.host.toggleClassName(inputArguments.emptyState, 'u-hidden', true);
    const wrapper = inputArguments.host.createElement('div', { class: 'mcp-tools-mode-layout' });
    const toolModes = inputArguments.toolModes ?? MCP_TOOL_MODES;
    const tabs = renderToolModeTabs({ host: inputArguments.host, activeToolTab: inputArguments.activeToolTab, toolModes, ...(inputArguments.toolModeAction ? { toolModeAction: inputArguments.toolModeAction } : {}) });
    if (tabs) {
        inputArguments.host.appendToElement(wrapper, tabs);
    }
    const panels = inputArguments.host.createElement('div', { class: 'mcp-tool-mode-panels' });
    toolModes.forEach((mode) => {
        const panel = inputArguments.host.createElement('div', {
            class: `mcp-tool-mode-panel${mode === inputArguments.activeToolTab ? ' mcp-tool-mode-panel--active' : ''}${mode === inputArguments.activeToolTab ? '' : ' u-hidden'}`,
            'data-tool-mode': mode,
            role: 'tabpanel'
        });
        inputArguments.host.appendToElement(
            panel,
            renderToolGroups({
                host: inputArguments.host,
                mode,
                tools: inputArguments.tools,
                selectedTools: resolveModeToolSelection(inputArguments.config, mode),
                serverConfigs: inputArguments.config.serverConfigs,
                config: inputArguments.config,
                buildToggleSwitch: inputArguments.buildToggleSwitch,
                toggleClassName: inputArguments.toggleClassName ?? 'mcp-tool-toggle mcp-input',
                toggleIdPrefix: inputArguments.toggleIdPrefix ?? 'mcp-tool-toggle',
                collapsed: inputArguments.collapsedToolGroups === true,
                ...(inputArguments.collapsedToolGroups === true && inputArguments.toolGroupToggleAction ? { toggleAction: inputArguments.toolGroupToggleAction } : {}),
                ...(inputArguments.collapsedToolGroups === true && inputArguments.toolGroupToggleIcon ? { toggleIcon: inputArguments.toolGroupToggleIcon } : {}),
                ...(inputArguments.expandedToolGroupIds ? { expandedServerIds: inputArguments.expandedToolGroupIds } : {}),
                showServerToggle: inputArguments.showServerToggles === true && mode === inputArguments.activeToolTab,
                ...(inputArguments.toolSearchAction ? { toolSearchAction: inputArguments.toolSearchAction } : {}),
                ...(inputArguments.isSelectionLocked ? { isSelectionLocked: inputArguments.isSelectionLocked } : {}),
                ...(inputArguments.resolveLockReason ? { resolveLockReason: inputArguments.resolveLockReason } : {})
            })
        );
        inputArguments.host.appendToElement(panels, panel);
    });
    inputArguments.host.appendToElement(wrapper, panels);
    inputArguments.host.appendToElement(inputArguments.container, wrapper);
    inputArguments.applyServerToolAvailability(inputArguments.config.serverConfigs);
};

export { MCP_TOOL_MODES, renderMcpToolModeGroups, resolveMcpToolModeLabel };
export type { McpToolModeRenderHost };
