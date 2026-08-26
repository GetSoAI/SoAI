/* SoAI - MCP conversation settings public contracts [frontend/assets/ts/features/chat/conversationsettings/mcpconversationsettingscontroller/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ConversationSettingsHost } from '@features/chat/conversationsettings/conversationSettingsHost.ts';
import type { McpCanonicalToolDefaults, McpConfig, McpTool } from '@features/chat/conversationsettings/settingsModels.ts';

interface McpConversationSettingsControllerDependencies {
    host: ConversationSettingsHost;
    readConversationId(): string | null;
    readMcpConfig(): McpConfig | null;
    writeMcpConfig(config: McpConfig | null): void;
    readMcpTools(): McpTool[];
    writeMcpTools(tools: McpTool[]): void;
    readMcpCanonicalToolDefaults(): McpCanonicalToolDefaults | null;
    writeMcpCanonicalToolDefaults(defaults: McpCanonicalToolDefaults | null): void;
    onDirtyStateChange(hasChanges: boolean): void;
}

interface McpToggleSwitchOptions {
    id: string;
    className: string;
    checked: boolean;
    data?: Record<string, string>;
    disabled?: boolean;
}

type McpToggleSwitchBuilder = (options: McpToggleSwitchOptions) => HTMLElement;

export type { McpConversationSettingsControllerDependencies, McpToggleSwitchBuilder, McpToggleSwitchOptions };
