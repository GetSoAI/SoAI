/* SoAI - Chat feature general preferences markup [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/generalPreferencesMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildToggleSwitchMarkup } from '@features/chat/modals/markup/chatconfigurationmodal/controls.ts';
import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

type ToggleLabels = Parameters<typeof buildToggleSwitchMarkup>[0]['labels'];

const buildGeneralPreferencesMarkup = (inputArguments: { modalId: string; strings: ChatPageMarkupContext['strings']; uiIdAttr: (token: string) => string; enabledDisabledLabels: ToggleLabels }): string => {
    const { modalId, strings, uiIdAttr, enabledDisabledLabels } = inputArguments;
    return `
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('conversation-pdf-export-toggle')}">${strings.exportToPdf}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'conversation-pdf-export-toggle',
        inputClassName: 'conversation-pdf-export-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'conversation_pdf_export_enabled'
    })}
    <span class="chat-configuration-hint">${strings.exportToPdfHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('inherit-last-settings-toggle')}">${strings.newConversationInheritLastSettings}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'inherit-last-settings-toggle',
        inputClassName: 'inherit-last-settings-toggle',
        checked: true,
        labels: enabledDisabledLabels,
        dataParameter: 'new_conversation_inherit_last_settings'
    })}
    <span class="chat-configuration-hint">${strings.newConversationInheritLastSettingsHint}</span>
  </div>

  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('ctrl-enter-send-toggle')}">${strings.ctrlEnterSend}</label>
    ${buildToggleSwitchMarkup({
        modalId,
        token: 'ctrl-enter-send-toggle',
        inputClassName: 'ctrl-enter-send-toggle',
        checked: false,
        labels: enabledDisabledLabels,
        dataParameter: 'ctrl_enter_send_enabled'
    })}
    <span class="chat-configuration-hint">${strings.ctrlEnterSendHint}</span>
  </div>
`;
};

export { buildGeneralPreferencesMarkup };
