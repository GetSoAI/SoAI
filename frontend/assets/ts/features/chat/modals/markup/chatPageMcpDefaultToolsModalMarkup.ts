/* SoAI - Chat feature page MCP default tools modal markup [frontend/assets/ts/features/chat/modals/markup/chatPageMcpDefaultToolsModalMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildMcpDefaultToolsModalBodyMarkup } from '@core/mcp/conversationSettingsMarkup.ts';
import { renderModalFooterCloseButton } from '@core/modals/footerButtons.ts';
import { i18n } from '@core/i18n/index.ts';
import { renderModalBody, renderModalScaffoldMarkup, renderSplitModalFooter, renderStandardModalHeader } from '@core/modals/scaffold.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS } from '@features/chat/conversationsettings/mcpconversationsettingscontroller/actionIds.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { CHAT_MCP_DEFAULT_TOOLS_MODAL_ID } from '@features/chat/modals/constants.ts';

const buildChatMcpDefaultToolsModalMarkup = (context: ChatPageMarkupContext): TrustedHtml => {
    const { strings } = context;
    const modalId = CHAT_MCP_DEFAULT_TOOLS_MODAL_ID;
    const header = renderStandardModalHeader({ modalId, title: strings.mcpDefaultToolsModalTitle, description: i18n.t('common.modalDescriptions.chatMcpDefaultTools'), closeLabel: strings.closeLabel });
    const body = renderModalBody(
        toTrustedHtml(
            buildMcpDefaultToolsModalBodyMarkup({
                modalId,
                strings: {
                    toolsTitle: strings.mcpTools,
                    toolsEmpty: strings.mcpToolsEmpty
                },
                resetTools: {
                    title: strings.mcpResetToolsTitle,
                    description: strings.mcpResetToolsDescription,
                    label: strings.mcpResetToolsLabel,
                    action: MCP_CONVERSATION_ACTION_RESET_TOOL_MODE_DEFAULTS
                }
            })
        )
    );
    const footer = renderSplitModalFooter({
        left: renderModalFooterCloseButton({ modalId, text: strings.close, ariaLabel: strings.closeLabel })
    });
    return renderModalScaffoldMarkup({ id: modalId, contentClassName: 'chat-mcp-default-tools-modal-content', header, body, footer, rootAttributes: { 'data-page-scope': 'chat' } });
};

export { buildChatMcpDefaultToolsModalMarkup };
