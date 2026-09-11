/* SoAI - Chat page input action buttons widget [frontend/assets/ts/pages/chat/controllers/page/markup/ChatInputActionButtonsWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderLabelAttributes, securityApi } from '@core/security/public.ts';
import { CHAT_ACTIONS, CHAT_CHARACTER_MAP_BUTTON_CLASS, type ChatPageMarkupContext } from '@features/chat/public.ts';

type ChatInputActionDescriptor = Readonly<{
    actionId: string;
    buttonClassName: string;
    label: string;
    stopLabel?: string;
}>;

const resolveChatInputActionDescriptors = (context: ChatPageMarkupContext): readonly ChatInputActionDescriptor[] => {
    const strings = context.strings;
    return [
        { actionId: CHAT_ACTIONS.NEW_CONVERSATION, buttonClassName: 'new-conversation-input-btn', label: strings.newConversation },
        { actionId: CHAT_ACTIONS.OPEN_CHARACTER_MAP, buttonClassName: CHAT_CHARACTER_MAP_BUTTON_CLASS, label: strings.openCharacterMap },
        { actionId: CHAT_ACTIONS.GOTO_PROMPTS, buttonClassName: 'goto-prompts-btn', label: strings.gotoPrompts },
        { actionId: CHAT_ACTIONS.TOGGLE_CALL, buttonClassName: 'call-btn', label: strings.voiceCallStart },
        { actionId: CHAT_ACTIONS.TOGGLE_RECORDING, buttonClassName: 'microphone-btn', label: strings.startRecording, stopLabel: strings.stopRecording },
        { actionId: CHAT_ACTIONS.OPEN_CAMERA, buttonClassName: 'camera-btn', label: strings.openCamera },
        { actionId: CHAT_ACTIONS.OPEN_ATTACH_MODAL, buttonClassName: 'attach-add-btn', label: strings.attachAdd }
    ];
};

const renderMicrophoneIconSlots = (): string => {
    return '<span class="ui-icon chat-action-icon chat-action-icon--microphone microphone-btn-icon--microphone" aria-hidden="true"></span><span class="ui-icon chat-action-icon chat-action-icon--stop microphone-btn-icon--stop" aria-hidden="true"></span>';
};

const renderActionIconSlots = (action: ChatInputActionDescriptor): string => {
    return action.stopLabel ? renderMicrophoneIconSlots() : '<span class="ui-icon chat-action-icon" aria-hidden="true"></span>';
};

const renderMicrophoneLabelDataAttributes = (action: ChatInputActionDescriptor): string => {
    if (!action.stopLabel) {
        return '';
    }
    return ` data-start-label="${securityApi.escapeAttribute(action.label)}" data-stop-label="${securityApi.escapeAttribute(action.stopLabel)}"`;
};

const renderMenuKeepOpenAttribute = (action: ChatInputActionDescriptor): string => {
    return action.actionId === CHAT_ACTIONS.TOGGLE_RECORDING ? ' data-page-actions-menu-keep-open="true"' : '';
};

const renderChatInputActionInlineButtonHtml = (action: ChatInputActionDescriptor): string => {
    return `<button type="button" class="${action.buttonClassName} ui-icon-button chat-input-action-inline" data-action="${action.actionId}"${renderMicrophoneLabelDataAttributes(action)} ${renderLabelAttributes(action.label)}>${renderActionIconSlots(action)}</button>`;
};

const renderChatInputActionMenuButtonHtml = (action: ChatInputActionDescriptor): string => {
    return `<button type="button" class="${action.buttonClassName} ui-button chat-input-action chat-header-action chat-composer-overflow-action" data-action="${action.actionId}"${renderMicrophoneLabelDataAttributes(action)}${renderMenuKeepOpenAttribute(action)} ${renderLabelAttributes(action.label)}>${renderActionIconSlots(action)}<span class="chat-input-action-label chat-action-label">${securityApi.escapeHtml(action.label)}</span></button>`;
};

const renderChatInputActionButtonsInline = (context: ChatPageMarkupContext): { leading: string; auxiliary: string } => {
    const strings = context.strings;
    const tokenCounterButton = `<button type="button" class="chat-token-counter-btn chat-token-counter-inline ui-icon-button u-hidden" data-action="chat:cycle-token-counter" ${renderLabelAttributes(strings.tokenCounterTooltip)} aria-pressed="false"><span class="chat-token-counter-label">${strings.tokenCounterInactive}</span></button>`;
    let leading = '';
    const auxiliary: string[] = [];
    for (const action of resolveChatInputActionDescriptors(context)) {
        const button = renderChatInputActionInlineButtonHtml(action);
        if (action.actionId === CHAT_ACTIONS.NEW_CONVERSATION) {
            leading = button;
        } else {
            auxiliary.push(button);
        }
    }
    auxiliary.push(tokenCounterButton);
    return { leading, auxiliary: auxiliary.join('') };
};

const renderChatHeaderOverflowComposerButtons = (context: ChatPageMarkupContext): string => {
    const strings = context.strings;
    const buttons = resolveChatInputActionDescriptors(context)
        .map((action) => renderChatInputActionMenuButtonHtml(action))
        .join('');
    const tokenCounterButton = `<button type="button" class="chat-token-counter-btn chat-token-counter-menu ui-button chat-input-action chat-header-action chat-composer-overflow-action" data-action="chat:cycle-token-counter" data-page-actions-menu-keep-open="true" ${renderLabelAttributes(strings.tokenCounterTooltip)} aria-pressed="false"><span class="chat-action-icon" aria-hidden="true"></span><span class="chat-token-counter-label chat-action-label">${strings.tokenCounterInactive}</span></button>`;
    return `${tokenCounterButton}${buttons}`;
};

export { renderChatInputActionButtonsInline, renderChatHeaderOverflowComposerButtons };
