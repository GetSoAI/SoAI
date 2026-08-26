/* SoAI - Message window scroll anchor capture and restoration [frontend/assets/ts/features/chat/chatuimanager/messageWindowScrollAnchor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { optionalNonNegativeIntegerAttribute } from '@core/dom/attributes.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import { resolveConversationEntryElements } from '@features/chat/message/conversationEntryElements.ts';

interface MessageWindowScrollAnchor {
    assistantTurnTimestamp: number | null;
    messageId: string;
    offsetTopWithinMessage: number;
}

const resolveConversationEntryContainer = (messagesArea: HTMLElement): HTMLElement => {
    const messagesContainer = dom.resolve(CHAT_SELECTORS.MESSAGES_CONTAINER, messagesArea);
    return messagesContainer instanceof HTMLElement ? messagesContainer : messagesArea;
};

const resolveMessageAnchorElement = (messagesArea: HTMLElement, anchor: MessageWindowScrollAnchor): HTMLElement | null => {
    const entries = resolveConversationEntryElements(resolveConversationEntryContainer(messagesArea));
    for (const element of entries) {
        if (element.getAttribute('data-id') === anchor.messageId) return element;
    }
    if (anchor.assistantTurnTimestamp === null) return null;
    for (const element of entries) {
        if (optionalNonNegativeIntegerAttribute(element, 'data-assistant-turn-ts', 'Message window scroll anchor') === anchor.assistantTurnTimestamp) return element;
    }
    return null;
};

const captureFirstVisibleMessageAnchor = (messagesArea: HTMLElement): MessageWindowScrollAnchor | null => {
    const areaRect = measureLayoutBox(messagesArea);
    for (const element of resolveConversationEntryElements(resolveConversationEntryContainer(messagesArea))) {
        const messageId = element.getAttribute('data-id');
        if (messageId === null || !messageId.trim()) continue;
        const rect = measureLayoutBox(element);
        if (rect.bottom < areaRect.top) continue;
        return {
            assistantTurnTimestamp: optionalNonNegativeIntegerAttribute(element, 'data-assistant-turn-ts', 'Message window scroll anchor'),
            messageId,
            offsetTopWithinMessage: areaRect.top - rect.top
        };
    }
    return null;
};

const resolveMessageScrollAnchorScrollTop = (messagesArea: HTMLElement, anchor: MessageWindowScrollAnchor | null): number | null => {
    if (anchor === null) return null;
    const target = resolveMessageAnchorElement(messagesArea, anchor);
    if (target === null) return null;
    const areaRect = measureLayoutBox(messagesArea);
    const targetRect = measureLayoutBox(target);
    const targetScrollTop = messagesArea.scrollTop + targetRect.top - areaRect.top + anchor.offsetTopWithinMessage;
    return targetScrollTop;
};

const restoreMessageScrollAnchor = (messagesArea: HTMLElement, anchor: MessageWindowScrollAnchor | null): boolean => {
    const targetScrollTop = resolveMessageScrollAnchorScrollTop(messagesArea, anchor);
    if (targetScrollTop === null) return false;
    if (targetScrollTop !== messagesArea.scrollTop) messagesArea.scrollTop = targetScrollTop;
    return true;
};

export { captureFirstVisibleMessageAnchor, resolveMessageScrollAnchorScrollTop, restoreMessageScrollAnchor };
export type { MessageWindowScrollAnchor };
