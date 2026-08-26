/* SoAI - Chat feature general identity markup [frontend/assets/ts/features/chat/modals/markup/chatconfigurationmodal/tabs/generalIdentityMarkup.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatPageMarkupContext } from '@features/chat/modals/markup/chatPageMarkupContext.ts';

const buildGeneralIdentityMarkup = (inputArguments: { strings: ChatPageMarkupContext['strings']; uiIdAttr: (token: string) => string }): string => {
    const { strings, uiIdAttr } = inputArguments;
    return `
  <div class="form-group setting-change-surface">
    <label for="${uiIdAttr('user-name-input')}">${strings.userName}</label>
    <input
      type="text"
      id="${uiIdAttr('user-name-input')}"
      class="user-display-name-input form-input"
      placeholder="${strings.userNamePlaceholder}"
      data-setting="identity.user_display_name"
    >
  </div>

  <div class="form-group setting-change-surface chat-config-span-2">
    <label for="${uiIdAttr('assistant-name-input')}">${strings.assistantName}</label>
    <input
      type="text"
      id="${uiIdAttr('assistant-name-input')}"
      class="assistant-display-name-input form-input"
      placeholder="${strings.assistantNamePlaceholder}"
      data-setting="identity.assistant_display_name"
    >
  </div>

  <div class="form-group setting-change-surface chat-config-span-2">
    <div class="chat-avatar-upload-grid">
      <div class="chat-avatar-upload-column">
        <div class="chat-config-field-header">
          <span class="form-label">${strings.userAvatarLabel}</span>
        </div>
        <div class="chat-avatar-upload-row">
          <div class="chat-avatar-preview user-avatar-preview message-avatar"></div>
          <button type="button" class="ui-button ui-button--sm" data-action="chat:upload-user-avatar" aria-label="${strings.userAvatarUpload}" data-tooltip="${strings.userAvatarUpload}">${strings.userAvatarUpload}</button>
          <button type="button" class="ui-button ui-button--sm ui-variant-danger user-avatar-remove-btn u-hidden" data-action="chat:remove-user-avatar" aria-label="${strings.userAvatarRemove}" data-tooltip="${strings.userAvatarRemove}">${strings.userAvatarRemove}</button>
        </div>
        <span class="chat-configuration-hint">${strings.userAvatarHint}</span>
      </div>

      <div class="chat-avatar-upload-column">
        <div class="chat-config-field-header">
          <span class="form-label">${strings.assistantAvatarLabel}</span>
        </div>
        <div class="chat-avatar-upload-row">
          <div class="chat-avatar-preview assistant-avatar-preview message-avatar"></div>
          <button type="button" class="ui-button ui-button--sm" data-action="chat:upload-assistant-avatar" aria-label="${strings.assistantAvatarUpload}" data-tooltip="${strings.assistantAvatarUpload}">${strings.assistantAvatarUpload}</button>
          <button type="button" class="ui-button ui-button--sm ui-variant-danger assistant-avatar-remove-btn u-hidden" data-action="chat:remove-assistant-avatar" aria-label="${strings.assistantAvatarRemove}" data-tooltip="${strings.assistantAvatarRemove}">${strings.assistantAvatarRemove}</button>
        </div>
        <span class="chat-configuration-hint">${strings.assistantAvatarHint}</span>
      </div>
    </div>
  </div>
`;
};

export { buildGeneralIdentityMarkup };
