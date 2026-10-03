/* SoAI - Chat page UI visibility [frontend/assets/ts/pages/chat/controllers/chatUiVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR } from '@pages/chat/controllers/page/dom/mobileAuxiliaryActionController.ts';
import { bindEventGroup } from '@core/dom/eventBindingGroup.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type ChatInputActionVisibilityHost = PageDomOwnerHost;

interface ChatInputActionVisibilityState {
    voiceEnabled: boolean;
    callEnabled: boolean;
    fileUploadEnabled: boolean;
    cameraEnabled: boolean;
    promptsEnabled: boolean;
    tokenCounterEnabled: boolean;
    tokenCounterAuxiliaryEnabled: boolean;
    newConversationEnabled: boolean;
    characterMapEnabled: boolean;
    sketchEnabled: boolean;
}

const setInputActionHidden = (host: ChatInputActionVisibilityHost, element: Element, hidden: boolean): void => {
    host.pageDom.toggleClass(element, 'u-hidden', hidden);
    const slot = element.parentElement;
    if (slot?.matches(CHAT_MOBILE_AUXILIARY_ACTION_SLOT_SELECTOR)) {
        host.pageDom.toggleClass(slot, 'u-hidden', hidden);
    }
};

export const applyChatInputActionVisibility = (host: ChatInputActionVisibilityHost, state: ChatInputActionVisibilityState): void => {
    host.pageDom.query(CHAT_SELECTORS.MICROPHONE_BTN).forEach((element) => setInputActionHidden(host, element, !state.voiceEnabled));

    host.pageDom.query(CHAT_SELECTORS.CALL_BTN).forEach((element) => setInputActionHidden(host, element, !state.callEnabled));

    host.pageDom.query(CHAT_SELECTORS.ATTACH_BTN).forEach((element) => setInputActionHidden(host, element, !state.fileUploadEnabled));

    host.pageDom.query(CHAT_SELECTORS.CAMERA_BTN).forEach((element) => setInputActionHidden(host, element, !state.cameraEnabled));

    host.pageDom.query(CHAT_SELECTORS.PROMPTS_BTN).forEach((element) => setInputActionHidden(host, element, !state.promptsEnabled));

    host.pageDom.query('.new-conversation-input-btn').forEach((element) => setInputActionHidden(host, element, !state.newConversationEnabled));

    host.pageDom.query(CHAT_SELECTORS.CHARACTER_MAP_BTN).forEach((element) => setInputActionHidden(host, element, !state.characterMapEnabled));

    host.pageDom.query(CHAT_SELECTORS.SKETCH_BTN).forEach((element) => setInputActionHidden(host, element, !state.sketchEnabled));

    host.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN).forEach((element) => {
        const isAuxiliary = element.classList.contains('chat-token-counter-auxiliary');
        setInputActionHidden(host, element, isAuxiliary ? !state.tokenCounterAuxiliaryEnabled : !state.tokenCounterEnabled);
    });
};

interface ChatEmptyStateNavTarget {
    initializeOverflowNav(container: Element, addEventListener: (target: EventTarget, type: string, listener: EventListener, options?: AddEventListenerOptions) => () => void): void;
}

export const initializeChatEmptyStateNav = (manager: ChatEmptyStateNavTarget, container: Element, signal: AbortSignal): void => {
    const addEventListener = (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions): (() => void) => {
        return bindEventGroup([{ target, type: event, listener: handler, options }], signal);
    };

    manager.initializeOverflowNav(container, addEventListener);
};

type ChatEmptyStateInputHintHost = PageDomOwnerHost;

export const updateChatEmptyStateInputHint = (host: ChatEmptyStateInputHintHost, { hasTextInput, hasAttachments }: { hasTextInput: boolean; hasAttachments: boolean }): void => {
    const emptyState = host.pageDom.optionalHTMLElement('.chat-page-empty-state');
    if (!emptyState) return;
    emptyState.classList.toggle('has-input', hasTextInput || hasAttachments);
};
