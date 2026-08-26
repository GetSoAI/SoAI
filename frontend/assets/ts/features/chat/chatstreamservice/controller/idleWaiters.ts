/* SoAI - Chat stream idle waiter coordination [frontend/assets/ts/features/chat/chatstreamservice/controller/idleWaiters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError, throwIfAborted } from '@core/errors/abort.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { normalizeConversationId } from '@features/chat/validation/ids.ts';

interface ConversationIdleWaiter {
    deferred: Deferred<void>;
    isResolved(): boolean;
    removeAbortListener(): void;
}

type ConversationIdleWaiterState = Map<string, ConversationIdleWaiter[]>;

const resolveConversationIdleWaiters = (waiters: ConversationIdleWaiterState, conversationId: string): void => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    if (!normalizedConversationId) {
        return;
    }
    const entries = waiters.get(normalizedConversationId);
    if (!entries) {
        return;
    }
    const remaining: ConversationIdleWaiter[] = [];
    for (const waiter of entries) {
        if (!waiter.isResolved()) {
            remaining.push(waiter);
            continue;
        }
        waiter.removeAbortListener();
        waiter.deferred.resolve();
    }
    if (remaining.length === 0) {
        waiters.delete(normalizedConversationId);
    } else {
        waiters.set(normalizedConversationId, remaining);
    }
};

const rejectConversationIdleWaiters = (waiters: ConversationIdleWaiterState): void => {
    for (const entries of waiters.values()) {
        for (const waiter of entries) {
            waiter.removeAbortListener();
            waiter.deferred.reject(createAbortError('Chat stream idle wait cancelled'));
        }
    }
    waiters.clear();
};

const waitForConversationIdleState = async (inputArguments: { waiters: ConversationIdleWaiterState; conversationId: string; signal?: AbortSignal | null; isIdle(): boolean }): Promise<void> => {
    const signal = inputArguments.signal ?? null;
    throwIfAborted(signal, 'Chat stream idle wait aborted');
    if (inputArguments.isIdle()) {
        return;
    }
    const normalizedConversationId = normalizeConversationId(inputArguments.conversationId);
    if (!normalizedConversationId) {
        throw new Error('Chat stream idle wait requires a valid conversation id.');
    }
    const deferred = createDeferred<void>();
    const rejectWaiter = (): void => {
        removeWaiter();
        deferred.reject(createAbortError('Chat stream idle wait aborted'));
    };
    const abortListener = (): void => {
        rejectWaiter();
    };
    const removeWaiter = (): void => {
        signal?.removeEventListener('abort', abortListener);
        const entries = inputArguments.waiters.get(normalizedConversationId);
        if (!entries) {
            return;
        }
        const index = entries.findIndex((entry) => entry.deferred === deferred);
        if (index >= 0) {
            entries.splice(index, 1);
        }
        if (entries.length === 0) {
            inputArguments.waiters.delete(normalizedConversationId);
        }
    };
    signal?.addEventListener('abort', abortListener, { once: true });
    const entries = inputArguments.waiters.get(normalizedConversationId) ?? [];
    entries.push({ deferred, isResolved: inputArguments.isIdle, removeAbortListener: () => signal?.removeEventListener('abort', abortListener) });
    inputArguments.waiters.set(normalizedConversationId, entries);
    if (signal?.aborted === true) {
        rejectWaiter();
    } else if (inputArguments.isIdle()) {
        resolveConversationIdleWaiters(inputArguments.waiters, normalizedConversationId);
    }
    await deferred.promise;
};

export { rejectConversationIdleWaiters, resolveConversationIdleWaiters, waitForConversationIdleState };
export type { ConversationIdleWaiterState };
