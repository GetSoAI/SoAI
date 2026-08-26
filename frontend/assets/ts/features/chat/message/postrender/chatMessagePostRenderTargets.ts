/* SoAI - Chat message post-render target resolution [frontend/assets/ts/features/chat/message/postrender/chatMessagePostRenderTargets.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isCanonicalAssistantMessage } from '@features/chat/contentPreviewFeedbackState.ts';
import type { ChatMessage, ConversationContract } from '@features/chat/ChatTypes.ts';
import { createAssistantVariantReferenceIndex, resolveAssistantVariantReferenceFromIndex, type AssistantVariantReferenceIndex } from '@features/chat/message/messageReferenceResolution.ts';

interface ChatPostRenderTargetResolution {
    assistantMessageByTarget: WeakMap<HTMLElement, ChatMessage>;
    targets: HTMLElement[];
}

const collectChatPostRenderTargets = (container: HTMLElement): HTMLElement[] => {
    if (container.classList.contains('chat-message')) {
        return [container];
    }
    const messageRoots = dom.resolveAll('.chat-message', container).filter((node): node is HTMLElement => node instanceof HTMLElement);
    return messageRoots.length > 0 ? messageRoots : [container];
};

const resolveAssistantMessageRoot = (target: HTMLElement): HTMLElement | null => {
    const messageRoot = target.closest('.chat-message.assistant');
    return messageRoot instanceof HTMLElement ? messageRoot : null;
};

const resolveIndexedCanonicalAssistantMessage = (messageRoot: HTMLElement, index: AssistantVariantReferenceIndex): { handled: boolean; message: ChatMessage | null } => {
    const messageDomId = (messageRoot.getAttribute('data-id') ?? '').trim();
    if (!messageDomId) {
        return { handled: true, message: null };
    }
    const resolved = resolveAssistantVariantReferenceFromIndex(index, messageDomId);
    if (!resolved.matchedIdentifier) {
        return { handled: false, message: null };
    }
    return {
        handled: true,
        message: isCanonicalAssistantMessage(resolved.message) ? resolved.message : null
    };
};

const resolveChatPostRenderTargets = (inputArguments: { container: HTMLElement; conversation: ConversationContract | null; resolveMessageForDomId: (conversation: ConversationContract, messageDomId: string) => ChatMessage | null }): ChatPostRenderTargetResolution => {
    const targets = collectChatPostRenderTargets(inputArguments.container);
    const assistantMessageByTarget = new WeakMap<HTMLElement, ChatMessage>();
    const index = targets.length > 1 && inputArguments.conversation !== null ? createAssistantVariantReferenceIndex(inputArguments.conversation) : null;
    for (const target of targets) {
        const messageRoot = resolveAssistantMessageRoot(target);
        if (messageRoot === null || inputArguments.conversation === null) {
            continue;
        }
        if (index !== null) {
            const indexed = resolveIndexedCanonicalAssistantMessage(messageRoot, index);
            if (indexed.handled) {
                if (indexed.message !== null) {
                    assistantMessageByTarget.set(target, indexed.message);
                }
                continue;
            }
        }
        const messageDomId = (messageRoot.getAttribute('data-id') ?? '').trim();
        if (!messageDomId) {
            continue;
        }
        const message = inputArguments.resolveMessageForDomId(inputArguments.conversation, messageDomId);
        if (isCanonicalAssistantMessage(message)) {
            assistantMessageByTarget.set(target, message);
        }
    }
    return { assistantMessageByTarget, targets };
};

export { resolveChatPostRenderTargets };
