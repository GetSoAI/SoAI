/* SoAI - Chat message inline state preservation for DOM replacement [frontend/assets/ts/features/chat/message/chatMessageInlineStatePreservation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { collectAssistantDomState, restoreAssistantDomState, type AssistantDomStatePreservation } from '@features/chat/message/assistantDomState.ts';
import { restoreInlineMediaCardsFromPreservation } from '@features/chat/message/assistantInlineMediaCardPreservation.ts';
import { resolveHTMLElement } from '@core/dom/patching.ts';

type ChatMessageInlineStatePreservation = {
    state: AssistantDomStatePreservation;
};

const resolveChatMessageInlineStateRoot = (entryRoot: Element): HTMLElement | null => {
    if (!(entryRoot instanceof HTMLElement)) {
        return null;
    }
    if (!entryRoot.classList.contains('chat-message')) {
        return entryRoot;
    }
    return resolveHTMLElement(':scope > .message-content > .message-text', entryRoot) ?? entryRoot;
};

const preserveChatMessageInlineState = (entryRoot: Element): ChatMessageInlineStatePreservation | null => {
    const target = resolveChatMessageInlineStateRoot(entryRoot);
    if (target === null) {
        return null;
    }
    return { state: collectAssistantDomState(target) };
};

const restoreChatMessageInlineState = (entryRoot: Element, preserved: ChatMessageInlineStatePreservation | null): void => {
    if (preserved === null) {
        return;
    }
    const target = resolveChatMessageInlineStateRoot(entryRoot);
    if (target === null) {
        return;
    }
    restoreInlineMediaCardsFromPreservation(target, preserved.state.inlineMediaCards);
    restoreAssistantDomState(target, preserved.state);
};

export { preserveChatMessageInlineState, restoreChatMessageInlineState };
export type { ChatMessageInlineStatePreservation };
