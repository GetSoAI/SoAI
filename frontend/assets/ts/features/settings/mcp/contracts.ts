/* SoAI - Settings feature MCP boundary contracts [frontend/assets/ts/features/settings/mcp/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpConnection, McpInteractionEntry, McpPromptEntry, McpResourceEntry, McpRootEntry, McpSearchKeyEntry, McpServer, McpStatus, McpToolEntry } from '@core/mcp/contracts.ts';
import type { McpManagerHost } from '@features/settings/mcp/mcpManagerTypes.ts';
import type { SettledSettingsCapability } from '@features/settings/capabilityAvailability.ts';

type McpManagerDataHost = Pick<McpManagerHost, 'services' | 'data'>;

interface McpSearchData {
    keys: McpSearchKeyEntry[];
    providers: string[];
}

interface McpManagerDataRefresh {
    status: SettledSettingsCapability<McpStatus | null>;
    servers: SettledSettingsCapability<McpServer[]>;
    connections: SettledSettingsCapability<McpConnection[]>;
    search: SettledSettingsCapability<McpSearchData>;
    roots: SettledSettingsCapability<McpRootEntry[]>;
    interactions: SettledSettingsCapability<McpInteractionEntry[]>;
    tools: SettledSettingsCapability<McpToolEntry[]>;
    resources: SettledSettingsCapability<McpResourceEntry[]>;
    prompts: SettledSettingsCapability<McpPromptEntry[]>;
}

export type { McpManagerDataHost, McpManagerDataRefresh };
