/* SoAI - Shared frontend MCP tool group rendering [frontend/assets/ts/core/mcp/toolGroupRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpConfig, McpServerGroup, McpTool, McpToolMode } from '@core/mcp/configTypes.ts';
import { isServerEnabled } from '@core/mcp/serverSettings.ts';
import { buildServerGroups, isToolAvailable } from '@core/mcp/toolCatalog.ts';
import { decodeAndInjectSvgIcon, normalizeToolNameForDisplay, resolveToolDescription, resolveToolIconSrc } from '@core/mcp/toolPresentation.ts';
import { createSearchTextIndex } from '@core/search/searchQuery.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { createSearchFieldActions } from '@core/ui/searchField.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

const TOOL_SEARCH_MIN_TOOLS = 6;

type McpElementAttributeValue = string | number | boolean;
type McpElementAttributes = Record<string, McpElementAttributeValue>;

interface McpToolGroupRenderHost {
    createElement(tag: string, options?: McpElementAttributes, content?: string | Node): HTMLElement;
    appendToElement(parent: Element, child: Node | Node[]): void;
    updateText(element: Element, text: string): void;
    dom: { getDocument(): Document };
}

type BuildToggleSwitch = (options: { id: string; className: string; checked: boolean; data?: Record<string, string>; disabled?: boolean }) => HTMLElement;

type McpToolSelectionLockResolver<TKnowledgeState extends JsonValue | null> = (config: McpConfig<TKnowledgeState>, tool: McpTool) => boolean;

type McpToolLockReasonResolver<TKnowledgeState extends JsonValue | null> = (config: McpConfig<TKnowledgeState>, tool: McpTool) => string | null;

const renderToolGroups = <TKnowledgeState extends JsonValue | null>(inputArguments: { host: McpToolGroupRenderHost; mode: McpToolMode; tools: readonly McpTool[]; selectedTools: Set<string>; serverConfigs: Record<string, boolean>; config: McpConfig<TKnowledgeState>; buildToggleSwitch: BuildToggleSwitch; toggleClassName?: string; toggleIdPrefix?: string; collapsed?: boolean; toggleAction?: string; toggleIcon?: TrustedHtml; expandedServerIds?: ReadonlySet<string>; showServerToggle?: boolean; toolSearchAction?: string; isSelectionLocked?: McpToolSelectionLockResolver<TKnowledgeState>; resolveLockReason?: McpToolLockReasonResolver<TKnowledgeState> }): HTMLElement => {
    const toggleCls = typeof inputArguments.toggleClassName === 'string' && inputArguments.toggleClassName.trim() ? inputArguments.toggleClassName : 'mcp-tool-toggle mcp-input';
    const togglePrefix = typeof inputArguments.toggleIdPrefix === 'string' && inputArguments.toggleIdPrefix.trim() ? inputArguments.toggleIdPrefix : 'mcp-tool-toggle';
    const groupContainer = inputArguments.host.createElement('div', { class: 'mcp-tool-groups' });
    const groups = buildServerGroups({
        serverConfigs: {},
        tools: inputArguments.tools,
        includeBuiltin: true
    }).filter((group) => group.tools.length > 0);

    groups.forEach((group, groupIndex) => {
        const panelId = `${togglePrefix}-${inputArguments.mode}-${groupIndex}-panel`;
        const collapsed = inputArguments.collapsed === true && !inputArguments.expandedServerIds?.has(group.id);
        const groupElement = inputArguments.host.createElement('div', {
            class: `mcp-tool-group ${collapsed ? 'is-collapsed' : 'is-expanded'}`,
            'data-server-id': group.id
        });
        const header = inputArguments.host.createElement('div', {
            class: `mcp-tool-group-header${inputArguments.collapsed === true ? ' setting-change-surface' : ''}`,
            'data-server-id': group.id
        });
        const title = inputArguments.host.createElement('span', { class: 'mcp-tool-group-title' });
        inputArguments.host.updateText(title, group.name);
        const headerContentOptions: McpElementAttributes = { class: 'mcp-tool-group-toggle-button' };
        if (inputArguments.toggleAction) {
            headerContentOptions['type'] = 'button';
            headerContentOptions['data-action'] = inputArguments.toggleAction;
            headerContentOptions['aria-expanded'] = collapsed ? 'false' : 'true';
            headerContentOptions['aria-controls'] = panelId;
        }
        const headerContent = inputArguments.host.createElement(inputArguments.toggleAction ? 'button' : 'div', headerContentOptions);
        const countBadge = inputArguments.host.createElement('span', { class: `ui-model-type-badge mcp-tool-count-badge ${getBadgeColorClass(group.id)}` });
        inputArguments.host.updateText(countBadge, i18n.t('chat.configuration.mcp.toolCountBadge', { count: group.tools.length }));
        inputArguments.host.appendToElement(headerContent, title);
        inputArguments.host.appendToElement(headerContent, countBadge);
        inputArguments.host.appendToElement(header, headerContent);
        if (inputArguments.showServerToggle === true) {
            inputArguments.host.appendToElement(
                header,
                inputArguments.buildToggleSwitch({
                    id: `${togglePrefix}-${inputArguments.mode}-${groupIndex}-server`,
                    className: 'mcp-server-toggle mcp-input',
                    checked: isServerEnabled(group.id, inputArguments.serverConfigs),
                    data: { serverId: group.id },
                    disabled: false
                })
            );
        }
        if (inputArguments.toggleAction) {
            if (!inputArguments.toggleIcon) {
                throw new Error('MCP collapsible tool groups require a toggle icon');
            }
            const collapseButton = inputArguments.host.createElement('button', {
                type: 'button',
                class: `mcp-tool-group-chevron-button mcp-tool-group-collapse-toggle ui-icon-button ui-icon-button--titlebar ui-variant-neutral${collapsed ? ' mcp-tool-group-collapse-toggle--collapsed' : ''}`,
                'data-action': inputArguments.toggleAction,
                'aria-expanded': collapsed ? 'false' : 'true',
                'aria-controls': panelId
            });
            inputArguments.host.appendToElement(collapseButton, createIconSlot(inputArguments.host.dom.getDocument(), inputArguments.toggleIcon));
            inputArguments.host.appendToElement(header, collapseButton);
        }
        inputArguments.host.appendToElement(groupElement, header);
        renderToolGroupBody({ ...inputArguments, group, groupElement, panelId, toggleCls, togglePrefix, groupIndex });
        inputArguments.host.appendToElement(groupContainer, groupElement);
    });

    return groupContainer;
};

const renderToolSearchBar = (host: McpToolGroupRenderHost, toolSearchAction: string): HTMLElement => {
    const container = host.createElement('div', { class: 'searchbar-container searchbar-container--collection mcp-tool-search' });
    const input = host.createElement('input', {
        type: 'text',
        class: 'searchbar-input mcp-tool-search-input',
        'data-action': toolSearchAction,
        autocomplete: 'off',
        placeholder: i18n.t('chat.configuration.mcp.toolSearch.placeholder')
    });
    host.appendToElement(container, input);
    host.appendToElement(container, [...createSearchFieldActions(host.dom.getDocument())]);
    return container;
};

const renderToolGroupBody = <TKnowledgeState extends JsonValue | null>(inputArguments: { host: McpToolGroupRenderHost; mode: McpToolMode; group: McpServerGroup; groupElement: HTMLElement; panelId: string; selectedTools: Set<string>; serverConfigs: Record<string, boolean>; config: McpConfig<TKnowledgeState>; buildToggleSwitch: BuildToggleSwitch; toggleCls: string; togglePrefix: string; groupIndex: number; toolSearchAction?: string; isSelectionLocked?: McpToolSelectionLockResolver<TKnowledgeState>; resolveLockReason?: McpToolLockReasonResolver<TKnowledgeState> }): void => {
    const body = inputArguments.host.createElement('div', { id: inputArguments.panelId, class: 'mcp-tool-group-body', 'aria-hidden': inputArguments.groupElement.classList.contains('is-collapsed') ? 'true' : 'false' });
    const bodyInner = inputArguments.host.createElement('div', { class: 'mcp-tool-group-body-inner' });
    if (inputArguments.toolSearchAction && inputArguments.group.tools.length >= TOOL_SEARCH_MIN_TOOLS) {
        inputArguments.host.appendToElement(bodyInner, renderToolSearchBar(inputArguments.host, inputArguments.toolSearchAction));
    }
    inputArguments.group.tools.forEach((tool, toolIndex) => {
        const available = isToolAvailable(tool, inputArguments.serverConfigs);
        const lockedSelection = inputArguments.isSelectionLocked ? inputArguments.isSelectionLocked(inputArguments.config, tool) : false;
        const row = inputArguments.host.createElement('div', {
            class: 'mcp-tool-item setting-change-surface',
            'data-server-id': inputArguments.group.id,
            'data-tool-search': createSearchTextIndex([tool.name, normalizeToolNameForDisplay(tool.name), resolveToolDescription(tool) ?? ''])
        });
        if (tool.blockedReason) {
            setTooltipText(row, tool.blockedReason);
        }
        const lockReason = inputArguments.resolveLockReason ? inputArguments.resolveLockReason(inputArguments.config, tool) : null;
        if (lockReason) {
            setTooltipText(row, lockReason);
        }
        renderToolInfo(inputArguments.host, row, tool);
        inputArguments.host.appendToElement(
            row,
            inputArguments.buildToggleSwitch({
                id: `${inputArguments.togglePrefix}-${inputArguments.mode}-${inputArguments.groupIndex}-${toolIndex}`,
                className: inputArguments.toggleCls,
                checked: lockedSelection || (available && inputArguments.selectedTools.has(tool.name)),
                data: {
                    toolName: tool.name,
                    serverId: inputArguments.group.id,
                    toolMode: inputArguments.mode,
                    toolAllowed: tool.allowed ? 'true' : 'false',
                    selectionLocked: lockedSelection ? 'true' : 'false'
                },
                disabled: lockedSelection || !available
            })
        );
        bodyInner.appendChild(row);
    });
    inputArguments.host.appendToElement(body, bodyInner);
    inputArguments.host.appendToElement(inputArguments.groupElement, body);
};

const renderToolInfo = (host: McpToolGroupRenderHost, row: Element, tool: McpTool): void => {
    const info = host.createElement('div', { class: 'mcp-tool-info' });
    const nameRow = host.createElement('div', { class: 'mcp-tool-name-row' });
    const toolIconSrc = resolveToolIconSrc(tool);
    const toolIconSvg = toolIconSrc ? decodeAndInjectSvgIcon(toolIconSrc) : null;
    if (toolIconSvg) {
        host.appendToElement(nameRow, toolIconSvg);
    }
    const name = host.createElement('div', { class: 'mcp-tool-name' });
    host.updateText(name, normalizeToolNameForDisplay(tool.name));
    setTooltipText(name, tool.name);
    host.appendToElement(nameRow, name);
    host.appendToElement(info, nameRow);
    const desc = resolveToolDescription(tool);
    if (desc) {
        const description = host.createElement('div', { class: 'mcp-tool-description' });
        host.updateText(description, desc);
        host.appendToElement(info, description);
    }
    host.appendToElement(row, info);
};

export { buildServerGroups, isToolAvailable, renderToolGroups };
export type { BuildToggleSwitch, McpElementAttributes, McpElementAttributeValue, McpToolGroupRenderHost, McpToolLockReasonResolver, McpToolSelectionLockResolver };
