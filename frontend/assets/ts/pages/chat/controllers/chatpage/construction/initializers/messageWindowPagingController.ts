/* SoAI - Chat page message window paging controller [frontend/assets/ts/pages/chat/controllers/chatpage/construction/initializers/messageWindowPagingController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureScrollEdges } from '@core/dom/scrollGeometry.ts';
import { CHAT_SELECTORS, type Conversation, type LoadConversationMessagesOptions } from '@features/chat/public.ts';
import type { ChatConcurrencyController, MessageWindowIntent } from '@pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts';

type MessageWindowRequestDirection = 'before' | 'after';

interface MessageWindowPagingHost {
    sessions: {
        conversationView: { current(): Conversation | null; renderCurrent(): Promise<void> };
        taskScope: { concurrency: ChatConcurrencyController; run(operationId: string, operation: () => Promise<void>): void };
    };
    state: { conversationState: { conversations: Map<string, Conversation>; currentConversationId: string | null } };
    page: { pageDom: { optional(selector: string): Element | null } };
    runtime: {
        conversationRuntime: { requireStorage(): { loadConversationMessages(conversationId: string, options: LoadConversationMessagesOptions): Promise<void> } };
        composerSurface: { requireUi(): { requestOlderMessagesIfAtTop(): void } };
    };
}

const MESSAGE_WINDOW_EDGE_THRESHOLD_PX = 96;

const isAtLoadEdge = (messagesArea: HTMLElement, direction: MessageWindowRequestDirection): boolean => {
    const edges = measureScrollEdges({ position: messagesArea.scrollTop, extent: messagesArea.scrollHeight, viewport: messagesArea.clientHeight, tolerance: MESSAGE_WINDOW_EDGE_THRESHOLD_PX });
    return direction === 'before' ? edges.atStart : edges.atEnd;
};

const resolveRestingBackgroundStatus = (conversation: Conversation): 'idle' | 'complete' => {
    return conversation.history?.hasOlder === true || conversation.history?.hasNewer === true ? 'idle' : 'complete';
};

const syncMessageWindowLoadingState = async (page: MessageWindowPagingHost, conversationId: string, direction: MessageWindowRequestDirection, loading: boolean, isCurrent: () => boolean): Promise<void> => {
    if (!isCurrent()) return;
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

const requestConversationMessageWindow = (page: MessageWindowPagingHost, pendingRequests: Map<string, MessageWindowIntent>, direction: MessageWindowRequestDirection): void => {
    const intent = page.sessions.taskScope.concurrency.captureMessageWindowPaging();
    if (intent === null) return;
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
    if (pendingRequests.get(requestKey)?.isCurrent()) {
        return;
    }
    pendingRequests.set(requestKey, intent);
    const isCurrent = (): boolean => intent.isCurrent() && page.state.conversationState.currentConversationId === conversationId;
    page.sessions.taskScope.run(`chat:loadMessageWindow:${requestKey}`, async () => {
        let loadingStateCleared = false;
        let shouldRecheckLoadEdge = false;
        let loadingHistory: Conversation['history'];
        try {
            if (!isCurrent()) {
                return;
            }
            loadingHistory = conversation.history;
            await syncMessageWindowLoadingState(page, conversationId, direction, true, isCurrent);
            if (!isCurrent()) {
                return;
            }
            await page.runtime.conversationRuntime.requireStorage().loadConversationMessages(conversationId, {
                direction,
                cursor,
                force: true,
                signal: intent.signal,
                isCurrentOperation: isCurrent
            });
            if (!isCurrent()) {
                return;
            }
            await syncMessageWindowLoadingState(page, conversationId, direction, false, isCurrent);
            if (!isCurrent()) return;
            loadingStateCleared = true;
            shouldRecheckLoadEdge = true;
        } finally {
            const ownsPendingRequest = pendingRequests.get(requestKey) === intent;
            if (ownsPendingRequest) pendingRequests.delete(requestKey);
            if (!loadingStateCleared && ownsPendingRequest) {
                if (isCurrent()) {
                    await syncMessageWindowLoadingState(page, conversationId, direction, false, isCurrent);
                } else if (conversation.history === loadingHistory && loadingHistory?.backgroundStatus === 'loading' && loadingHistory.backgroundDirection === direction) {
                    loadingHistory.backgroundStatus = resolveRestingBackgroundStatus(conversation);
                    loadingHistory.backgroundDirection = null;
                }
            }
            if (shouldRecheckLoadEdge && direction === 'before' && isCurrent()) {
                page.runtime.composerSurface.requireUi().requestOlderMessagesIfAtTop();
            }
        }
    });
};

export { requestConversationMessageWindow };
export type { MessageWindowPagingHost, MessageWindowRequestDirection };
