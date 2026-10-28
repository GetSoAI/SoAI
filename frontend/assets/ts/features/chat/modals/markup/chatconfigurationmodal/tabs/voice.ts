/* SoAI - Chat feature voice [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/voice.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { modalUiId } from '@core/modals/uiIds.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderSpeechModelControl } from '@core/speechsetup/modelSelector.ts';
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
      <label for="${uiIdAttr('voice-tts-model-select')}" data-modal-localize="text">${strings.voiceTtsModel}</label>
      ${renderSpeechModelControl(
          `<select id="${uiIdAttr('voice-tts-model-select')}" class="form-input voice-tts-model-select" data-param="voice_tts_model" data-modal-localize="options">
        <option value="auto" data-modal-localize="text">${strings.voiceTtsModelAuto}</option>
      </select>`,
          'synthesis'
      )}
      <span class="chat-configuration-hint" data-modal-localize="text">${strings.voiceTtsModelHint}</span>
      <div class="speech-setup-note u-hidden" data-speech-setup="synthesis" role="status"></div>
    </div>
    <div class="form-group setting-change-surface">
      <label for="${uiIdAttr('voice-stt-model-select')}" data-modal-localize="text">${strings.voiceSttModel}</label>
      ${renderSpeechModelControl(
          `<select id="${uiIdAttr('voice-stt-model-select')}" class="form-input voice-stt-model-select" data-param="voice_stt_model" data-modal-localize="options">
        <option value="auto" data-modal-localize="text">${strings.voiceSttModelAuto}</option>
      </select>`,
          'voice'
      )}
      <span class="chat-configuration-hint" data-modal-localize="text">${strings.voiceSttModelHint}</span>
      <div class="speech-setup-note u-hidden" data-voice-speech-status data-speech-setup="voice" role="status"></div>
    </div>
  </div>
</div>
`;
};

export { buildVoiceTabMarkup };
