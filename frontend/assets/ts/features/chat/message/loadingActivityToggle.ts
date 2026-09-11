/* SoAI - Chat feature loading activity toggle [frontend/assets/ts/features/chat/message/loadingActivityToggle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';
import { CHAT_SELECTORS } from '@features/chat/chatConstants.ts';
import type { ChatMessageActionsDependencies } from '@features/chat/message/actionDeps.ts';
import { patchRenderedAssistantMessageInConversation } from '@features/chat/message/assistantMessageDomPatch.ts';
import { resolveAssistantMessageParts } from '@features/chat/message/assistantMessageMarkupParts.ts';
import { animateMessageTextTransition, resolvePersistedContentMotionSnapshot } from '@features/chat/message/loadingActivityToggleMotion.ts';
import { beginLoadingActivityAnimations, beginLoadingActivityToggleSequence, cancelLoadingActivityTransition, clearLoadingActivityAnimations } from '@features/chat/message/loadingActivityToggleRegistry.ts';

type LoadingActivityToggleDependencies = {
    session: Pick<ChatMessageActionsDependencies['session'], 'getCurrentConversation'>;
    presentation: Pick<ChatMessageActionsDependencies['presentation'], 'resolveMessageReference' | 'resolveMessageContainer' | 'toggleLoadingActivityCollapsedState' | 'isShowActivitiesEnabled' | 'invalidateMessageCache' | 'invalidateActiveStreamDomCache' | 'assistantRenderPort' | 'postRender'>;
};

const toggleLoadingActivityItem = (dependencies: LoadingActivityToggleDependencies, messageId: string): void => {
    const conversation = dependencies.session.getCurrentConversation();
    const conversationId = normalizeConversationId(conversation?.id);
    if (conversation === null || conversationId === null) {
        return;
    }
    const { message } = dependencies.presentation.resolveMessageReference(conversation, messageId);
    if (message === null || message.role !== 'assistant') {
        return;
    }
    const messageContainer = dependencies.presentation.resolveMessageContainer(messageId);
    const messagesArea = messageContainer?.closest(CHAT_SELECTORS.MESSAGES_AREA);
    if (!(messageContainer instanceof HTMLElement) || !(messagesArea instanceof HTMLElement) || !messagesArea.isConnected) {
        return;
    }
    const messageTextNode = dom.resolve('.message-text', messageContainer);
    if (!(messageTextNode instanceof HTMLElement)) {
        return;
    }
    cancelLoadingActivityTransition(messageTextNode);
    const documentRef = messageTextNode.ownerDocument;
    const sequence = beginLoadingActivityToggleSequence(documentRef, messageId);
    beginLoadingActivityAnimations(documentRef, messageId, sequence);
    const persistedContent = resolvePersistedContentMotionSnapshot(messageTextNode);
    const startHeight = measureLayoutBox(messageTextNode).height;
    const nextCollapsed = dependencies.presentation.toggleLoadingActivityCollapsedState(message, !dependencies.presentation.isShowActivitiesEnabled());
    dependencies.presentation.invalidateMessageCache(message);
    let committed = false;
    try {
        const currentConversation = dependencies.session.getCurrentConversation();
        if (normalizeConversationId(currentConversation?.id) !== conversationId || currentConversation === null) {
            return;
        }
        const currentMessage = dependencies.presentation.resolveMessageReference(currentConversation, messageId).message;
        if (currentMessage === null || currentMessage.role !== 'assistant') {
            return;
        }
        dependencies.presentation.invalidateMessageCache(currentMessage);
        const result = patchRenderedAssistantMessageInConversation({ optionalUI: (selector, parent) => (parent ? dom.resolve(selector, parent) : messagesArea.matches(selector) ? messagesArea : dom.resolve(selector, messagesArea)), messageManager: dependencies.presentation.assistantRenderPort }, { conversation: currentConversation, conversationId, message: currentMessage, comparisonTurn: null, forceSettledAssistantActions: false, intent: 'activityToggle' });
        if (result === null) {
            return;
        }
        committed = true;
        dependencies.presentation.invalidateActiveStreamDomCache(conversationId, result.messageDomId);
        if (result.requiresPostRender) {
            dependencies.presentation.postRender(result.root);
        }
        const committedText = resolveAssistantMessageParts(result.root)?.text ?? null;
        if (committedText === messageTextNode) {
            animateMessageTextTransition(messageTextNode, documentRef, messageId, sequence, startHeight, nextCollapsed, persistedContent);
        } else {
            clearLoadingActivityAnimations(documentRef, messageId, sequence);
        }
    } finally {
        if (!committed) {
            dependencies.presentation.toggleLoadingActivityCollapsedState(message, nextCollapsed);
            dependencies.presentation.invalidateMessageCache(message);
            clearLoadingActivityAnimations(documentRef, messageId, sequence);
        }
    }
};

export { toggleLoadingActivityItem };
