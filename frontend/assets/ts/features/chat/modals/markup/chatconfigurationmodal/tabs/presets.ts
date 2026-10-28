/* SoAI - Chat configuration presets tab markup [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/presets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildPresetsTabMarkup = (context: ChatPageMarkupContext): string => {
    const { sanitizer } = context;
    const uiIdAttr = (token: string): string => uiAttr(modalUiId(CHAT_CONFIGURATION_MODAL_ID, token)).html;
    return `
<div id="${uiIdAttr('presets-content')}" class="tab-content chat-configuration-presets-content">
  <div class="chat-configuration-library chat-preset-library" data-chat-preset-state="loading" data-chat-library-loading="true">
    <div id="${uiIdAttr('preset-toolbar')}" class="chat-configuration-library-toolbar chat-preset-library-toolbar">
      <div class="searchbar-container searchbar-container--collection chat-preset-search-surface">
        <input id="${uiIdAttr('preset-search')}" class="searchbar-input" type="search" autocomplete="off" spellcheck="false" aria-label="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.searchLabel')}" placeholder="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.searchPlaceholder')}" / data-modal-localize="placeholder aria-label">
      </div>
      <div class="chat-configuration-actions">
        <button type="button" class="ui-button ui-variant-accent chat-preset-new-action" data-action="chat:new-preset" aria-label="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.newAction')}" data-tooltip="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.newAction')}" data-modal-localize="aria-label data-tooltip"><span data-modal-localize="text">${i18n.html(sanitizer, 'chat.configuration.presetLibrary.newAction')}</span></button>
      </div>
    </div>
    <div id="${uiIdAttr('preset-editor')}" class="chat-preset-editor glass-surface-full u-hidden"></div>
    <div id="${uiIdAttr('preset-list')}" class="ui-collection-grid chat-preset-list" role="list" aria-label="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.listLabel')}" data-modal-localize="aria-label"></div>
    <div id="${uiIdAttr('preset-empty')}" class="u-hidden"></div>
    <div id="${uiIdAttr('preset-status')}" class="ui-collection-notice glass-surface-medium u-hidden" role="status" aria-live="polite"></div>
    <div class="chat-configuration-library-utility glass-surface-medium">
      <div>
        <strong data-modal-localize="text">${i18n.html(sanitizer, 'chat.configuration.presetLibrary.restoreTitle')}</strong>
        <p data-modal-localize="text">${i18n.html(sanitizer, 'chat.configuration.presetLibrary.restoreHint')}</p>
      </div>
      <button type="button" class="ui-button ui-variant-danger" data-action="chat:restore-parameter-defaults" aria-label="${i18n.attr(sanitizer, 'settings.system.resetButtonLabel')}" data-tooltip="${i18n.attr(sanitizer, 'settings.system.resetButtonLabel')}" data-modal-localize="text aria-label data-tooltip">${i18n.html(sanitizer, 'settings.system.resetButtonLabel')}</button>
    </div>
  </div>
</div>
`;
};

export { buildPresetsTabMarkup };
