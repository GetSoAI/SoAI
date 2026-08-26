/* SoAI - Chat feature configuration general tab [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/chatConfigurationGeneralTab.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildToggleSwitchMarkup, resolveEnabledDisabledToggleLabels } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';
import { buildGeneralIdentityMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/generalIdentityMarkup.ts';
import { buildGeneralPreferencesMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/generalPreferencesMarkup.ts';
import { i18n } from '@core/i18n/index.ts';

const buildGeneralTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiIdAttr = (token: string): string => uiAttr(modalUiId(modalId, token)).html;
    const enabledDisabledLabels = resolveEnabledDisabledToggleLabels();

    return `
<div id="${uiIdAttr('general-content')}" class="tab-content is-active chat-config-general-tab">
  <div class="chat-config-grid">
    <div class="form-group setting-change-surface">
      <div class="chat-config-field-header">
        <span id="${uiIdAttr('configuration-model-label')}" class="form-label">${i18n.html(context.sanitizer, 'chat.configuration.configurationModel.label')}</span>
        <div class="chat-config-field-hide-model">
          <label for="${uiIdAttr('hide-real-model-checkbox')}">${strings.hideRealModel}</label>
          ${buildToggleSwitchMarkup({
              modalId,
              token: 'hide-real-model-checkbox',
              inputClassName: 'hide-real-model-checkbox',
              checked: false,
              labels: enabledDisabledLabels,
              inline: true,
              dataParameter: 'hide_real_model'
          })}
        </div>
      </div>
      <div class="model-selector page-header-filter-select" data-chat-model-control="true" data-scope="configuration" aria-labelledby="${uiIdAttr('configuration-model-label')}"></div>
      <span class="chat-configuration-hint">${strings.hideRealModelHint}</span>
    </div>
${buildGeneralIdentityMarkup({ strings, uiIdAttr })}
${buildGeneralPreferencesMarkup({ modalId, strings, uiIdAttr, enabledDisabledLabels })}
</div>
</div>
`;
};

export { buildGeneralTabMarkup };
