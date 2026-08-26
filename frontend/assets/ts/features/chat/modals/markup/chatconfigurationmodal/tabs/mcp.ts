/* SoAI - Chat feature MCP [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/mcp.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { buildMcpConversationSettingsBodyMarkup } from '@core/mcp/conversationSettingsMarkup.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { MCP_CONVERSATION_ACTION_AUTO_TOGGLE, MCP_CONVERSATION_ACTION_OPEN_DEFAULT_TOOLS, MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';
import { CHAT_CONFIGURATION_MODAL_ID, CHAT_MCP_DEFAULT_TOOLS_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildMcpTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, sanitizer, sectionHeader } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('mcp-content')}" class="tab-content chat-configuration-mcp-content">
  <div class="chat-config-grid">
  <div class="chat-config-span-2">
    <div class="chat-configuration-hint mcp-automation-ephemeral-hint u-hidden">${i18n.html(sanitizer, 'chat.configuration.mcp.automationEphemeralHint')}</div>
    ${buildMcpConversationSettingsBodyMarkup({
        modalId,
        toolsEnabledToggle: {
            label: strings.mcpToolsEnabled,
            hint: strings.mcpToolsEnabledHint,
            action: MCP_CONVERSATION_ACTION_AUTO_TOGGLE
        },
        toolApprovalRequiredToggle: {
            label: strings.mcpToolApprovalRequired,
            hint: strings.mcpToolApprovalRequiredHint,
            action: MCP_CONVERSATION_ACTION_AUTO_TOGGLE
        },
        defaultTools: {
            modalId: CHAT_MCP_DEFAULT_TOOLS_MODAL_ID,
            title: strings.mcpDefaultToolsTitle,
            open: strings.mcpDefaultToolsOpen,
            summary: strings.mcpDefaultToolsSummary,
            summaryHint: strings.mcpDefaultToolsSummaryHint,
            openTitleAttr: i18n.attr(sanitizer, 'chat.configuration.mcp.defaultTools.open'),
            triggerAction: MCP_CONVERSATION_ACTION_OPEN_DEFAULT_TOOLS
        },
        resetTools: {
            title: strings.mcpResetToolsTitle,
            description: strings.mcpResetToolsDescription,
            label: strings.mcpResetToolsLabel,
            action: MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS
        },
        strings: {
            serversEmpty: strings.mcpServersEmpty,
            toolsEmpty: strings.mcpToolsEmpty,
            enabledLabelAttr: strings.enabledLabelAttr,
            disabledLabelAttr: strings.disabledLabelAttr,
            disabledLabel: strings.disabledLabel
        }
    })}
  </div>
  ${sectionHeader(strings.mcpTitle)}
  </div>
</div>
`;
};

export { buildMcpTabMarkup };
