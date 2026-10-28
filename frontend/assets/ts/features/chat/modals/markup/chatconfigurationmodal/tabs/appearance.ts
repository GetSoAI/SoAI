/* SoAI - Chat feature appearance [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/appearance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_TEXT_ZOOM_DEFAULT, CHAT_TEXT_ZOOM_MAX, CHAT_TEXT_ZOOM_MIN, CHAT_TEXT_ZOOM_STEP } from '@core/chat/parameters/textZoom.ts';
import { modalUiId } from '@core/modals/uiIds.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { uiAttr } from '@core/security/uiHtml.ts';
import { CHAT_CONFIGURATION_MODAL_ID } from '@features/chat/modals/constants.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildToggleSwitchMarkup, resolveEnabledDisabledToggleLabels } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';
import { buildAppearanceInputActionsMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/tabs/appearanceInputActions.ts';

type ToggleLabels = Parameters<typeof buildToggleSwitchMarkup>[0]['labels'];

const buildAppearanceControlsMarkup = (inputArguments: { modalId: string; strings: ChatPageMarkupContext['strings']; sanitizer: SanitizerApi; uiIdAttr: (token: string) => string; enabledDisabledLabels: ToggleLabels; textZoomValueId: string; textZoomValueIdAttr: string }): string => {
    const { modalId, strings, sanitizer, uiIdAttr, enabledDisabledLabels, textZoomValueId, textZoomValueIdAttr } = inputArguments;
    return `
  <div class="form-group setting-change-surface chat-config-span-2">
    <label for="${uiIdAttr('text-zoom-slider')}" data-modal-localize="text">
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
    <label for="${uiIdAttr('widescreen-checkbox')}" data-modal-localize="text">${strings.widescreenMode}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'widescreen-checkbox',
        inputClassName: 'widescreen-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'widescreen_mode'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.widescreenModeHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('auto-hide-chat-composer-checkbox')}" data-modal-localize="text">${strings.autoHideChatComposer}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'auto-hide-chat-composer-checkbox',
        inputClassName: 'auto-hide-chat-composer-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'auto_hide_chat_composer'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.autoHideChatComposerHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('auto-hide-chat-header-checkbox')}" data-modal-localize="text">${strings.autoHideChatHeader}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'auto-hide-chat-header-checkbox',
        inputClassName: 'auto-hide-chat-header-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'auto_hide_chat_header'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.autoHideChatHeaderHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('rich-text-checkbox')}" data-modal-localize="text">${strings.richTextMode}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'rich-text-checkbox',
        inputClassName: 'rich-text-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'rich_text_enabled'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.richTextModeHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('inline-multimedia-previews-checkbox')}" data-modal-localize="text">${strings.inlineMultimediaPreviews}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'inline-multimedia-previews-checkbox',
        inputClassName: 'inline-multimedia-previews-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'inline_multimedia_previews_enabled'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.inlineMultimediaPreviewsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('auto-title-generation-checkbox')}" data-modal-localize="text">${strings.autoTitleGeneration}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'auto-title-generation-checkbox',
        inputClassName: 'auto-title-generation-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'auto_title_generation'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.autoTitleGenerationHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('show-activities-checkbox')}" data-modal-localize="text">${strings.showActivities}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'show-activities-checkbox',
        inputClassName: 'show-activities-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'show_activities'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.showActivitiesHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('show-activity-elapsed-time-checkbox')}" data-modal-localize="text">${strings.showActivityElapsedTime}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'show-activity-elapsed-time-checkbox',
        inputClassName: 'show-activity-elapsed-time-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'show_activity_elapsed_time'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.showActivityElapsedTimeHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('hide-automation-runs-checkbox')}" data-modal-localize="text">${strings.hideAutomationRuns}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'hide-automation-runs-checkbox',
        inputClassName: 'hide-automation-runs-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'hide_automation_runs'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.hideAutomationRunsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('hide-messaging-conversations-checkbox')}" data-modal-localize="text">${strings.hideMessagingConversations}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'hide-messaging-conversations-checkbox',
        inputClassName: 'hide-messaging-conversations-checkbox',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'hide_messaging_conversations'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.hideMessagingConversationsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('notify-completion-checkbox')}" data-modal-localize="text">${strings.notifyOnCompletion}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'notify-completion-checkbox',
        inputClassName: 'notify-completion-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'notify_on_completion'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.notifyOnCompletionHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('notify-error-checkbox')}" data-modal-localize="text">${strings.notifyOnError}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'notify-error-checkbox',
        inputClassName: 'notify-error-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'notify_on_error'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.notifyOnErrorHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('microphone-sound-effects-checkbox')}" data-modal-localize="text">${strings.microphoneSoundEffects}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'microphone-sound-effects-checkbox',
        inputClassName: 'microphone-sound-effects-checkbox',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'microphone_sound_effects_enabled'
    })}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.microphoneSoundEffectsHint}</span>
  </div>

${buildAppearanceInputActionsMarkup({ modalId, strings, sanitizer, uiIdAttr, enabledDisabledLabels })}
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
