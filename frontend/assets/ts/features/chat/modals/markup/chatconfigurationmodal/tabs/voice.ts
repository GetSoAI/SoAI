/* SoAI - Chat feature voice [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/voice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildVoiceTabMarkup = (context: ChatPageMarkupContext): string => {
    const { strings } = context;
    const modalId = CHAT_CONFIGURATION_MODAL_ID;

    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;

    return `
<div id="${uiIdAttr('voice-content')}" class="tab-content">
  <div class="chat-config-grid">
    <div class="form-group setting-change-surface">
      <label for="${uiIdAttr('voice-tts-model-select')}">${strings.voiceTtsModel}</label>
      ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('voice-tts-model-select')}" class="form-input voice-tts-model-select" data-param="voice_tts_model">
        <option value="auto">${strings.voiceTtsModelAuto}</option>
      </select>`)}
      <span class="chat-configuration-hint">${strings.voiceTtsModelHint}</span>
    </div>
    <div class="form-group setting-change-surface">
      <label for="${uiIdAttr('voice-stt-model-select')}">${strings.voiceSttModel}</label>
      ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('voice-stt-model-select')}" class="form-input voice-stt-model-select" data-param="voice_stt_model">
        <option value="auto">${strings.voiceSttModelAuto}</option>
      </select>`)}
      <span class="chat-configuration-hint">${strings.voiceSttModelHint}</span>
    </div>
  </div>
</div>
`;
};

export { buildVoiceTabMarkup };
