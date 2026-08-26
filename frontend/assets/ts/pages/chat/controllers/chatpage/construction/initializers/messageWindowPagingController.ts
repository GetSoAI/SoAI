/* SoAI - Chat page message window paging controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/messageWindowPagingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureScrollEdges } from '@core/dom/scrollGeometry.ts';
import { CHAT_SELECTORS, type Conversation } from '@features/chat/public.ts';
import type { ChatControllerInitializationContext } from '@pages/chat/controllers/chatpage/construction/initializers/contracts.ts';

type MessageWindowRequestDirection = 'before' | 'after';

const MESSAGE_WINDOW_EDGE_THRESHOLD_PX = 96;

const isAtLoadEdge = (messagesArea: HTMLElement, direction: MessageWindowRequestDirection): boolean => {
    const edges = measureScrollEdges({ position: messagesArea.scrollTop, extent: messagesArea.scrollHeight, viewport: messagesArea.clientHeight, tolerance: MESSAGE_WINDOW_EDGE_THRESHOLD_PX });
    return direction === 'before' ? edges.atStart : edges.atEnd;
};

const resolveRestingBackgroundStatus = (conversation: Conversation): 'idle' | 'complete' => {
    return conversation.history?.hasOlder === true || conversation.history?.hasNewer === true ? 'idle' : 'complete';
};

const syncMessageWindowLoadingState = async (page: ChatControllerInitializationContext, conversationId: string, direction: MessageWindowRequestDirection, loading: boolean): Promise<void> => {
    const conversation = page.state.conversationState.conversations.get(conversationId);
    if (conversation?.history === undefined) {
        return;
    }
    const nextStatus = loading ? 'loading' : resolveRestingBackgroundStatus(conversation);
    const nextDirection = loading ? direction : null;
    const stateAlreadySynced = conversation.history.backgroundStatus === nextStatus && conversation.history.backgroundDirection === nextDirection;
    if (stateAlreadySynced && loading) {
        return;
    }
    if (!stateAlreadySynced) {
        conversation.history.backgroundStatus = nextStatus;
        conversation.history.backgroundDirection = nextDirection;
    }
    if (page.state.conversationState.currentConversationId === conversationId) {
        await page.sessions.conversationView.renderCurrent();
    }
};

const requestConversationMessageWindow = (page: ChatControllerInitializationContext, pendingRequests: Set<string>, direction: MessageWindowRequestDirection): void => {
    const conversation = page.sessions.conversationView.current();
    if (conversation === null || conversation.history === undefined) {
        return;
    }
    const cursor = direction === 'before' ? conversation.history.oldestCursor : conversation.history.newestCursor;
    const hasMore = direction === 'before' ? conversation.history.hasOlder : conversation.history.hasNewer;
    if (cursor === null || !hasMore) {
        return;
    }
    const conversationId = conversation.id;
    const requestKey = `${conversationId}:${direction}`;
    const messagesArea = page.page.pageDom.optional(CHAT_SELECTORS.MESSAGES_AREA);
    const typedMessagesArea = messagesArea instanceof HTMLElement ? messagesArea : null;
    if (typedMessagesArea === null || !isAtLoadEdge(typedMessagesArea, direction)) {
        return;
    }
    if (pendingRequests.has(requestKey)) {
        return;
    }
    pendingRequests.add(requestKey);
    page.sessions.taskScope.run(`chat:loadMessageWindow:${requestKey}`, async () => {
        let loadingStateCleared = false;
        let shouldRecheckLoadEdge = false;
        try {
            if (page.state.conversationState.currentConversationId !== conversationId) {
                return;
            }
            await syncMessageWindowLoadingState(page, conversationId, direction, true);
            if (page.state.conversationState.currentConversationId !== conversationId) {
                return;
            }
            await page.runtime.conversationRuntime.requireStorage().loadConversationMessages(conversationId, {
                direction,
                cursor,
                force: true
            });
            if (page.state.conversationState.currentConversationId !== conversationId) {
                return;
            }
            await syncMessageWindowLoadingState(page, conversationId, direction, false);
            loadingStateCleared = true;
            shouldRecheckLoadEdge = true;
        } finally {
            pendingRequests.delete(requestKey);
            if (!loadingStateCleared) {
                await syncMessageWindowLoadingState(page, conversationId, direction, false);
            }
            if (shouldRecheckLoadEdge && direction === 'before') {
                page.runtime.composerSurface.requireUi().requestOlderMessagesIfAtTop();
            }
        }
    });
};

export { requestConversationMessageWindow };
export type { MessageWindowRequestDirection };
