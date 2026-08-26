/* SoAI - Microtask-coalesced chat stream listener notifications [frontend/assets/ts/features/chat/chatstreamservice/streamNotificationQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import type { StreamMutation } from '@features/chat/chatstreamservice/contracts.ts';
import { notifyListeners, notifyListenersAndWait } from '@features/chat/chatstreamservice/events.ts';
import type { ChatStreamSession, StreamListener } from '@features/chat/chatstreamservice/types.ts';

interface PendingStreamNotification {
    session: ChatStreamSession;
    mutation: StreamMutation | null;
}

type ChatStreamNotificationRequestClearer = {
    clearRequest(conversationId: string, requestId: string): void;
};

const mergeStreamMutation = (current: StreamMutation | null, next: StreamMutation | undefined): StreamMutation | null => {
    if (!next) {
        return current;
    }
    if (current === null || current.type === 'replay') {
        return next;
    }
    if (next.type === 'terminal') {
        return next;
    }
    if (next.type === 'image') {
        return next;
    }
    if (next.type === 'text-delta') {
        const currentTextDelta = typeof current.textDelta === 'string' ? current.textDelta : '';
        const nextTextDelta = typeof next.textDelta === 'string' ? next.textDelta : '';
        return {
            type: 'text-delta',
            textDelta: `${currentTextDelta}${nextTextDelta}`
        };
    }
    return current.type === 'text-delta' ? current : next;
};

const flushPendingNotifications = (pendingByConversationId: Map<string, PendingStreamNotification>, sessions: ReadonlyMap<string, ChatStreamSession>, listeners: Set<StreamListener>): void => {
    const pending = Array.from(pendingByConversationId.entries());
    pendingByConversationId.clear();
    for (const [conversationId, pendingNotification] of pending) {
        const activeSession = sessions.get(conversationId);
        if (!activeSession || !activeSession.active || activeSession !== pendingNotification.session) {
            continue;
        }
        notifyListeners(listeners, activeSession, pendingNotification.mutation ?? undefined);
    }
};

class ChatStreamNotificationQueue {
    readonly #sessions: Map<string, ChatStreamSession>;
    readonly #listeners: Set<StreamListener>;
    #pendingMutationByConversationId = new Map<string, PendingStreamNotification>();
    readonly #scheduleFlush: () => void;
    #disposed = false;

    constructor(inputArguments: { sessions: Map<string, ChatStreamSession>; listeners: Set<StreamListener> }) {
        this.#sessions = inputArguments.sessions;
        this.#listeners = inputArguments.listeners;
        this.#scheduleFlush = createMicrotaskScheduler(() => flushPendingNotifications(this.#pendingMutationByConversationId, this.#sessions, this.#listeners), {
            label: 'ChatStreamNotificationQueue',
            isDisposed: () => this.#disposed
        });
    }

    #deletePendingMutation(session: ChatStreamSession): void {
        const pending = this.#pendingMutationByConversationId.get(session.conversationId);
        if (pending && pending.session !== session) {
            return;
        }
        this.#pendingMutationByConversationId.delete(session.conversationId);
    }

    clearRequest(conversationId: string, requestId: string): void {
        const pending = this.#pendingMutationByConversationId.get(conversationId);
        if (!pending || pending.session.requestId !== requestId) {
            return;
        }
        this.#pendingMutationByConversationId.delete(conversationId);
    }

    clearPending(): void {
        this.#pendingMutationByConversationId.clear();
    }

    flushPending(): void {
        if (this.#disposed) {
            return;
        }
        flushPendingNotifications(this.#pendingMutationByConversationId, this.#sessions, this.#listeners);
    }

    dispose(): void {
        this.#disposed = true;
        this.clearPending();
    }

    async notifyCheckpoint(session: ChatStreamSession, mutation: StreamMutation): Promise<void> {
        if (this.#disposed) {
            return;
        }
        this.#deletePendingMutation(session);
        await notifyListenersAndWait(this.#listeners, session, mutation);
    }

    notify(session: ChatStreamSession, mutation?: StreamMutation): void {
        if (this.#disposed) {
            return;
        }
        if (mutation?.type === 'replay' || mutation?.type === 'terminal') {
            this.#deletePendingMutation(session);
            notifyListeners(this.#listeners, session, mutation);
            return;
        }
        if (!this.#listeners.size) {
            this.#deletePendingMutation(session);
            return;
        }
        if (session.status !== 'streaming' || session.countsAsStreaming !== true) {
            this.#deletePendingMutation(session);
            notifyListeners(this.#listeners, session, mutation);
            return;
        }
        const current = this.#pendingMutationByConversationId.get(session.conversationId) ?? null;
        const currentMutation = current && current.session === session ? current.mutation : null;
        this.#pendingMutationByConversationId.set(session.conversationId, {
            session,
            mutation: mergeStreamMutation(currentMutation, mutation)
        });
        this.#scheduleFlush();
    }
}

export { ChatStreamNotificationQueue };
export type { ChatStreamNotificationRequestClearer };
