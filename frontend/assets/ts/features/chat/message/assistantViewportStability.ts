/* SoAI - Chat feature assistant viewport stability [frontend/assets/ts/features/chat/message/assistantViewportStability.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { captureFirstVisibleMessageAnchor, restoreMessageScrollAnchor, type MessageWindowScrollAnchor } from '@features/chat/chatuimanager/messageWindowScrollAnchor.ts';
import { isMainTimelineAtBottom, isMainTimelineAutoScrollLocked } from '@features/chat/mainTimelineScroll.ts';

type AssistantViewportStability = {
    element: HTMLElement;
    messageAnchor: MessageWindowScrollAnchor | null;
    scrollTop: number;
    stickToBottom: boolean;
};

type AssistantViewportStabilityScope = 'transaction' | 'caller';

const resolveMessagesArea = (container: Element): HTMLElement | null => {
    let current: Element | null = container;
    while (current) {
        if (current instanceof HTMLElement && current.matches(CHAT_SELECTORS.MESSAGES_AREA)) {
            return current;
        }
        current = current.parentElement;
    }
    return null;
};

const captureAssistantViewportStability = (container: Element): AssistantViewportStability | null => {
    const element = resolveMessagesArea(container);
    if (!element) {
        return null;
    }
    return {
        element,
        messageAnchor: captureFirstVisibleMessageAnchor(element),
        scrollTop: element.scrollTop,
        stickToBottom: isMainTimelineAutoScrollLocked(element) && isMainTimelineAtBottom(element)
    };
};

const applyAssistantViewportStability = (state: AssistantViewportStability): void => {
    const maxScrollTop = Math.max(0, state.element.scrollHeight - state.element.clientHeight);
    if (state.stickToBottom) {
        if (state.element.scrollTop !== maxScrollTop) state.element.scrollTop = maxScrollTop;
        return;
    }
    if (restoreMessageScrollAnchor(state.element, state.messageAnchor)) return;
    const fallbackScrollTop = Math.min(state.scrollTop, maxScrollTop);
    if (state.element.scrollTop !== fallbackScrollTop) state.element.scrollTop = fallbackScrollTop;
};

const restoreAssistantViewportStability = (state: AssistantViewportStability | null): void => {
    if (!state || !state.element.isConnected) {
        return;
    }
    applyAssistantViewportStability(state);
};

const withCapturedAssistantViewportStability = (state: AssistantViewportStability | null, update: () => void): void => {
    const currentState = state !== null && state.element.scrollTop !== state.scrollTop ? captureAssistantViewportStability(state.element) : state;
    restoreAssistantViewportStability(currentState);
    try {
        update();
    } finally {
        restoreAssistantViewportStability(currentState);
    }
};

const withAssistantViewportStability = (container: Element, update: () => void): void => {
    const state = captureAssistantViewportStability(container);
    try {
        update();
    } finally {
        restoreAssistantViewportStability(state);
    }
};

export { captureAssistantViewportStability, restoreAssistantViewportStability, withAssistantViewportStability, withCapturedAssistantViewportStability };
export type { AssistantViewportStabilityScope };
