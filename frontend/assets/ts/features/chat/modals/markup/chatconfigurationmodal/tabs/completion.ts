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
  <div class="chat-config-grid">
  ${renderChatParameterControlsMarkup({ modalId, strings })}

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('service-tier-select')}">${strings.serviceTier}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('service-tier-select')}" class="form-input" data-param="service_tier">
      <option value="">${strings.serviceTierUnset}</option>
      <option value="auto">${strings.serviceTierAuto}</option>
      <option value="default">${strings.serviceTierDefault}</option>
      <option value="flex">${strings.serviceTierFlex}</option>
      <option value="priority">${strings.serviceTierPriority}</option>
    </select>`)}
    <span class="chat-configuration-hint">${strings.serviceTierHint}</span>
  </div>

  ${modelSectionHeader(strings.modelSettingsTitle)}
</div>
</div>
`;
};

export { buildCompletionTabMarkup };
