/* SoAI - MCP conversation settings configuration comparison [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/configComparison.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { McpConfig, McpFormValues } from '@features/chat/conversationsettings/settingsModels.ts';
import { haveMcpFormValuesChanged, normalizeMcpConfigValues } from '@core/mcp/toolChangeSurfaces.ts';

const hasMcpConfigChanges = (currentValues: McpFormValues, baselineConfig: McpConfig): boolean => {
    return haveMcpFormValuesChanged(currentValues, normalizeMcpConfigValues(baselineConfig));
};

export { hasMcpConfigChanges };
