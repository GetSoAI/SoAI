/* SoAI - Chat feature mobile auxiliary action catalog [frontend/assets/ts/features/chat/inputactions/mobileAuxiliaryActionCatalog.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_MOBILE_AUXILIARY_ACTIONS, CHAT_MOBILE_AUXILIARY_ACTION_NONE, normalizeChatMobileAuxiliaryAction, type ChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import { i18n } from '@core/i18n/index.ts';
import type { SanitizerApi } from '@core/pagecontext/public.ts';
import { renderLabelAttributes, securityApi, toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { EMPTY_UI_HTML } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { CHAT_ACTIONS, type ChatActionId } from '@features/chat/chatActionIds.ts';
import { CHAT_CHARACTER_MAP_BUTTON_CLASS, CHAT_ICON_SIZE_MD, CHAT_ICON_SIZE_SM } from '@features/chat/chatConstants.ts';

type ChatMobileAuxiliaryActionIconSlotType = 'none' | 'standard' | 'microphone' | 'agent_mode' | 'token_counter';

type ChatMobileAuxiliaryActionDescriptor = Readonly<{
    id: ChatMobileAuxiliaryAction;
    buttonClassNames: string;
    actionId: ChatActionId | null;
    iconName: IconName | null;
    iconSlotType: ChatMobileAuxiliaryActionIconSlotType;
}>;

const CHAT_MOBILE_AUXILIARY_ACTION_DESCRIPTORS: ReadonlyArray<ChatMobileAuxiliaryActionDescriptor> = Object.freeze([
    { id: 'none', buttonClassNames: '', actionId: null, iconName: null, iconSlotType: 'none' },
    { id: 'agent_mode', buttonClassNames: 'agent-mode-cycle-btn', actionId: CHAT_ACTIONS.CYCLE_AGENT_MODE, iconName: 'chat', iconSlotType: 'agent_mode' },
    { id: 'agent_compact', buttonClassNames: 'agent-compact-btn hidden', actionId: CHAT_ACTIONS.COMPACT_AGENT, iconName: 'agent-compact', iconSlotType: 'standard' },
    { id: 'export', buttonClassNames: 'export-btn hidden', actionId: CHAT_ACTIONS.EXPORT_CONVERSATION, iconName: 'download', iconSlotType: 'standard' },
    { id: 'configuration', buttonClassNames: 'configuration-toggle-btn', actionId: CHAT_ACTIONS.TOGGLE_CONFIGURATION, iconName: 'model-config', iconSlotType: 'standard' },
    { id: 'favorite', buttonClassNames: 'header-favorite-btn', actionId: CHAT_ACTIONS.TOGGLE_CURRENT_CONVERSATION_FAVORITE, iconName: 'star', iconSlotType: 'standard' },
    { id: 'tools', buttonClassNames: 'tools-toggle-btn', actionId: CHAT_ACTIONS.TOGGLE_TOOLS, iconName: 'tools-toggle', iconSlotType: 'standard' },
    { id: 'token_counter', buttonClassNames: 'chat-token-counter-btn chat-token-counter-auxiliary', actionId: CHAT_ACTIONS.CYCLE_TOKEN_COUNTER, iconName: 'info', iconSlotType: 'token_counter' },
    { id: 'voice', buttonClassNames: 'microphone-btn', actionId: CHAT_ACTIONS.TOGGLE_RECORDING, iconName: 'microphone', iconSlotType: 'microphone' },
    { id: 'voice_call', buttonClassNames: 'call-btn', actionId: CHAT_ACTIONS.TOGGLE_CALL, iconName: 'call', iconSlotType: 'standard' },
    { id: 'camera', buttonClassNames: 'camera-btn', actionId: CHAT_ACTIONS.OPEN_CAMERA, iconName: 'camera', iconSlotType: 'standard' },
    { id: 'attach', buttonClassNames: 'attach-add-btn', actionId: CHAT_ACTIONS.OPEN_ATTACH_MODAL, iconName: 'paperclip', iconSlotType: 'standard' },
    { id: 'character_map', buttonClassNames: CHAT_CHARACTER_MAP_BUTTON_CLASS, actionId: CHAT_ACTIONS.OPEN_CHARACTER_MAP, iconName: 'file-font', iconSlotType: 'standard' },
    { id: 'prompts', buttonClassNames: 'goto-prompts-btn', actionId: CHAT_ACTIONS.GOTO_PROMPTS, iconName: 'prompt', iconSlotType: 'standard' }
]);

const resolveChatMobileAuxiliaryActionDescriptor = (action: ChatMobileAuxiliaryAction): ChatMobileAuxiliaryActionDescriptor => {
    const normalized = normalizeChatMobileAuxiliaryAction(action);
    for (const candidate of CHAT_MOBILE_AUXILIARY_ACTION_DESCRIPTORS) {
        if (candidate.id === normalized) {
            return candidate;
        }
    }
    throw new Error(`Missing chat mobile auxiliary action descriptor for ${normalized}`);
};

const renderOptionLabel = (sanitizer: SanitizerApi, descriptor: ChatMobileAuxiliaryActionDescriptor): string => {
    switch (descriptor.id) {
        case 'none':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.none');
        case 'agent_mode':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.agentMode');
        case 'agent_compact':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.agentCompact');
        case 'export':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.export');
        case 'configuration':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.configuration');
        case 'favorite':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.favorite');
        case 'tools':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.tools');
        case 'token_counter':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.tokenCounter');
        case 'voice':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.voice');
        case 'voice_call':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.voiceCall');
        case 'camera':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.camera');
        case 'attach':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.attach');
        case 'character_map':
            return i18n.html(sanitizer, 'chat.characterMap.mobileOption');
        case 'prompts':
            return i18n.html(sanitizer, 'chat.configuration.inputActions.auxiliary.options.prompts');
    }
};

const resolveButtonLabel = (descriptor: ChatMobileAuxiliaryActionDescriptor): string => {
    switch (descriptor.id) {
        case 'none':
            return i18n.t('chat.configuration.inputActions.auxiliary.options.none');
        case 'agent_mode':
            return i18n.t('chat.agent.mode.cycleTooltip');
        case 'agent_compact':
            return i18n.t('chat.agent.compact.tooltip');
        case 'export':
            return i18n.t('chat.header.export');
        case 'configuration':
            return i18n.t('chat.header.configuration');
        case 'favorite':
            return i18n.t('chat.header.toggleFavorite');
        case 'tools':
            return i18n.t('chat.header.toggleTools');
        case 'token_counter':
            return i18n.t('chat.tokenCounter.tooltip');
        case 'voice':
            return i18n.t('chat.input.startRecording');
        case 'voice_call':
            return i18n.t('chat.input.voiceCallStart');
        case 'camera':
            return i18n.t('chat.input.openCamera');
        case 'attach':
            return i18n.t('chat.input.attachAdd');
        case 'character_map':
            return i18n.t('chat.characterMap.open');
        case 'prompts':
            return i18n.t('chat.header.gotoPrompts');
    }
};

const renderChatMobileAuxiliaryActionSelectOptions = (sanitizer: SanitizerApi): string => {
    return CHAT_MOBILE_AUXILIARY_ACTIONS.map((action) => {
        const actionDescriptor = resolveChatMobileAuxiliaryActionDescriptor(action);
        return `<option value="${securityApi.escapeAttribute(actionDescriptor.id)}">${renderOptionLabel(sanitizer, actionDescriptor)}</option>`;
    }).join('');
};

const renderActionDataAttribute = (actionId: ChatActionId | null): string => {
    return actionId === null ? '' : ` data-action="${securityApi.escapeAttribute(actionId)}"`;
};

const renderStandardIconSlot = (iconMarkup: TrustedHtml): string => {
    return `<span class="ui-icon chat-action-icon" aria-hidden="true">${iconMarkup.html}</span><span class="chat-action-label"></span>`;
};

const renderMicrophoneIconSlots = (microphoneIcon: TrustedHtml, stopIcon: TrustedHtml): string => {
    return `<span class="ui-icon chat-action-icon chat-action-icon--microphone microphone-btn-icon--microphone" aria-hidden="true">${microphoneIcon.html}</span><span class="ui-icon chat-action-icon chat-action-icon--stop microphone-btn-icon--stop" aria-hidden="true">${stopIcon.html}</span>`;
};

const renderChatMobileAuxiliaryActionButton = (inputArguments: { descriptor: ChatMobileAuxiliaryActionDescriptor; getIcon: (iconName: IconName, size: typeof CHAT_ICON_SIZE_MD) => TrustedHtml }): TrustedHtml => {
    const actionDescriptor = inputArguments.descriptor;
    if (actionDescriptor.id === CHAT_MOBILE_AUXILIARY_ACTION_NONE) {
        return EMPTY_UI_HTML;
    }
    const label = resolveButtonLabel(actionDescriptor);
    const actionDataAttribute = renderActionDataAttribute(actionDescriptor.actionId);
    const buttonClassNames = securityApi.escapeAttribute(actionDescriptor.buttonClassNames);
    const actionId = securityApi.escapeAttribute(actionDescriptor.id);
    if (actionDescriptor.iconSlotType === 'microphone') {
        const microphoneIcon = inputArguments.getIcon('microphone', CHAT_ICON_SIZE_MD);
        const stopIcon = inputArguments.getIcon('stop', CHAT_ICON_SIZE_MD);
        return toTrustedUiHtml(`<button type="button" class="chat-mobile-auxiliary-action ui-icon-button ${buttonClassNames}" data-mobile-auxiliary-action="${actionId}"${actionDataAttribute} data-start-label="${securityApi.escapeAttribute(i18n.t('chat.input.startRecording'))}" data-stop-label="${securityApi.escapeAttribute(i18n.t('chat.input.stopRecording'))}" ${renderLabelAttributes(label)}>${renderMicrophoneIconSlots(microphoneIcon, stopIcon)}</button>`);
    }
    if (actionDescriptor.iconSlotType === 'agent_mode') {
        const iconMarkup = inputArguments.getIcon('chat', CHAT_ICON_SIZE_SM);
        return toTrustedUiHtml(`<button type="button" class="chat-mobile-auxiliary-action ui-icon-button ${buttonClassNames}" data-mobile-auxiliary-action="${actionId}" data-agent-mode="chat"${actionDataAttribute} ${renderLabelAttributes(label)}><span class="agent-mode-cycle-icon ui-icon" aria-hidden="true">${iconMarkup.html}</span><span class="agent-mode-cycle-label">${securityApi.escapeHtml(i18n.t('chat.agent.mode.chat'))}</span></button>`);
    }
    if (actionDescriptor.iconSlotType === 'token_counter') {
        return toTrustedUiHtml(`<button type="button" class="chat-mobile-auxiliary-action ui-icon-button ${buttonClassNames}" data-mobile-auxiliary-action="${actionId}"${actionDataAttribute} ${renderLabelAttributes(label)} aria-pressed="false"><span class="chat-token-counter-label">${securityApi.escapeHtml(i18n.t('chat.tokenCounter.inactive'))}</span></button>`);
    }
    if (actionDescriptor.iconName === null) {
        throw new Error(`Chat mobile auxiliary action ${actionDescriptor.id} requires an icon`);
    }
    const iconMarkup = inputArguments.getIcon(actionDescriptor.iconName, CHAT_ICON_SIZE_MD);
    return toTrustedUiHtml(`<button type="button" class="chat-mobile-auxiliary-action ui-icon-button ${buttonClassNames}" data-mobile-auxiliary-action="${actionId}"${actionDataAttribute} ${renderLabelAttributes(label)} aria-pressed="false">${renderStandardIconSlot(iconMarkup)}</button>`);
};

export { CHAT_MOBILE_AUXILIARY_ACTION_DESCRIPTORS, renderChatMobileAuxiliaryActionButton, renderChatMobileAuxiliaryActionSelectOptions, resolveChatMobileAuxiliaryActionDescriptor };
export type { ChatMobileAuxiliaryActionDescriptor };
