/* SoAI - MCP configuration section rendering [frontend/assets/ts/features/settings/mcp/renderConfigSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isJsonObject } from '@core/types/jsonValues.ts';
import { renderConfigTreeGroup } from '@features/settings/mcp/configitems/service.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { McpSectionExpansionResolver } from '@features/settings/mcp/mcpSectionExpansionState.ts';
import { renderMcpCollapsibleSection } from '@features/settings/mcp/renderCollapsibleSection.ts';

const renderMcpConfigSubgroup = (page: McpManagerHost, resolveExpanded: McpSectionExpansionResolver): string => {
    const coreConfig = page.data.getCoreConfig();
    const toolsConfig = coreConfig['TOOLS'];
    if (!isJsonObject(toolsConfig)) {
        throw new TypeError('TOOLS must be present in core config for MCP settings');
    }
    if (!isJsonObject(toolsConfig['MCP'])) {
        throw new TypeError('TOOLS.MCP must be present in core config for MCP settings');
    }

    const group = renderConfigTreeGroup(coreConfig, 'TOOLS.MCP');

    return renderMcpCollapsibleSection({
        id: 'config',
        title: i18n.t('settings.mcp.config.title'),
        description: i18n.t('settings.mcp.config.description'),
        className: 'settings-section--mcp settings-section--mcp-config',
        content: group,
        expanded: true,
        resolveExpanded
    });
};

export { renderMcpConfigSubgroup };
