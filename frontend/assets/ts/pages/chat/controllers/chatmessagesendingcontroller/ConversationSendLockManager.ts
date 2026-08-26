/* SoAI - Conversation send lock management [frontend/assets/ts/pages/chat/controllers/chatmessagesendingcontroller/ConversationSendLockManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import { createAbortError } from '@core/errors/abort.ts';
import { normalizeConversationId } from '@features/chat/public.ts';

const NEW_CONVERSATION_SEND_LOCK_KEY = 'new-conversation';

interface SendLockWaiter {
    id: number;
    keys: string[];
    signal: AbortSignal;
    completion: Deferred<SendLockLease>;
    removeAbortListener(): void;
}

const resolveSendLockKey = (conversationId: string | null | undefined): string => {
    const normalizedConversationId = normalizeConversationId(conversationId);
    return normalizedConversationId ? `conversation:${normalizedConversationId}` : NEW_CONVERSATION_SEND_LOCK_KEY;
};

const normalizeLockKeys = (keys: readonly string[]): string[] => {
    const resolved = new Set<string>();
    for (const key of keys) {
        const normalized = key.trim();
        if (normalized) {
            resolved.add(normalized);
        }
    }
    return Array.from(resolved.values()).sort((leftKey, rightKey) => leftKey.localeCompare(rightKey, 'en'));
};

class SendLockLease {
    readonly #manager: ConversationSendLockManager;
    readonly #id: number;
    readonly #keys = new Set<string>();
    #released = false;

    constructor(manager: ConversationSendLockManager, id: number, keys: readonly string[]) {
        this.#manager = manager;
        this.#id = id;
        for (const key of keys) {
            this.#keys.add(key);
        }
    }

    get id(): number {
        return this.#id;
    }

    get keys(): readonly string[] {
        return Array.from(this.#keys.values());
    }

    addKey(key: string): boolean {
        if (this.#released) {
            return false;
        }
        const normalizedKeys = normalizeLockKeys([key]);
        if (normalizedKeys.length !== 1) {
            return false;
        }
        const normalizedKey = normalizedKeys[0] ?? null;
        if (normalizedKey === null) {
            return false;
        }
        if (this.#keys.has(normalizedKey)) {
            return true;
        }
        if (!this.#manager.tryAddKeyToLease(this, normalizedKey)) {
            return false;
        }
        this.#keys.add(normalizedKey);
        return true;
    }

    release(): void {
        if (this.#released) {
            return;
        }
        this.#released = true;
        this.#manager.releaseLease(this.#id, this.keys);
        this.#keys.clear();
    }
}

class ConversationSendLockManager {
    readonly #heldByKey = new Map<string, number>();
    readonly #waiters: SendLockWaiter[] = [];
    #nextLeaseId = 0;
    #nextWaiterId = 0;

    tryAcquire(keys: readonly string[]): SendLockLease | null {
        const normalizedKeys = normalizeLockKeys(keys);
        if (!normalizedKeys.length || !this.#canAcquire(normalizedKeys)) {
            return null;
        }
        return this.#createLease(normalizedKeys);
    }

    async acquire(keys: readonly string[], signal: AbortSignal): Promise<SendLockLease> {
        if (signal.aborted) {
            throw createAbortError('Queued chat send was aborted.');
        }
        const lease = this.tryAcquire(keys);
        if (lease !== null) {
            return lease;
        }
        const normalizedKeys = normalizeLockKeys(keys);
        if (!normalizedKeys.length) {
            throw new Error('Queued chat send requires at least one lock key.');
        }
        const waiterId = this.#nextWaiterId + 1;
        this.#nextWaiterId = waiterId;
        const completion = createDeferred<SendLockLease>();
        const abortListener = (): void => {
            this.#removeWaiter(waiterId);
            completion.reject(createAbortError('Queued chat send was aborted.'));
        };
        signal.addEventListener('abort', abortListener, { once: true });
        this.#waiters.push({
            id: waiterId,
            keys: normalizedKeys,
            signal,
            completion,
            removeAbortListener: () => signal.removeEventListener('abort', abortListener)
        });
        return await completion.promise;
    }

    clear(): void {
        for (const waiter of this.#waiters.splice(0)) {
            waiter.removeAbortListener();
            waiter.completion.reject(new Error('Chat send lock manager was disposed.'));
        }
        this.#heldByKey.clear();
    }

    tryAddKeyToLease(lease: SendLockLease, key: string): boolean {
        const currentHolder = this.#heldByKey.get(key);
        if (currentHolder !== undefined && currentHolder !== lease.id) {
            return false;
        }
        this.#heldByKey.set(key, lease.id);
        return true;
    }

    releaseLease(leaseId: number, keys: readonly string[]): void {
        for (const key of keys) {
            if (this.#heldByKey.get(key) === leaseId) {
                this.#heldByKey.delete(key);
            }
        }
        this.#drainWaiters();
    }

    releaseKeys(keys: readonly string[]): void {
        const normalizedKeys = normalizeLockKeys(keys);
        for (const key of normalizedKeys) {
            this.#heldByKey.delete(key);
        }
        this.#drainWaiters();
    }

    #canAcquire(keys: readonly string[]): boolean {
        for (const key of keys) {
            if (this.#heldByKey.has(key)) {
                return false;
            }
        }
        return true;
    }

    #createLease(keys: readonly string[]): SendLockLease {
        const leaseId = this.#nextLeaseId + 1;
        this.#nextLeaseId = leaseId;
        for (const key of keys) {
            this.#heldByKey.set(key, leaseId);
        }
        return new SendLockLease(this, leaseId, keys);
    }

    #removeWaiter(waiterId: number): void {
        const index = this.#waiters.findIndex((waiter) => waiter.id === waiterId);
        if (index < 0) {
            return;
        }
        const waiter = this.#waiters[index];
        if (waiter === undefined) {
            return;
        }
        waiter.removeAbortListener();
        this.#waiters.splice(index, 1);
    }

    #drainWaiters(): void {
        let index = 0;
        while (index < this.#waiters.length) {
            const waiter = this.#waiters[index];
            if (waiter === undefined) {
                index += 1;
                continue;
            }
            if (waiter.signal.aborted) {
                waiter.removeAbortListener();
                this.#waiters.splice(index, 1);
                waiter.completion.reject(createAbortError('Queued chat send was aborted.'));
                continue;
            }
            if (!this.#canAcquire(waiter.keys)) {
                index += 1;
                continue;
            }
            this.#waiters.splice(index, 1);
            waiter.removeAbortListener();
            waiter.completion.resolve(this.#createLease(waiter.keys));
        }
    }
}

export { ConversationSendLockManager, SendLockLease, resolveSendLockKey };
