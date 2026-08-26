/* SoAI - Settings feature MCP render status section [frontend/assets/ts/features/settings/mcp/renderStatusSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { securityApi } from '@core/security/public.ts';
import { renderSection, renderSettingItem, renderSettingsGroup, renderSettingsStatusBadge, renderSettingsSubgroup } from '@core/settings/settingsMarkup.ts';
import { renderSettingsTitlebarRefreshButton } from '@core/settings/titlebarActions.ts';
import { getBadgeColorClass } from '@core/ui/badgeColors.ts';
import { renderEmptyState } from '@core/ui/emptyState.ts';
import { UI_IDS } from '@features/settings/contracts/SettingsPageSupport.ts';
import { MCP_ACTION_REFRESH } from '@features/settings/mcp/actions.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';

const renderMcpStatusValueBadge = (value: string): string => {
    const colorClass = getBadgeColorClass(`mcp-status:${value}`);
    return `<span class="settings-control-value settings-record-badge ui-model-type-badge ${colorClass}">${securityApi.escapeHtml(value)}</span>`;
};

const renderMcpStatusSubgroup = (page: McpManagerHost): string => {
    const mcpData = page.data.getMcpData();
    const status = mcpData.status;
    const refreshButton = renderSettingsTitlebarRefreshButton({ id: UI_IDS.MCP_REFRESH, action: MCP_ACTION_REFRESH, label: i18n.t('settings.mcp.refresh') });

    if (!status) {
        return renderSection({
            title: i18n.t('settings.mcp.status.title'),
            description: i18n.t('settings.mcp.status.description'),
            trailing: refreshButton,
            className: 'settings-section--mcp settings-section--mcp-status',
            content: renderSettingsSubgroup({
                title: i18n.t('settings.mcp.status.title'),
                description: i18n.t('settings.mcp.status.description'),
                content: renderEmptyState({ title: i18n.t('settings.mcp.status.empty'), className: 'ui-empty-state--simple' }).html
            })
        });
    }

    const yesNoBadge = (enabled: boolean): string => renderSettingsStatusBadge(enabled ? i18n.t('common.yes') : i18n.t('common.no'), enabled ? 'active' : 'danger');

    const items = [
        renderSettingItem({
            label: i18n.t('settings.mcp.status.enabled'),
            help: i18n.t('settings.mcp.status.enabledHelp'),
            control: yesNoBadge(status.enabled)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.server_mode'),
            help: i18n.t('settings.mcp.status.serverModeHelp'),
            control: yesNoBadge(status.serverMode.enabled)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.server_mode_active'),
            help: i18n.t('settings.mcp.status.serverModeActiveHelp'),
            control: yesNoBadge(status.serverMode.active)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.host_mode'),
            help: i18n.t('settings.mcp.status.hostModeHelp'),
            control: yesNoBadge(status.hostMode.enabled)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.connected_servers'),
            help: i18n.t('settings.mcp.status.connectedServersHelp'),
            control: renderMcpStatusValueBadge(`${status.hostMode.connectedServers} / ${status.hostMode.totalServers}`)
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.connection_entries'),
            help: i18n.t('settings.mcp.status.connectionEntriesHelp'),
            control: renderMcpStatusValueBadge(String(status.hostMode.connectionEntries))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.server_mode_tools'),
            help: i18n.t('settings.mcp.status.serverModeToolsHelp'),
            control: renderMcpStatusValueBadge(String(status.serverMode.toolsCount))
        }),
        renderSettingItem({
            label: i18n.t('settings.mcp.status.server_mode_resources'),
            help: i18n.t('settings.mcp.status.serverModeResourcesHelp'),
            control: renderMcpStatusValueBadge(String(status.serverMode.resourcesCount))
        })
    ];

    return renderSection({
        title: i18n.t('settings.mcp.status.title'),
        description: i18n.t('settings.mcp.status.description'),
        trailing: refreshButton,
        className: 'settings-section--mcp settings-section--mcp-status',
        content: renderSettingsSubgroup({
            title: i18n.t('settings.mcp.status.title'),
            description: i18n.t('settings.mcp.status.description'),
            content: renderSettingsGroup(items)
        })
    });
};

export { renderMcpStatusSubgroup };
