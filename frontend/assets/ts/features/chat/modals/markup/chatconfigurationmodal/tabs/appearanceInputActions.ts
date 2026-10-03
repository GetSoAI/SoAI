/* SoAI - Chat configuration appearance tab input action controls [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/appearanceInputActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { renderStandardDropdownSelectControl } from '@core/ui/dropdown/selectControl.ts';
import { renderChatMobileAuxiliaryActionSelectOptions } from '@features/chat/inputactions/mobileAuxiliaryActionCatalog.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';
import { buildToggleSwitchMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';

type ToggleLabels = Parameters<typeof buildToggleSwitchMarkup>[0]['labels'];

type InputActionToggleDescriptor = Readonly<{
    token: string;
    label: string;
    hint: string | null;
    checked: boolean;
    dataParameter: string;
}>;

const resolveInputActionToggleDescriptors = (strings: ChatPageMarkupContext['strings']): readonly InputActionToggleDescriptor[] => [
    { token: 'input-action-voice-toggle', label: strings.inputActionVoice, hint: strings.inputActionVoiceHint, checked: true, dataParameter: 'input_action_voice_enabled' },
    { token: 'input-action-call-toggle', label: strings.inputActionCall, hint: strings.inputActionCallHint, checked: true, dataParameter: 'input_action_call_enabled' },
    { token: 'input-action-file-toggle', label: strings.inputActionUploadFile, hint: strings.inputActionUploadFileHint, checked: true, dataParameter: 'input_action_file_upload_enabled' },
    { token: 'input-action-camera-toggle', label: strings.inputActionCamera, hint: strings.inputActionCameraHint, checked: false, dataParameter: 'input_action_camera_enabled' },
    { token: 'input-action-sketch-toggle', label: strings.inputActionSketch, hint: strings.inputActionSketchHint, checked: false, dataParameter: 'input_action_sketch_enabled' },
    { token: 'input-action-prompts-toggle', label: strings.inputActionPrompts, hint: strings.inputActionPromptsHint, checked: false, dataParameter: 'input_action_prompts_enabled' },
    { token: 'input-action-new-conversation-toggle', label: strings.newConversation, hint: null, checked: true, dataParameter: 'input_action_new_conversation_enabled' },
    { token: 'input-action-character-map-toggle', label: strings.inputActionCharacterMap, hint: strings.inputActionCharacterMapHint, checked: false, dataParameter: 'input_action_character_map_enabled' },
    { token: 'input-action-token-counter-toggle', label: strings.inputActionTokenCounter, hint: strings.inputActionTokenCounterHint, checked: false, dataParameter: 'input_action_token_counter_enabled' }
];

const buildInputActionToggleMarkup = (modalId: string, uiIdAttr: (token: string) => string, labels: ToggleLabels, descriptor: InputActionToggleDescriptor): string => {
    const hint = descriptor.hint === null ? '' : `\n    <span class="chat-configuration-hint">${descriptor.hint}</span>`;
    return `
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr(descriptor.token)}">${descriptor.label}</label>
    ${buildToggleSwitchMarkup({ modalId, token: descriptor.token, inputClassName: descriptor.token, checked: descriptor.checked, labels, dataParameter: descriptor.dataParameter })}${hint}
  </div>
`;
};

const buildAppearanceInputActionsMarkup = (inputArguments: { modalId: string; strings: ChatPageMarkupContext['strings']; sanitizer: SanitizerApi; uiIdAttr: (token: string) => string; enabledDisabledLabels: ToggleLabels }): string => {
    const { modalId, strings, sanitizer, uiIdAttr, enabledDisabledLabels } = inputArguments;
    const toggles = resolveInputActionToggleDescriptors(strings)
        .map((descriptor) => buildInputActionToggleMarkup(modalId, uiIdAttr, enabledDisabledLabels, descriptor))
        .join('');
    return `${toggles}
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-mobile-auxiliary-action-select')}">${strings.inputActionMobileAuxiliaryAction}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('input-action-mobile-auxiliary-action-select')}" class="form-input" data-param="input_action_mobile_auxiliary_action">
      ${renderChatMobileAuxiliaryActionSelectOptions(sanitizer)}
    </select>`)}
    <span class="chat-configuration-hint">${strings.inputActionMobileAuxiliaryActionHint}</span>
  </div>
`;
};

export { buildAppearanceInputActionsMarkup };
