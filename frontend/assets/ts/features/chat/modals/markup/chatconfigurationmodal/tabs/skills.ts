/* SoAI - Chat configuration skills tab markup [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/skills.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildSkillsTabMarkup = (context: ChatPageMarkupContext): string => {
    const { sanitizer } = context;
    return `
<div id="${uiAttr(modalUiId(CHAT_CONFIGURATION_MODAL_ID, 'skills-content')).html}" class="tab-content" data-chat-library-loading="true">
  <div class="chat-configuration-library chat-skills-library">
    <div data-skills-controls class="chat-configuration-library-toolbar chat-skills-controls"></div>
    <div data-skills-list class="ui-collection-grid chat-skills-list" role="list" aria-label="${i18n.attr(sanitizer, 'chat.configuration.skills.title')}" data-modal-localize="aria-label"></div>
    <div data-skills-empty class="u-hidden"></div>
    <div data-skills-details class="chat-skills-details glass-surface-medium u-hidden"></div>
    <div data-skills-status class="ui-collection-notice glass-surface-medium u-hidden" role="status" aria-live="polite"></div>
    <div class="chat-configuration-library-utility glass-surface-medium">
      <div>
        <strong data-modal-localize="text">${i18n.html(sanitizer, 'chat.configuration.skills.aboutTitle')}</strong>
        <p data-modal-localize="text">${i18n.html(sanitizer, 'chat.configuration.skills.description')} ${i18n.html(sanitizer, 'chat.configuration.skills.immediate')}</p>
      </div>
    </div>
  </div>
</div>`;
};

export { buildSkillsTabMarkup };
