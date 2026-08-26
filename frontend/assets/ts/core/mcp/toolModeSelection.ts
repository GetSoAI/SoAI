/* SoAI - Shared frontend MCP tool mode selection [frontend/assets/ts/core/mcp/toolModeSelection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpToolMode } from '@core/mcp/configTypes.ts';

type McpToolModeSelectionConfig = {
    defaultTools: string[];
    planTools: string[];
    executeTools: string[];
};

const isMcpToolMode = (value: string | null): value is McpToolMode => value === 'default' || value === 'plan' || value === 'execute';

const resolveMcpToolsForMode = (config: McpToolModeSelectionConfig, mode: McpToolMode): string[] => {
    if (mode === 'plan') {
        return config.planTools;
    }
    if (mode === 'execute') {
        return config.executeTools;
    }
    return config.defaultTools;
};

const resolveMcpToolFieldForMode = (mode: McpToolMode): keyof McpToolModeSelectionConfig => {
    if (mode === 'plan') {
        return 'planTools';
    }
    if (mode === 'execute') {
        return 'executeTools';
    }
    return 'defaultTools';
};

export { isMcpToolMode, resolveMcpToolFieldForMode, resolveMcpToolsForMode };
export type { McpToolModeSelectionConfig };
