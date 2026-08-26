/* SoAI - Chat page shell sidebar markup [frontend/assets/ts/pages/chat/controllers/page/markup/chatPageShellSidebarMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes } from '@core/security/public.ts';
import type { ChatPageMarkupContext } from '@features/chat/public.ts';
import { buildConversationToolbarMarkup } from '@pages/chat/widgets/conversationtoolbar/markup.ts';

const buildChatContainerAndSidebarMarkup = (context: ChatPageMarkupContext): string => {
    const { strings } = context;
    const toolbarHtml = buildConversationToolbarMarkup({
        toolbarExpand: strings.toolbarExpand,
        toolbarSelect: strings.toolbarSelect,
        toolbarArchive: strings.toolbarArchive,
        toolbarBatchArchive: strings.toolbarBatchArchive,
        toolbarBatchDelete: strings.toolbarBatchDelete,
        toolbarBatchClone: strings.toolbarBatchClone,
        toolbarExitSelect: strings.toolbarExitSelect
    });
    return `
        <div class="chat-sidebar glass-surface-strong">
        <div class="chat-sidebar-header">
        <div class="model-selector page-header-filter-select" data-chat-model-control="true" data-scope="sidebar" ${renderLabelAttributes(strings.selectModel)}></div>
        <button type="button" class="new-conversation-btn ui-icon-button" data-action="chat:new-conversation" ${renderLabelAttributes(strings.newConversation)}></button>
        </div>
        <div id="chat-search-container" class="chat-search-container"><button type="button" class="favorite-toggle-btn chat-header-action ui-button" data-action="chat:toggle-favorites" ${renderLabelAttributes(strings.toggleFavorites)}><span class="ui-icon chat-action-icon" aria-hidden="true"></span><span class="chat-action-label">${strings.toggleFavorites}</span></button></div>
        <div class="conversation-list-empty u-hidden" id="conversations-list-empty"></div>
        <div class="conversations-list" id="conversations-list"></div>
        ${toolbarHtml}
        </div>
        `;
};

export { buildChatContainerAndSidebarMarkup };
