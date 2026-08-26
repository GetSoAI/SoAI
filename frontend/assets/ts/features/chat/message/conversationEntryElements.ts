/* SoAI - Conversation transcript entry DOM selection [frontend/assets/ts/features/chat/message/conversationEntryElements.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const CHAT_MESSAGE_CLASS = 'chat-message';
const CHAT_COMPARISON_TURN_CLASS = 'chat-comparison-turn';

const resolveConversationEntryElements = (container: Element): HTMLElement[] => {
    return Array.from(container.children).filter((child): child is HTMLElement => {
        if (!(child instanceof HTMLElement)) return false;
        return child.classList.contains(CHAT_MESSAGE_CLASS) || child.classList.contains(CHAT_COMPARISON_TURN_CLASS);
    });
};

export { resolveConversationEntryElements };
