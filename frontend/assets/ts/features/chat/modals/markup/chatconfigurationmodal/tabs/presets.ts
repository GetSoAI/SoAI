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
  <div class="chat-preset-library" data-chat-preset-state="loading">
    <div id="${uiIdAttr('preset-toolbar')}" class="chat-preset-library-toolbar">
      <div class="searchbar-container searchbar-container--collection chat-preset-search-surface">
        <label class="visually-hidden" for="${uiIdAttr('preset-search')}">${i18n.html(sanitizer, 'chat.configuration.presetLibrary.searchLabel')}</label>
        <input id="${uiIdAttr('preset-search')}" class="searchbar-input" type="search" autocomplete="off" spellcheck="false" placeholder="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.searchPlaceholder')}" />
        <span id="${uiIdAttr('preset-search-icon')}" class="searchbar-icon" aria-hidden="true"></span>
      </div>
      <div class="chat-configuration-actions">
        <button type="button" class="ui-button ui-variant-accent chat-preset-new-action" data-action="chat:new-preset" aria-label="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.newAction')}" data-tooltip="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.newAction')}"><span id="${uiIdAttr('preset-add-icon')}" class="ui-icon" aria-hidden="true"></span><span>${i18n.html(sanitizer, 'chat.configuration.presetLibrary.newAction')}</span></button>
      </div>
    </div>
    <div id="${uiIdAttr('preset-status')}" class="chat-preset-status chat-preset-status--loading glass-surface-medium" role="status" aria-live="polite"><span class="loading-spinner chat-preset-status-spinner" aria-hidden="true"></span><span>${i18n.html(sanitizer, 'common.loading')}</span></div>
    <div id="${uiIdAttr('preset-editor')}" class="chat-preset-editor glass-surface-full u-hidden"></div>
    <div id="${uiIdAttr('preset-list')}" class="ui-collection-grid chat-preset-list" role="list" aria-label="${i18n.attr(sanitizer, 'chat.configuration.presetLibrary.listLabel')}"></div>
    <div class="chat-preset-library-utility glass-surface-medium">
      <div>
        <strong>${i18n.html(sanitizer, 'chat.configuration.presetLibrary.restoreTitle')}</strong>
        <p>${i18n.html(sanitizer, 'chat.configuration.presetLibrary.restoreHint')}</p>
      </div>
      <button type="button" class="ui-button ui-variant-danger" data-action="chat:restore-parameter-defaults" aria-label="${i18n.attr(sanitizer, 'settings.system.resetButtonLabel')}" data-tooltip="${i18n.attr(sanitizer, 'settings.system.resetButtonLabel')}">${i18n.html(sanitizer, 'settings.system.resetButtonLabel')}</button>
    </div>
  </div>
</div>
`;
};

export { buildPresetsTabMarkup };
