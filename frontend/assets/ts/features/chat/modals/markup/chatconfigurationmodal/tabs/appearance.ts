/* SoAI - Chat feature appearance [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/appearance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_TEXT_ZOOM_DEFAULT, CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN, CHAT_TEXT_ZOOM_STEP } from '@core/chat/parameters/textZoom.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderChatMobileAuxiliaryActionSelectOptions } from '@features/chat/inputactions/mobileAuxiliaryActionCatalog.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildToggleSwitchMarkup, resolveEnabledDisabledToggleLabels } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';

type ToggleLabels = Parameters<typeof buildToggleSwitchMarkup>[0]['labels'];

const buildAppearanceControlsMarkup = (inputArguments: { modalId: string; strings: ChatPageMarkupContext['strings']; sanitizer: SanitizerApi; uiIdAttr: (token: string) => string; enabledDisabledLabels: ToggleLabels; textZoomValueId: string; textZoomValueIdAttr: string }): string => {
    const { modalId, strings, sanitizer, uiIdAttr, enabledDisabledLabels, textZoomValueId, textZoomValueIdAttr } = inputArguments;
    return `
  <div class="form-group setting-change-surface chat-config-span-2">
    <label for="${uiIdAttr('text-zoom-slider')}">
      ${strings.textZoom}
      <span id="${textZoomValueIdAttr}" class="text-zoom-value">100%</span>
    </label>
    <input
      type="range"
      id="${uiIdAttr('text-zoom-slider')}"
      class="text-zoom-slider ui-range"
      min="${String(CHAT_TEXT_ZOOM_MIN)}"
      max="${String(CHAT_TEXT_ZOOM_MAX)}"
      step="${String(CHAT_TEXT_ZOOM_STEP)}"
      value="${String(CHAT_TEXT_ZOOM_DEFAULT)}"
      data-param="text_zoom"
      data-display="#${textZoomValueId}"
    >
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('widescreen-checkbox')}">${strings.widescreenMode}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'widescreen-checkbox',
        inputClassName: 'widescreen-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'widescreen_mode'
    })}
    <span class="chat-configuration-hint">${strings.widescreenModeHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rich-text-checkbox')}">${strings.richTextMode}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'rich-text-checkbox',
        inputClassName: 'rich-text-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'rich_text_enabled'
    })}
    <span class="chat-configuration-hint">${strings.richTextModeHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('inline-multimedia-previews-checkbox')}">${strings.inlineMultimediaPreviews}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'inline-multimedia-previews-checkbox',
        inputClassName: 'inline-multimedia-previews-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'inline_multimedia_previews_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inlineMultimediaPreviewsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('auto-title-generation-checkbox')}">${strings.autoTitleGeneration}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'auto-title-generation-checkbox',
        inputClassName: 'auto-title-generation-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'auto_title_generation'
    })}
    <span class="chat-configuration-hint">${strings.autoTitleGenerationHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('show-activities-checkbox')}">${strings.showActivities}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'show-activities-checkbox',
        inputClassName: 'show-activities-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'show_activities'
    })}
    <span class="chat-configuration-hint">${strings.showActivitiesHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('hide-automation-runs-checkbox')}">${strings.hideAutomationRuns}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'hide-automation-runs-checkbox',
        inputClassName: 'hide-automation-runs-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'hide_automation_runs'
    })}
    <span class="chat-configuration-hint">${strings.hideAutomationRunsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('hide-messaging-conversations-checkbox')}">${strings.hideMessagingConversations}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'hide-messaging-conversations-checkbox',
        inputClassName: 'hide-messaging-conversations-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'hide_messaging_conversations'
    })}
    <span class="chat-configuration-hint">${strings.hideMessagingConversationsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('notify-completion-checkbox')}">${strings.notifyOnCompletion}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'notify-completion-checkbox',
        inputClassName: 'notify-completion-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'notify_on_completion'
    })}
    <span class="chat-configuration-hint">${strings.notifyOnCompletionHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('notify-error-checkbox')}">${strings.notifyOnError}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'notify-error-checkbox',
        inputClassName: 'notify-error-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'notify_on_error'
    })}
    <span class="chat-configuration-hint">${strings.notifyOnErrorHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('microphone-sound-effects-checkbox')}">${strings.microphoneSoundEffects}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'microphone-sound-effects-checkbox',
        inputClassName: 'microphone-sound-effects-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'microphone_sound_effects_enabled'
    })}
    <span class="chat-configuration-hint">${strings.microphoneSoundEffectsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-voice-toggle')}">${strings.inputActionVoice}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-voice-toggle',
        inputClassName: 'input-action-voice-toggle',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_voice_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionVoiceHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-call-toggle')}">${strings.inputActionCall}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-call-toggle',
        inputClassName: 'input-action-call-toggle',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_call_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionCallHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-file-toggle')}">${strings.inputActionUploadFile}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-file-toggle',
        inputClassName: 'input-action-file-toggle',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_file_upload_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionUploadFileHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-camera-toggle')}">${strings.inputActionCamera}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-camera-toggle',
        inputClassName: 'input-action-camera-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_camera_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionCameraHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-prompts-toggle')}">${strings.inputActionPrompts}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-prompts-toggle',
        inputClassName: 'input-action-prompts-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_prompts_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionPromptsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-new-conversation-toggle')}">${strings.newConversation}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-new-conversation-toggle',
        inputClassName: 'input-action-new-conversation-toggle',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_new_conversation_enabled'
    })}
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-character-map-toggle')}">${strings.inputActionCharacterMap}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-character-map-toggle',
        inputClassName: 'input-action-character-map-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_character_map_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionCharacterMapHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-token-counter-toggle')}">${strings.inputActionTokenCounter}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'input-action-token-counter-toggle',
        inputClassName: 'input-action-token-counter-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'input_action_token_counter_enabled'
    })}
    <span class="chat-configuration-hint">${strings.inputActionTokenCounterHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-mobile-auxiliary-action-select')}">${strings.inputActionMobileAuxiliaryAction}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('input-action-mobile-auxiliary-action-select')}" class="form-input" data-param="input_action_mobile_auxiliary_action">
      ${renderChatMobileAuxiliaryActionSelectOptions(sanitizer)}
    </select>`)}
    <span class="chat-configuration-hint">${strings.inputActionMobileAuxiliaryActionHint}</span>
  </div>
`;
};

const buildAppearanceTabMarkup = (context: ChatPageMarkupContext): string => {
    const modalId = CHAT_CONFIGURATION_MODAL_ID;
    const uiId = (token: string): string => modalUiId(modalId, token);
    const uiIdAttr = (token: string): string => uiAttr(uiId(token)).html;
    const textZoomValueId = uiId('text-zoom-value');

    return `
<div id="${uiIdAttr('appearance-content')}" class="tab-content chat-config-appearance-tab">
  <div class="chat-config-grid">
${buildAppearanceControlsMarkup({
    modalId,
    strings: context.strings,
    sanitizer: context.sanitizer,
    uiIdAttr,
    enabledDisabledLabels: resolveEnabledDisabledToggleLabels(),
    textZoomValueId,
    textZoomValueIdAttr: uiAttr(textZoomValueId).html
})}
</div>
</div>
`;
};

export { buildAppearanceTabMarkup };
