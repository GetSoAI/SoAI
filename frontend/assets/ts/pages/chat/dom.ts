/* SoAI - Chat page DOM contracts [frontend/assets/ts/pages/chat/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isHTMLElement } from '@core/typeGuards.ts';
import { CHAT_SELECTORS } from '@features/chat/public.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type ChatPageDomHost = PageDomOwnerHost & {
    getDomContext: () => Element | Document | null;
    requireHTMLElement: (selector: string | Element, context?: Element) => HTMLElement;
    optionalHTMLElement: (selector: string | Element, context?: Element) => HTMLElement | null;
};

type ChatPageUi = {
    root: HTMLElement;
    messagesContainer: HTMLElement;
    conversationsList: HTMLElement;
    input: HTMLTextAreaElement | null;
};

const CHAT_MESSAGE_CLASS = 'chat-message';
const MESSAGE_WINDOW_LOADING_LABEL_CLASS = 'chat-message-window-loading-label';

export const optionalChatRoot = (host: Pick<ChatPageDomHost, 'getDomContext'>): HTMLElement | null => {
    const root = host.getDomContext();
    return isHTMLElement(root) ? root : null;
};

export const requireChatRoot = (host: Pick<ChatPageDomHost, 'getDomContext'>): HTMLElement => {
    const root = host.getDomContext();
    if (!isHTMLElement(root)) {
        throw new Error('ChatPage requires a host container');
    }
    return root;
};

const requireMessagesContainer = (host: ChatPageDomHost): HTMLElement => {
    return host.pageDom.requireHTMLElement(CHAT_SELECTORS.MESSAGES_CONTAINER);
};

const requireConversationsList = (host: ChatPageDomHost): HTMLElement => {
    return host.pageDom.requireHTMLElement(CHAT_SELECTORS.CONVERSATIONS_LIST);
};

const optionalInput = (host: ChatPageDomHost): HTMLTextAreaElement | null => {
    const candidate = host.pageDom.optionalHTMLElement(CHAT_SELECTORS.INPUT);
    return candidate instanceof HTMLTextAreaElement ? candidate : null;
};

export const requireChatUi = (host: ChatPageDomHost): ChatPageUi => {
    const root = requireChatRoot(host);
    return {
        root,
        messagesContainer: requireMessagesContainer(host),
        conversationsList: requireConversationsList(host),
        input: optionalInput(host)
    };
};

export const resolveChatMessageElements = (container: Element): HTMLElement[] => {
    return Array.from(container.children).filter((child): child is HTMLElement => {
        return child instanceof HTMLElement && child.classList.contains(CHAT_MESSAGE_CLASS) && child.hasAttribute('data-id');
    });
};

export const requireMessageWindowLoadingLabel = (element: HTMLElement): HTMLElement => {
    const label = Array.from(element.children).find((child): child is HTMLElement => {
        return child instanceof HTMLElement && child.classList.contains(MESSAGE_WINDOW_LOADING_LABEL_CLASS);
    });
    if (label === undefined) {
        throw new Error('Message window loading element is missing its label');
    }
    return label;
};

export type { ChatPageDomHost, ChatPageUi };
