/* SoAI - Settings feature MCP render collapsible section [frontend/assets/ts/features/settings/mcp/renderCollapsibleSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { securityApi } from '@core/security/public.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { MCP_ACTION_SECTION_TOGGLE } from '@features/settings/mcp/actions.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';

interface McpCollapsibleSectionOptions {
    id: string;
    title: string;
    description?: string;
    trailing?: string;
    className?: string;
    content: string;
    expanded?: boolean;
    resolveExpanded?: McpSectionExpansionResolver;
}

const renderMcpCollapsibleSection = (options: McpCollapsibleSectionOptions): string => {
    const sectionId = `settings-mcp-${options.id}`;
    const panelId = `${sectionId}-panel`;
    const classSuffix = options.className ? ` ${securityApi.escapeAttribute(options.className)}` : '';
    const escapedSectionId = securityApi.escapeAttribute(sectionId);
    const escapedPanelId = securityApi.escapeAttribute(panelId);
    const escapedAction = securityApi.escapeAttribute(MCP_ACTION_SECTION_TOGGLE);
    const escapedTitle = securityApi.escapeAttribute(options.title);
    const fallbackExpanded = options.expanded === true;
    const expanded = options.resolveExpanded ? options.resolveExpanded(sectionId, fallbackExpanded) : fallbackExpanded;
    const expandedAttribute = expanded ? 'true' : 'false';
    const hiddenAttribute = expanded ? 'false' : 'true';
    const sectionStateClass = expanded ? 'is-expanded' : 'is-collapsed';
    const chevronStateClass = expanded ? '' : ' mcp-tool-group-collapse-toggle--collapsed';
    const description = options.description ? `<p class="section-description">${options.description}</p>` : '';
    const trailing = options.trailing ? `<div class="section-header-end">${options.trailing}</div>` : '';
    const icon = renderIconSlot(getIconSync('chevron-left', { size: 14, strokeWidth: 2 }));
    const titleBlock = `<div><h2 class="section-title">${options.title}</h2>${description}</div>`;
    const chevron = `<button type="button" class="mcp-tool-group-chevron-button mcp-tool-group-collapse-toggle ui-icon-button ui-icon-button--titlebar ui-variant-neutral${chevronStateClass}" data-action="${escapedAction}" aria-label="${escapedTitle}" data-tooltip="${escapedTitle}" aria-expanded="${expandedAttribute}" aria-controls="${escapedPanelId}">${icon}</button>`;
    const header = `<div class="section-header mcp-tool-group-header" data-action="${escapedAction}" data-server-id="${escapedSectionId}">${titleBlock}${trailing}${chevron}</div>`;
    const body = `<div id="${escapedPanelId}" class="section-content settings-mcp-section-body mcp-tool-group-body" aria-hidden="${hiddenAttribute}"><div class="mcp-tool-group-body-inner">${options.content}</div></div>`;
    return `<div class="settings-section settings-section--mcp settings-section--mcp-collapsible mcp-tool-group ${sectionStateClass}${classSuffix}" data-server-id="${escapedSectionId}">${header}${body}</div>`;
};

export { renderMcpCollapsibleSection };
export type { McpCollapsibleSectionOptions };
