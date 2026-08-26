/* SoAI - Chat page current conversation [frontend/assets/ts/pages/chat/controllers/page/renderer/currentConversation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { resolveMaxCssAnimationTotalMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { analyzeConversationProjection, CHAT_SELECTORS, resolveRenderableConversationEntries, type ActiveComparisonRun } from '@features/chat/public.ts';
import type { ChatConversationRenderOutcome } from '@pages/chat/controllers/chatpage/conversations/contracts.ts';
import type { ChatCurrentConversationRenderDependencies } from '@pages/chat/controllers/page/renderer/contracts.ts';
import { renderCurrentConversationMessageState } from '@pages/chat/controllers/page/renderer/currentConversationMessageController.ts';
import { clearStaleCurrentConversationStatusNodes, finalizeCurrentConversationUi, renderCurrentConversationStatusState, resolveCurrentConversationKey } from '@pages/chat/controllers/page/renderer/currentConversationStateController.ts';
import { resolveSelectedConversationViewState } from '@pages/chat/controllers/page/renderer/selectedConversationState.ts';

const LOADING_CONVERSATION_STATUS_SELECTOR = '.chat-page-empty-state[data-state="loading"]';
const CONVERSATION_ENTER_CLASS = 'chat-conversation-enter';
const CONVERSATION_ENTER_ANIMATION_CLEANUP_BUFFER_MS = 50;

const hasLoadingConversationStatus = (container: Element): boolean => {
    const firstElement = container.firstElementChild;
    return firstElement instanceof HTMLElement && firstElement.matches(LOADING_CONVERSATION_STATUS_SELECTOR);
};

const applyConversationEnterAnimation = (container: Element): void => {
    if (!(container instanceof HTMLElement)) {
        return;
    }
    container.classList.remove(CONVERSATION_ENTER_CLASS);
    measureLayoutBox(container);
    container.classList.add(CONVERSATION_ENTER_CLASS);
    const view = container.ownerDocument.defaultView;
    let timeoutId: number | null = null;
    const cleanup = (): void => {
        container.removeEventListener('animationend', onEnd);
        if (timeoutId !== null) {
            view?.clearTimeout(timeoutId);
            timeoutId = null;
        }
        container.classList.remove(CONVERSATION_ENTER_CLASS);
    };
    const onEnd = (event: AnimationEvent): void => {
        if (event.target === container) {
            cleanup();
        }
    };
    container.addEventListener('animationend', onEnd);
    if (view) {
        timeoutId = view.setTimeout(cleanup, resolveMaxCssAnimationTotalMs(container) + CONVERSATION_ENTER_ANIMATION_CLEANUP_BUFFER_MS);
    }
};

const renderCurrentConversationView = async (host: ChatCurrentConversationRenderDependencies): Promise<ChatConversationRenderOutcome> => {
    const renderToken = host.taskScope.concurrency.beginRenderSequence('conversation-current');
    const isCurrent = (): boolean => host.taskScope.concurrency.isRenderSequenceCurrent('conversation-current', renderToken);
    const container = host.pageDom.optional(CHAT_SELECTORS.MESSAGES_CONTAINER);
    if (!container) {
        return 'not-rendered';
    }
    let contentUpdated = false;
    const conversation = host.conversationView.current();
    const conversationKey = resolveCurrentConversationKey(host, conversation);
    const previousCache = host.viewState.conversationRenderCache;
    const isCurrentStreaming = Boolean(conversationKey) ? host.conversationView.isStreaming(conversationKey) : false;
    const activeComparisonRun: ActiveComparisonRun | null = conversationKey ? host.conversationView.activeComparisonRun(conversationKey) : null;
    const streamingController = host.turnRuntime.hasStreaming() ? host.turnRuntime.requireStreaming() : null;
    const activeStreamIdentity = conversationKey && streamingController ? streamingController.getStreamIdentity(conversationKey) : null;
    const renderAnalysis = analyzeConversationProjection(conversation, {
        isCurrentStreaming,
        activeComparisonRun,
        activeStreamIdentity,
        isMessagePendingDeletion: (messageDomId) => host.conversationRuntime.requireMessages().isMessagePendingDeletion(conversation, messageDomId),
        isTerminalRenderPending: (conversationId, message) => streamingController?.isTerminalRenderPending(conversationId, message) === true
    });
    const selectedConversationState = resolveSelectedConversationViewState(host, conversation, renderAnalysis.logicalMessageCount, isCurrentStreaming, conversationKey);
    const showEmptyState = selectedConversationState === 'empty';
    const showLoadingState = selectedConversationState === 'loading';
    const showErrorState = selectedConversationState === 'error';
    const showEarlierMessagesLoading = selectedConversationState === 'messages' && conversation?.history?.backgroundStatus === 'loading' && conversation.history.backgroundDirection === 'before' && conversation.history.hasOlder;
    const showNewerMessagesLoading = selectedConversationState === 'messages' && conversation?.history?.backgroundStatus === 'loading' && conversation.history.backgroundDirection === 'after' && conversation.history.hasNewer;
    const activeVariantIndexByAssistantTurnTimestamp = host.modelSession.syncComparisonSelection(renderAnalysis);
    const renderEntries = selectedConversationState === 'messages' ? resolveRenderableConversationEntries(renderAnalysis, { activeVariantIndexByAssistantTurnTimestamp }) : [];
    const shouldAnimateConversationEnter = selectedConversationState === 'messages' && hasLoadingConversationStatus(container);
    if (selectedConversationState === 'messages' && isCurrent()) {
        const removed = clearStaleCurrentConversationStatusNodes(container);
        if (removed) {
            host.emptyState.dispose();
        }
    }
    if (showEmptyState || showLoadingState || showErrorState) {
        if (isCurrent()) {
            contentUpdated = renderCurrentConversationStatusState(host, {
                container,
                previousCache,
                selectedConversationState,
                conversationKey
            });
        }
    } else if (isCurrent()) {
        const messageRenderState = renderCurrentConversationMessageState({
            host,
            container,
            previousCache,
            conversationKey,
            renderEntries,
            isCurrentStreaming,
            showEarlierMessagesLoading,
            showNewerMessagesLoading
        });
        if (messageRenderState === 'unchanged') {
            if (!isCurrent()) {
                return 'superseded';
            }
            finalizeCurrentConversationUi(host, {
                container,
                conversation,
                conversationKey,
                contentUpdated: false,
                messagesCommitted: true
            });
            return 'messages-unchanged';
        }
        contentUpdated = true;
        if (shouldAnimateConversationEnter) {
            applyConversationEnterAnimation(container);
        }
    }
    if (!isCurrent()) {
        return 'superseded';
    }
    finalizeCurrentConversationUi(host, {
        container,
        conversation,
        conversationKey,
        contentUpdated,
        messagesCommitted: selectedConversationState === 'messages'
    });
    return 'dom-reconciled';
};
export { renderCurrentConversationView };
