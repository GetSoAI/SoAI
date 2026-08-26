/* SoAI - Assistant body cache synchronization from post-render DOM [frontend/assets/ts/features/chat/message/postrender/assistantBodyCacheSync.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import { canSerializeSettledAssistantBody, createSettledAssistantBodyHtml } from '@features/chat/message/assistantSettledDom.ts';
import { hasInlineMediaCards } from '@features/chat/message/enhancers/inlineMultimediaCardQueries.ts';

const resolveAssistantMessageRoot = (container: HTMLElement): HTMLElement | null => {
    if (container.classList.contains('chat-message')) {
        return container.classList.contains('assistant') ? container : null;
    }
    const root = container.closest('.chat-message.assistant');
    return root instanceof HTMLElement ? root : null;
};

const syncAssistantBodyCacheFromDom = (inputArguments: { container: HTMLElement; assistantMessage: ChatMessage | null; storePreRenderedAssistantBodyHtml: (message: ChatMessage, html: string) => void }): void => {
    if (!inputArguments.container.isConnected) {
        return;
    }
    const messageRoot = resolveAssistantMessageRoot(inputArguments.container);
    if (messageRoot === null) {
        return;
    }
    if (inputArguments.assistantMessage === null || !canSerializeSettledAssistantBody(messageRoot) || hasInlineMediaCards(messageRoot)) {
        return;
    }
    inputArguments.storePreRenderedAssistantBodyHtml(inputArguments.assistantMessage, createSettledAssistantBodyHtml(messageRoot));
};

export { syncAssistantBodyCacheFromDom };
