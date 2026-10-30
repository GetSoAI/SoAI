/* SoAI - Chat feature memory [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/memory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';

import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildMemoryTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, sanitizer } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('memory-content')}" class="tab-content" data-chat-memory-state="loading" data-chat-library-loading="true">
  <div class="chat-configuration-library chat-memory-library">
    <div class="chat-configuration-library-toolbar">
      <div class="searchbar-container searchbar-container--collection">
        <input id="${uiIdAttr('memory-search')}" class="searchbar-input" type="search" autocomplete="off" spellcheck="false" aria-label="${i18n.attr(sanitizer, 'chat.memory.library.search')}" placeholder="${i18n.attr(sanitizer, 'chat.memory.library.search')}" / data-modal-localize="placeholder aria-label">
      </div>
      <div class="chat-configuration-actions">
        <button type="button" class="ui-button ui-variant-accent" data-action="chat:add-memory" aria-label="${i18n.attr(sanitizer, 'chat.memory.library.add')}" data-tooltip="${i18n.attr(sanitizer, 'chat.memory.library.add')}" data-modal-localize="text aria-label data-tooltip">${i18n.html(sanitizer, 'chat.memory.library.add')}</button>
      </div>
    </div>
    <div id="${uiIdAttr('memory-viewer')}" class="ui-collection-grid chat-memory-list" role="list" aria-label="${i18n.attr(sanitizer, 'chat.configuration.memory.userMemoriesTitle')}" data-modal-localize="aria-label"></div>
    <div id="${uiIdAttr('memory-empty')}" class="u-hidden"></div>
    <div id="${uiIdAttr('memory-status')}" class="ui-collection-notice glass-surface-medium u-hidden" role="status" aria-live="polite"></div>
    <div class="chat-configuration-library-utility glass-surface-medium">
      <div>
        <strong data-modal-localize="text">${i18n.html(sanitizer, 'chat.memory.profile.title')}</strong>
        <p data-modal-localize="text">${i18n.html(sanitizer, 'chat.memory.profile.description')}</p>
      </div>
      <button type="button" class="ui-button" data-action="chat:open-memory-profile" aria-label="${strings.memoryOpenProfile}" data-tooltip="${strings.memoryOpenProfile}" data-modal-localize="text aria-label data-tooltip">${strings.memoryOpenProfile}</button>
    </div>
  </div>
</div>
`;
};

export { buildMemoryTabMarkup };
