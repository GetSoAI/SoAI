/* SoAI - Chat feature memory [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/memory.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';

import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildMemoryTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, sectionHeader } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('memory-content')}" class="tab-content">
  <div class="chat-config-grid">
    <div class="form-group setting-change-surface chat-config-span-2">
      <label>${strings.memoryUserMemoriesTitle}</label>
    </div>
    <div class="chat-memory-panel chat-config-span-2">
      <div class="chat-configuration-hint">${strings.memoryDescription}</div>
      <div class="chat-configuration-actions">
        <button type="button" class="ui-button" data-action="chat:open-memory-profile" aria-label="${strings.memoryOpenProfile}" data-tooltip="${strings.memoryOpenProfile}">${strings.memoryOpenProfile}</button>
        <button type="button" class="ui-button" data-action="chat:refresh-memory" aria-label="${strings.memoryRefresh}" data-tooltip="${strings.memoryRefresh}">${strings.memoryRefresh}</button>
      </div>
      <div id="${uiIdAttr('memory-viewer')}" class="chat-memory-viewer"></div>
      <div id="${uiIdAttr('memory-empty')}" class="chat-configuration-hint u-hidden">${strings.memoryEmpty}</div>
    </div>
    ${sectionHeader(strings.memoryTitle)}
  </div>
</div>
`;
};

export { buildMemoryTabMarkup };
