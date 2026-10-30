/* SoAI - Chat configuration appearance tab input action controls [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/appearanceInputActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getDefaultChatParameters } from '@core/chat/parameters/chatParameterDefaults.ts';
import { CHAT_PARAMETER_WIRE_KEYS } from '@core/chat/parameters/chatParameterKeySets.ts';
import type { ChatParameters } from '@core/chat/parameters/types.ts';
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
    parameter: Extract<keyof ChatParameters, string>;
}>;

const resolveInputActionToggleDescriptors = (strings: ChatPageMarkupContext['strings']): readonly InputActionToggleDescriptor[] => [
    { token: 'input-action-voice-toggle', label: strings.inputActionVoice, hint: strings.inputActionVoiceHint, parameter: 'inputActionVoiceEnabled' },
    { token: 'input-action-call-toggle', label: strings.inputActionCall, hint: strings.inputActionCallHint, parameter: 'inputActionCallEnabled' },
    { token: 'input-action-file-toggle', label: strings.inputActionUploadFile, hint: strings.inputActionUploadFileHint, parameter: 'inputActionFileUploadEnabled' },
    { token: 'input-action-camera-toggle', label: strings.inputActionCamera, hint: strings.inputActionCameraHint, parameter: 'inputActionCameraEnabled' },
    { token: 'input-action-find-toggle', label: strings.inputActionFind, hint: strings.inputActionFindHint, parameter: 'inputActionFindEnabled' },
    { token: 'input-action-sketch-toggle', label: strings.inputActionSketch, hint: strings.inputActionSketchHint, parameter: 'inputActionSketchEnabled' },
    { token: 'input-action-prompts-toggle', label: strings.inputActionPrompts, hint: strings.inputActionPromptsHint, parameter: 'inputActionPromptsEnabled' },
    { token: 'input-action-new-conversation-toggle', label: strings.newConversation, hint: strings.inputActionNewConversationHint, parameter: 'inputActionNewConversationEnabled' },
    { token: 'input-action-character-map-toggle', label: strings.inputActionCharacterMap, hint: strings.inputActionCharacterMapHint, parameter: 'inputActionCharacterMapEnabled' },
    { token: 'input-action-token-counter-toggle', label: strings.inputActionTokenCounter, hint: strings.inputActionTokenCounterHint, parameter: 'inputActionTokenCounterEnabled' }
];

const buildInputActionToggleMarkup = (modalId: string, uiIdAttr: (token: string) => string, labels: ToggleLabels, descriptor: InputActionToggleDescriptor, defaults: ChatParameters): string => {
    const hint = descriptor.hint === null ? '' : `\n    <span class="chat-configuration-hint" data-modal-localize="text">${descriptor.hint}</span>`;
    return `
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr(descriptor.token)}" data-modal-localize="text">${descriptor.label}</label>
    ${buildToggleSwitchMarkup({ modalId, token: descriptor.token, inputClassName: descriptor.token, checked: defaults[descriptor.parameter] === true, labels, dataParameter: CHAT_PARAMETER_WIRE_KEYS[descriptor.parameter] ?? descriptor.parameter })}${hint}
  </div>
`;
};

const buildAppearanceInputActionsMarkup = (inputArguments: { modalId: string; strings: ChatPageMarkupContext['strings']; sanitizer: SanitizerApi; uiIdAttr: (token: string) => string; enabledDisabledLabels: ToggleLabels }): string => {
    const { modalId, strings, sanitizer, uiIdAttr, enabledDisabledLabels } = inputArguments;
    const defaults = getDefaultChatParameters();
    const toggles = resolveInputActionToggleDescriptors(strings)
        .map((descriptor) => buildInputActionToggleMarkup(modalId, uiIdAttr, enabledDisabledLabels, descriptor, defaults))
        .join('');
    return `${toggles}
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('input-action-mobile-auxiliary-action-select')}" data-modal-localize="text">${strings.inputActionMobileAuxiliaryAction}</label>
    ${renderStandardDropdownSelectControl(`<select id="${uiIdAttr('input-action-mobile-auxiliary-action-select')}" class="form-input" data-param="${CHAT_PARAMETER_WIRE_KEYS['inputActionMobileAuxiliaryAction']}" data-modal-localize="options">
      ${renderChatMobileAuxiliaryActionSelectOptions(sanitizer)}
    </select>`)}
    <span class="chat-configuration-hint" data-modal-localize="text">${strings.inputActionMobileAuxiliaryActionHint}</span>
  </div>
`;
};

export { buildAppearanceInputActionsMarkup };
