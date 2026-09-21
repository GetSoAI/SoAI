/* SoAI - Chat page input [frontend/assets/ts/pages/chat/controllers/page/dom/input.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isInstanceOf } from '@core/typeGuards.ts';
import { normalizeChatMobileAuxiliaryAction } from '@core/chat/parameters/mobileAuxiliaryAction.ts';
import type { Conversation } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import { applyChatInputActionVisibility } from '@pages/chat/controllers/chatUiVisibility.ts';
import type { VisionSupportHost } from '@pages/chat/controllers/page/guards/modelVisionSupportController.ts';
import type { ChatConversationDomHost, ChatIconResolver, ChatPageDomHost, ChatParameters } from '@pages/chat/controllers/page/dom/contracts.ts';
import { syncCameraInputActionSupport } from '@pages/chat/controllers/page/dom/cameraController.ts';
import { syncChatInputActionSupport } from '@pages/chat/controllers/page/dom/inputActionSupportController.ts';
import { renderMobileAuxiliaryAction } from '@pages/chat/controllers/page/dom/mobileAuxiliaryActionController.ts';

interface ChatInputUiStateHost {
    resizeChatInput(textarea: Element): void;
    updateInputState(): void;
    updateEmptyStateInputHint(): void;
}

interface ChatInputMutationHost extends ChatInputUiStateHost {
    setUIValue(target: Element, value: string, options?: { attribute?: string }): void;
}

interface ChatExportButtonHost extends PageDomOwnerHost {
    currentConversation(): Conversation | null;
    isConversationExecuting(conversationId: string): boolean;
}
type ChatInputActionHost = ChatConversationDomHost;

const applyInputActionVisibility = (host: ChatInputActionHost & VisionSupportHost, parameters: ChatParameters, getIcon: ChatIconResolver): void => {
    const auxiliaryAction = normalizeChatMobileAuxiliaryAction(parameters.inputActionMobileAuxiliaryAction);
    renderMobileAuxiliaryAction(host, parameters, getIcon);
    applyChatInputActionVisibility(
        {
            pageDom: host.pageDom
        },
        {
            voiceEnabled: parameters.inputActionVoiceEnabled === true,
            callEnabled: parameters.inputActionCallEnabled === true,
            fileUploadEnabled: parameters.inputActionFileUploadEnabled === true,
            cameraEnabled: parameters.inputActionCameraEnabled === true,
            promptsEnabled: parameters.inputActionPromptsEnabled === true,
            newConversationEnabled: parameters.inputActionNewConversationEnabled === true,
            characterMapEnabled: parameters.inputActionCharacterMapEnabled === true,
            tokenCounterEnabled: parameters.inputActionTokenCounterEnabled === true && auxiliaryAction !== 'token_counter',
            tokenCounterAuxiliaryEnabled: auxiliaryAction === 'token_counter'
        }
    );
    syncCameraInputActionSupport(host);
    syncChatInputActionSupport(host);
};

const refreshChatInputUiState = (host: ChatInputUiStateHost, input: HTMLTextAreaElement): void => {
    host.resizeChatInput(input);
    host.updateInputState();
    host.updateEmptyStateInputHint();
};

const insertTranscription = (host: ChatInputMutationHost, input: HTMLTextAreaElement | null, text: string, noteDraftChanged: (value: string) => void): void => {
    if (!input) {
        return;
    }
    const currentValue = input.value;
    const separator = currentValue.length > 0 && !currentValue.endsWith(' ') ? ' ' : '';
    const newValue = currentValue + separator + text;
    host.setUIValue(input, newValue, { attribute: 'value' });
    input.focus();
    refreshChatInputUiState(host, input);
    noteDraftChanged(newValue);
};

const resizeChatInput = (host: ChatPageDomHost, textarea: Element): void => {
    if (!isInstanceOf(textarea, HTMLTextAreaElement)) {
        throw new TypeError('Chat input requires a textarea element');
    }
    const maxHeight = 120;
    host.dom.setStyle(textarea, 'height', '');
    if (textarea.value.length === 0) {
        host.dom.setStyle(textarea, 'overflowY', 'hidden');
        return;
    }
    const scrollHeight = textarea.scrollHeight;
    const borderBlockSize = Math.max(textarea.offsetHeight - textarea.clientHeight, 0);
    const requiredHeight = scrollHeight + borderBlockSize;
    const needsExpansion = scrollHeight > textarea.clientHeight;
    if (needsExpansion) {
        host.dom.setStyle(textarea, 'height', `${Math.min(requiredHeight, maxHeight)}px`);
    }
    host.dom.setStyle(textarea, 'overflowY', requiredHeight > maxHeight ? 'auto' : 'hidden');
};

const updateExportButtonVisibility = (host: ChatExportButtonHost): void => {
    const conversation = host.currentConversation();
    const messageCount = conversation?.history?.totalCount ?? conversation?.messageCount ?? conversation?.messages.length ?? 0;
    const hasMessages = messageCount > 0;
    const isRunning = conversation?.id ? host.isConversationExecuting(conversation.id) : false;
    for (const candidate of host.pageDom.query('.export-btn')) {
        if (!(candidate instanceof HTMLButtonElement)) {
            continue;
        }
        host.pageDom.toggleClass(candidate, 'u-hidden', !hasMessages);
        candidate.toggleAttribute('disabled', !hasMessages || isRunning);
    }
};

export { applyInputActionVisibility, insertTranscription, refreshChatInputUiState, resizeChatInput, updateExportButtonVisibility };
export type { ChatInputUiStateHost };
