/* SoAI - Settings feature MCP render resources tools prompts sections [frontend/assets/ts/features/settings/mcp/renderResourcesToolsPromptsSections.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import type { McpPromptEntry, McpResourceEntry, McpToolEntry } from '@core/mcp/contracts.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { sanitizeSvgDataUriToHtml } from '@core/svgSanitizer.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';

const resolveCatalogIconHtml = (iconEntries: readonly JsonObject[]): string => {
    if (iconEntries.length === 0) {
        return '';
    }
    const firstIcon = iconEntries[0];
    if (!firstIcon) {
        return '';
    }
    const src = firstIcon['src'];
    if (!isString(src) || !src.trim()) {
        return '';
    }
    try {
        const svgHtml = sanitizeSvgDataUriToHtml(src.trim(), {
            className: 'mcp-catalog-icon',
            ariaHidden: true
        });
        return `<span class="mcp-catalog-icon-wrap">${svgHtml}</span>`;
    } catch (error) {
        const runtimeError = ensureError(error);
        throw runtimeError;
    }
};

const renderCatalogItem = (page: McpManagerHost, name: string, typeBadge: string, description: string | null, serverName: string | null, iconEntries: readonly JsonObject[]): string => {
    const sanitizer = page.services.pageContext.sanitizer;
    const descriptionText = description ? sanitizer.html(description) : i18n.t('settings.mcp.catalog.noDescription');
    const serverLabel = serverName ? sanitizer.html(serverName) : i18n.t('settings.mcp.catalog.unknownServer');
    const iconHtml = resolveCatalogIconHtml(iconEntries);

    return `<div class="settings-record-item mcp-catalog-entry">${iconHtml}<div class="settings-record-info mcp-catalog-info"><div class="settings-record-header mcp-catalog-header"><span class="settings-record-label mcp-catalog-name">${sanitizer.html(name)}</span><span class="settings-record-badge settings-record-badge--neutral mcp-catalog-type-badge">${typeBadge}</span></div><div class="settings-record-meta mcp-catalog-meta"><span class="mcp-catalog-description">${descriptionText}</span><span class="mcp-catalog-server">${i18n.t('settings.mcp.catalog.server')}: ${serverLabel}</span></div></div></div>`;
};

const renderMcpToolsSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const mcpData = page.data.getMcpData();
    const typeBadge = i18n.t('settings.mcp.catalog.tool');
    const sanitizer = page.services.pageContext.sanitizer;
    const title = sanitizer.html(i18n.t('settings.mcp.tools.title'));
    const description = sanitizer.html(i18n.t('settings.mcp.tools.description'));
    const count = mcpData.tools.length;
    const countBadge = `<span class="settings-record-badge settings-record-badge--neutral section-count-badge">${count}</span>`;
    const list = renderSettingsRecordList({
        items: mcpData.tools.map((tool: McpToolEntry) => renderCatalogItem(page, tool.name, typeBadge, tool.description, tool.serverName, tool.icons)),
        empty: renderEmptyState({ title: i18n.t('settings.mcp.tools.empty'), className: 'ui-empty-state--simple' }).html,
        className: 'settings-record-list--tools'
    });

    return renderMcpCollapsibleSection({
        id: 'tools',
        title: `${title} ${countBadge}`,
        description,
        className: 'settings-section--mcp settings-section--mcp-tools',
        content: list,
        resolveExpanded
    });
};

const renderMcpResourcesSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const mcpData = page.data.getMcpData();
    const typeBadge = i18n.t('settings.mcp.catalog.resource');

    return renderMcpCollapsibleSection({
        id: 'resources',
        title: i18n.t('settings.mcp.resources.title'),
        description: i18n.t('settings.mcp.resources.description'),
        className: 'settings-section--mcp settings-section--mcp-resources',
        content: renderSettingsRecordList({
            items: mcpData.resources.map((resource: McpResourceEntry) => renderCatalogItem(page, resource.uri, typeBadge, resource.name ?? resource.description, resource.serverName, resource.icons)),
            empty: renderEmptyState({ title: i18n.t('settings.mcp.resources.empty'), className: 'ui-empty-state--simple' }).html
        }),
        expanded: mcpData.resources.length > 0,
        resolveExpanded
    });
};

const renderMcpPromptsSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const mcpData = page.data.getMcpData();
    const typeBadge = i18n.t('settings.mcp.catalog.prompt');

    return renderMcpCollapsibleSection({
        id: 'prompts',
        title: i18n.t('settings.mcp.prompts.title'),
        description: i18n.t('settings.mcp.prompts.description'),
        className: 'settings-section--mcp settings-section--mcp-prompts',
        content: renderSettingsRecordList({
            items: mcpData.prompts.map((prompt: McpPromptEntry) => renderCatalogItem(page, prompt.name, typeBadge, prompt.description, prompt.serverName, prompt.icons)),
            empty: renderEmptyState({ title: i18n.t('settings.mcp.prompts.empty'), className: 'ui-empty-state--simple' }).html
        }),
        expanded: mcpData.prompts.length > 0,
        resolveExpanded
    });
};

export { renderMcpPromptsSubgroup, renderMcpResourcesSubgroup, renderMcpToolsSubgroup };
