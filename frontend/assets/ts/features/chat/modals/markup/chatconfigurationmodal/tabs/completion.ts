/* SoAI - Chat feature completion [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/completion.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderChatParameterControlsMarkup } from '@core/chat/parameters/parameterControlsMarkup.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildCompletionTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings, modelSectionHeader } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('completion-content')}" class="tab-content chat-config-completion-tab">
  <div class="chat-config-grid" data-modal-localize="text">
  ${renderChatParameterControlsMarkup({ modalId, strings, includeContextWindowPresets: true })}

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('service-tier-select')}" data-modal-localize="text">${strings.serviceTier}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('service-tier-select')}" class="form-input" data-param="service_tier" data-modal-localize="options">
      <option value="" data-modal-localize="text">${strings.serviceTierUnset}</option>
      <option value="auto" data-modal-localize="text">${strings.serviceTierAuto}</option>
      <option value="default" data-modal-localize="text">${strings.serviceTierDefault}</option>
      <option value="flex" data-modal-localize="text">${strings.serviceTierFlex}</option>
      <option value="priority" data-modal-localize="text">${strings.serviceTierPriority}</option>
    </select>`)}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.serviceTierHint}</span>
  </div>

  ${modelSectionHeader(strings.modelSettingsTitle)}
</div>
</div>
`;
};

export { buildCompletionTabMarkup };
