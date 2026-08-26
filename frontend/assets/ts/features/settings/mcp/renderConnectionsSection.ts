/* SoAI - Settings feature MCP render connections section [frontend/assets/ts/features/settings/mcp/renderConnectionsSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpConnection } from '@core/mcp/contracts.ts';
import { formatPositiveEpochMsWithFallback } from '@core/primitives/dateTime.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';
import { resolveServerStatusLabel, resolveTransportLabel } from '@features/settings/mcp/view.ts';

const resolveConnectionStatusClass = (status: string): string => {
    if (status === 'connected') return 'settings-record-badge--active';
    if (status === 'auth_required' || status === 'connecting' || status === 'reconnecting') return 'settings-record-badge--warning';
    if (status === 'error') return 'settings-record-badge--danger';
    return 'settings-record-badge--neutral';
};

const renderConnectionCounts = (connection: McpConnection, sanitizer: PageSanitizer): string => {
    const toolsCount = connection.toolsCount === null ? i18n.t('settings.mcp.connections.unknownCount') : String(connection.toolsCount);
    const resourcesCount = connection.resourcesCount === null ? i18n.t('settings.mcp.connections.unknownCount') : String(connection.resourcesCount);
    return sanitizer.html(i18n.t('settings.mcp.connections.catalogCounts', { tools: toolsCount, resources: resourcesCount }));
};

const renderConnectionItem = (page: McpManagerHost, connection: McpConnection): string => {
    const sanitizer = page.services.pageContext.sanitizer;
    const statusClass = resolveConnectionStatusClass(connection.status);
    const statusLabel = sanitizer.html(resolveServerStatusLabel(connection.status));
    const transportLabel = sanitizer.html(resolveTransportLabel(connection.transportType));
    const endpoint = sanitizer.html(connection.endpoint);
    const connectedAt = sanitizer.html(formatPositiveEpochMsWithFallback(connection.connectedAtMs, i18n.t('settings.mcp.connections.notConnected')));
    const lastError = connection.lastError ? `<div class="settings-record-description mcp-connection-error">${sanitizer.html(connection.lastError)}</div>` : '';

    return `<div class="settings-record-item" data-connection-id="${sanitizer.attribute(connection.id)}"><div class="settings-record-info mcp-connection-info"><div class="settings-record-header mcp-connection-header"><span class="settings-record-label mcp-connection-name">${sanitizer.html(connection.name)}</span><span class="settings-record-badge ${statusClass}">${statusLabel}</span></div><div class="settings-record-meta mcp-connection-meta"><span>${transportLabel}</span><span>${endpoint}</span><span>${i18n.t('settings.mcp.connections.connectedAt')}: ${connectedAt}</span><span>${renderConnectionCounts(connection, sanitizer)}</span></div>${lastError}</div></div>`;
};

const renderMcpConnectionsSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const connections = page.data.getMcpData().connections;
    return renderMcpCollapsibleSection({
        id: 'connections',
        title: i18n.t('settings.mcp.connections.title'),
        description: i18n.t('settings.mcp.connections.description'),
        className: 'settings-section--mcp settings-section--mcp-connections',
        content: renderSettingsRecordList({
            id: UI_IDS.MCP_CONNECTION_LIST,
            items: connections.map((connection) => renderConnectionItem(page, connection)),
            empty: renderEmptyState({ title: i18n.t('settings.mcp.connections.empty'), className: 'ui-empty-state--simple' }).html
        }),
        expanded: connections.length > 0,
        resolveExpanded
    });
};

export { renderMcpConnectionsSubgroup };
