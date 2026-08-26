/* SoAI - Settings feature MCP render servers section [frontend/assets/ts/features/settings/mcp/renderServersSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { McpServer } from '@core/mcp/contracts.ts';
import { renderLabelAttributes } from '@core/security/public.ts';
import { renderSettingsRecordList } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarAddButton } from '@core/settings/titlebarActions.ts';
import { renderToggleSwitch, type ToggleLabelState } from '@core/toggleSwitch.ts';
import { renderControlDisabledAttributes } from '@core/ui/controls/disabledState.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import type { PageSanitizer } from '@features/settings/contracts/contracts.ts';
import { MCP_ACTION_SERVER_ADD, MCP_ACTION_SERVER_AUTHORIZE, MCP_ACTION_SERVER_CLEAR_AUTH, MCP_ACTION_SERVER_CONNECT, MCP_ACTION_SERVER_DELETE, MCP_ACTION_SERVER_DISCONNECT, MCP_ACTION_SERVER_EDIT, MCP_ACTION_SERVER_ENABLED_CHANGE } from '@features/settings/mcp/actions.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { isMcpServerOauthAuth } from '@features/settings/mcp/mcpServerFormRules.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';
import { getPreferenceStateLabels, resolveOauthStatusLabel, resolveServerStatusClass, resolveServerStatusLabel, resolveTransportLabel } from '@features/settings/mcp/view.ts';
import { isSettingsOauthActionBlockedStatus } from '@features/settings/oauthValues.ts';

const buildServerHeader = (server: McpServer, sanitizer: PageSanitizer, statusClass: string, statusLabel: string): string => {
    const oauthStatus = resolveOauthStatusLabel(server);
    const oauthBadge = oauthStatus ? `<span class="settings-record-badge settings-record-badge--neutral">${sanitizer.html(oauthStatus)}</span>` : '';
    return `<div class="settings-record-header mcp-server-header"><span class="settings-record-label mcp-server-name">${sanitizer.html(server.name)}</span>${oauthBadge}<span class="settings-record-badge ${statusClass}">${statusLabel}</span></div>`;
};

const buildServerMeta = (server: McpServer, sanitizer: PageSanitizer): string => {
    const transportLabel = i18n.t('settings.mcp.servers.form.transport.label');
    const transportValue = sanitizer.html(resolveTransportLabel(server.transportType));
    const endpointValue = sanitizer.html(server.endpoint);
    return `<div class="settings-record-meta mcp-server-details"><span>${transportLabel}: ${transportValue}</span><span>${endpointValue}</span></div>`;
};

const buildServerError = (lastError: string, sanitizer: PageSanitizer): string => {
    return `<div class="settings-record-description mcp-server-error">${sanitizer.html(lastError)}</div>`;
};

const buildServerActions = (server: McpServer, sanitizer: PageSanitizer, labels: ToggleLabelState): string => {
    const serverId = sanitizer.attribute(server.id);
    const oauthStatus = server.oauthStatus ?? 'none';
    const oauthBlocksConnect = isMcpServerOauthAuth(server.authType) && isSettingsOauthActionBlockedStatus(oauthStatus);
    const canConnect = server.enabled && !oauthBlocksConnect;
    const connectLabel = i18n.t('settings.mcp.servers.actions.connect');
    const disconnectLabel = i18n.t('settings.mcp.servers.actions.disconnect');
    const connectButton = server.status === 'connected' ? `<button type="button" data-action="${MCP_ACTION_SERVER_DISCONNECT}" class="ui-button ui-button--sm ui-variant-neutral mcp-server-disconnect-btn" data-server-id="${serverId}" ${renderLabelAttributes(disconnectLabel)}>${disconnectLabel}</button>` : `<button type="button" data-action="${MCP_ACTION_SERVER_CONNECT}" class="ui-button ui-button--sm ui-variant-primary mcp-server-connect-btn" data-server-id="${serverId}"${renderControlDisabledAttributes(!canConnect)} ${renderLabelAttributes(connectLabel)}>${connectLabel}</button>`;

    const toggle = renderToggleSwitch({
        id: `mcp-server-enabled-${server.id}`,
        checked: server.enabled,
        labels,
        inputClassName: 'mcp-server-enabled-toggle',
        inputDataset: {
            action: MCP_ACTION_SERVER_ENABLED_CHANGE,
            serverId: server.id,
            enabled: server.enabled ? 'true' : 'false'
        },
        showLabel: false
    });

    const editLabel = i18n.t('settings.mcp.servers.actions.edit');
    const deleteLabel = i18n.t('settings.mcp.servers.actions.delete');
    const editButton = `<button type="button" data-action="${MCP_ACTION_SERVER_EDIT}" class="ui-button ui-button--sm ui-variant-warning mcp-server-edit-btn" data-server-id="${serverId}" ${renderLabelAttributes(editLabel)}>${editLabel}</button>`;
    const deleteButton = `<button type="button" data-action="${MCP_ACTION_SERVER_DELETE}" class="ui-button ui-button--sm ui-variant-danger mcp-server-delete-btn" data-server-id="${serverId}" ${renderLabelAttributes(deleteLabel)}>${deleteLabel}</button>`;

    const oauthActions = (() => {
        if (!isMcpServerOauthAuth(server.authType)) {
            return '';
        }
        const authorizeLabel = server.oauthStatus === 'ready' ? i18n.t('settings.mcp.servers.actions.reauthorize') : i18n.t('settings.mcp.servers.actions.authorize');
        const disabledAttributes = renderControlDisabledAttributes(!server.enabled);
        const clearAuthLabel = i18n.t('settings.mcp.servers.actions.clearAuth');
        const authorizeButton = `<button type="button" data-action="${MCP_ACTION_SERVER_AUTHORIZE}" class="ui-button ui-button--sm ui-variant-accent" data-server-id="${serverId}"${disabledAttributes} ${renderLabelAttributes(authorizeLabel)}>${authorizeLabel}</button>`;
        const clearButton = `<button type="button" data-action="${MCP_ACTION_SERVER_CLEAR_AUTH}" class="ui-button ui-button--sm ui-variant-neutral" data-server-id="${serverId}"${disabledAttributes} ${renderLabelAttributes(clearAuthLabel)}>${clearAuthLabel}</button>`;
        return `${authorizeButton}${clearButton}`;
    })();

    return `<div class="settings-record-actions mcp-server-actions">${toggle}${oauthActions}${connectButton}${editButton}${deleteButton}</div>`;
};

const renderServerItem = (page: McpManagerHost, server: McpServer): string => {
    const sanitizer = page.services.pageContext.sanitizer;
    const preferenceLabels = getPreferenceStateLabels();
    const statusClass = resolveServerStatusClass(server);
    const statusLabel = resolveServerStatusLabel(server.status);
    const header = buildServerHeader(server, sanitizer, statusClass, statusLabel);
    const meta = buildServerMeta(server, sanitizer);
    const errorMarkup = server.lastError ? buildServerError(server.lastError, sanitizer) : '';
    const actions = buildServerActions(server, sanitizer, preferenceLabels);

    return `<div class="settings-record-item" data-server-id="${sanitizer.attribute(server.id)}"><div class="settings-record-info mcp-server-info">${header}${meta}${errorMarkup}</div>${actions}</div>`;
};

const renderServerList = (page: McpManagerHost): string => {
    const servers = page.data.getMcpData().servers;
    return renderSettingsRecordList({
        id: UI_IDS.MCP_SERVER_LIST,
        items: servers.map((server) => renderServerItem(page, server)),
        empty: renderEmptyState({ title: i18n.t('settings.mcp.servers.empty'), className: 'ui-empty-state--simple' }).html
    });
};

const renderMcpServersSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const list = renderServerList(page);
    const addButtonLabel = i18n.t('settings.mcp.servers.actions.addServer');
    const addButton = renderSettingsTitlebarAddButton({ id: UI_IDS.MCP_SERVER_ADD, action: MCP_ACTION_SERVER_ADD, label: addButtonLabel });
    const hasServers = page.data.getMcpData().servers.length > 0;

    return renderMcpCollapsibleSection({
        id: 'servers',
        title: i18n.t('settings.mcp.servers.title'),
        description: i18n.t('settings.mcp.servers.description'),
        className: 'settings-section--mcp settings-section--mcp-servers',
        trailing: addButton,
        content: list,
        expanded: hasServers,
        resolveExpanded
    });
};

export { renderMcpServersSubgroup };
