/* SoAI - Chat page UI visibility [frontend/assets/ts/pages/chat/controllers/chatUiVisibility.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

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
    characterMapEnabled: boolean;
}

export const applyChatInputActionVisibility = (host: ChatInputActionVisibilityHost, state: ChatInputActionVisibilityState): void => {
    host.pageDom.query(CHAT_SELECTORS.MICROPHONE_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.voiceEnabled));

    host.pageDom.query(CHAT_SELECTORS.CALL_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.callEnabled));

    host.pageDom.query(CHAT_SELECTORS.ATTACH_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.fileUploadEnabled));

    host.pageDom.query(CHAT_SELECTORS.CAMERA_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.cameraEnabled));

    host.pageDom.query(CHAT_SELECTORS.PROMPTS_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.promptsEnabled));

    host.pageDom.query(CHAT_SELECTORS.CHARACTER_MAP_BTN).forEach((element) => host.pageDom.toggleClass(element, 'u-hidden', !state.characterMapEnabled));

    host.pageDom.query(CHAT_SELECTORS.TOKEN_COUNTER_BTN).forEach((element) => {
        const isAuxiliary = element.classList.contains('chat-token-counter-auxiliary');
        host.pageDom.toggleClass(element, 'u-hidden', isAuxiliary ? !state.tokenCounterAuxiliaryEnabled : !state.tokenCounterEnabled);
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

type ChatHeaderModelSelectorHost = PageDomOwnerHost;

export const updateChatHeaderModelSelectorVisibility = (
    host: ChatHeaderModelSelectorHost,
    {
        modelCount,
        sidebarOpen,
        detached
    }: {
        modelCount: number;
        sidebarOpen: boolean;
        detached: boolean;
    }
): void => {
    const container = host.pageDom.optionalHTMLElement('.chat-header-model-selector');
    if (!container) return;
    const show = modelCount > 0 && (!sidebarOpen || detached);
    host.pageDom.toggleClass(container, 'is-visible', show);
    host.pageDom.updateAttribute(container, 'hidden', show ? null : 'true');
    host.pageDom.updateAttribute(container, 'aria-hidden', show ? 'false' : 'true');
};

type ChatEmptyStateInputHintHost = PageDomOwnerHost;

export const updateChatEmptyStateInputHint = (host: ChatEmptyStateInputHintHost, { hasTextInput, hasAttachments }: { hasTextInput: boolean; hasAttachments: boolean }): void => {
    const emptyState = host.pageDom.optionalHTMLElement('.chat-page-empty-state');
    if (!emptyState) return;
    emptyState.classList.toggle('has-input', hasTextInput || hasAttachments);
};
