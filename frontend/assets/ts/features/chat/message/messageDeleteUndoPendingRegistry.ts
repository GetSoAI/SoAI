/* SoAI - Pending persisted message delete ownership [frontend/assets/ts/features/chat/message/messageDeleteUndoPendingRegistry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildPersistedMessageCursorKey } from '@features/chat/message/persistedMessageIdentity.ts';
import { normalizeMessageDomId } from '@features/chat/message/messageDomIds.ts';
import type { MessageCursor } from '@features/chat/storage/storageModels.ts';

type TimerHost = {
    setTimeout: (callback: (() => void) | undefined, delay: number) => number | null;
    clearTimer: (timerId: number) => void;
};

type PendingDeletePhase = 'countdown' | 'paused' | 'committing';

type PendingDeleteDescriptor = {
    targetKey: string;
    cursor: MessageCursor | null;
    renderIdentity: string;
    nonce: string;
    timerId: number | null;
    phase: PendingDeletePhase;
};

type CommitResult = {
    descriptor: PendingDeleteDescriptor | null;
};

class ChatMessageDeleteUndoPendingRegistry {
    readonly #pendingByConversationKey = new Map<string, Map<string, PendingDeleteDescriptor>>();
    #nextNonceId = 1;
    readonly #deleteDelayMs: number;
    readonly #onCommitTimer: (conversationKey: string, targetKey: string, nonce: string) => void;
    readonly #timers: TimerHost;

    constructor(dependencies: { deleteDelayMs: number; onCommitTimer: (conversationKey: string, targetKey: string, nonce: string) => void; timers: TimerHost }) {
        this.#deleteDelayMs = dependencies.deleteDelayMs;
        this.#onCommitTimer = dependencies.onCommitTimer;
        this.#timers = dependencies.timers;
    }

    dispose(): void {
        for (const pendingByCursor of this.#pendingByConversationKey.values()) {
            for (const descriptor of pendingByCursor.values()) {
                if (descriptor.timerId !== null) this.#timers.clearTimer(descriptor.timerId);
            }
        }
        this.#pendingByConversationKey.clear();
    }

    isConversationActive(conversationKey: string): boolean {
        return this.#pendingByConversationKey.has(conversationKey);
    }

    listPendingTargetKeys(conversationKey: string): string[] {
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey);
        if (!pendingByCursor) return [];
        return Array.from(pendingByCursor.entries())
            .filter(([, descriptor]) => descriptor.phase !== 'committing')
            .map(([targetKey]) => targetKey);
    }

    isPending(conversationKey: string, messageDomId: string): boolean {
        const renderIdentity = normalizeMessageDomId(messageDomId);
        if (!renderIdentity) return false;
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey);
        if (!pendingByCursor) return false;
        for (const descriptor of pendingByCursor.values()) {
            if (descriptor.renderIdentity === renderIdentity) return true;
        }
        return false;
    }

    requestDelete(conversationKey: string, messageDomId: string, cursor: MessageCursor | null): boolean {
        const renderIdentity = normalizeMessageDomId(messageDomId);
        if (!renderIdentity) return false;
        const targetKey = cursor === null ? `local:${renderIdentity}` : `persisted:${buildPersistedMessageCursorKey(cursor)}`;
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey) ?? new Map<string, PendingDeleteDescriptor>();
        if (pendingByCursor.has(targetKey)) return false;
        const nonce = this.#createNonce();
        const timerId = this.#timers.setTimeout(() => this.#onCommitTimer(conversationKey, targetKey, nonce), this.#deleteDelayMs);
        pendingByCursor.set(targetKey, { targetKey, cursor: cursor === null ? null : { ...cursor }, renderIdentity, nonce, timerId, phase: 'countdown' });
        this.#pendingByConversationKey.set(conversationKey, pendingByCursor);
        return true;
    }

    undoDelete(conversationKey: string, messageDomId: string): boolean {
        const resolved = this.#resolveByRenderIdentity(conversationKey, messageDomId);
        if (resolved === null || resolved.descriptor.phase === 'committing') return false;
        this.#remove(conversationKey, resolved.targetKey, resolved.descriptor);
        return true;
    }

    pauseDeleteCountdown(conversationKey: string, messageDomId: string): boolean {
        const resolved = this.#resolveByRenderIdentity(conversationKey, messageDomId);
        if (resolved === null || resolved.descriptor.phase === 'committing') return false;
        if (resolved.descriptor.timerId !== null) this.#timers.clearTimer(resolved.descriptor.timerId);
        resolved.descriptor.timerId = null;
        resolved.descriptor.nonce = this.#createNonce();
        resolved.descriptor.phase = 'paused';
        return true;
    }

    resumeDeleteCountdown(conversationKey: string, messageDomId: string): boolean {
        const resolved = this.#resolveByRenderIdentity(conversationKey, messageDomId);
        if (resolved === null || resolved.descriptor.phase === 'committing') return false;
        this.#schedule(conversationKey, resolved.targetKey, resolved.descriptor);
        return true;
    }

    resumeAllPaused(conversationKey: string): void {
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey);
        if (!pendingByCursor) return;
        for (const [targetKey, descriptor] of pendingByCursor) {
            if (descriptor.phase === 'paused') this.#schedule(conversationKey, targetKey, descriptor);
        }
    }

    commitIfCurrent(conversationKey: string, targetKey: string, nonce: string): CommitResult {
        const descriptor = this.#pendingByConversationKey.get(conversationKey)?.get(targetKey) ?? null;
        if (descriptor === null || descriptor.nonce !== nonce || descriptor.phase === 'committing') return { descriptor: null };
        return { descriptor: this.#markCommitting(descriptor) };
    }

    deferIfCurrent(conversationKey: string, targetKey: string, nonce: string): boolean {
        const descriptor = this.#pendingByConversationKey.get(conversationKey)?.get(targetKey) ?? null;
        if (descriptor === null || descriptor.nonce !== nonce || descriptor.phase === 'committing') return false;
        this.#schedule(conversationKey, targetKey, descriptor);
        return true;
    }

    commitNow(conversationKey: string, targetKey: string): CommitResult {
        const descriptor = this.#pendingByConversationKey.get(conversationKey)?.get(targetKey) ?? null;
        if (descriptor === null || descriptor.phase === 'committing') return { descriptor: null };
        return { descriptor: this.#markCommitting(descriptor) };
    }

    commitNowByRenderIdentity(conversationKey: string, messageDomId: string): CommitResult {
        const resolved = this.#resolveByRenderIdentity(conversationKey, messageDomId);
        if (resolved === null || resolved.descriptor.phase === 'committing') return { descriptor: null };
        return { descriptor: this.#markCommitting(resolved.descriptor) };
    }

    settle(conversationKey: string, targetKey: string): void {
        const descriptor = this.#pendingByConversationKey.get(conversationKey)?.get(targetKey) ?? null;
        if (descriptor !== null) this.#remove(conversationKey, targetKey, descriptor);
    }

    #markCommitting(descriptor: PendingDeleteDescriptor): PendingDeleteDescriptor {
        if (descriptor.timerId !== null) this.#timers.clearTimer(descriptor.timerId);
        descriptor.timerId = null;
        descriptor.phase = 'committing';
        return { ...descriptor, cursor: descriptor.cursor === null ? null : { ...descriptor.cursor } };
    }

    #schedule(conversationKey: string, targetKey: string, descriptor: PendingDeleteDescriptor): void {
        if (descriptor.timerId !== null) this.#timers.clearTimer(descriptor.timerId);
        const nonce = this.#createNonce();
        descriptor.nonce = nonce;
        descriptor.phase = 'countdown';
        descriptor.timerId = this.#timers.setTimeout(() => this.#onCommitTimer(conversationKey, targetKey, nonce), this.#deleteDelayMs);
    }

    #resolveByRenderIdentity(conversationKey: string, messageDomId: string): { targetKey: string; descriptor: PendingDeleteDescriptor } | null {
        const renderIdentity = normalizeMessageDomId(messageDomId);
        if (!renderIdentity) return null;
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey);
        if (!pendingByCursor) return null;
        for (const [targetKey, descriptor] of pendingByCursor) {
            if (descriptor.renderIdentity === renderIdentity) return { targetKey, descriptor };
        }
        return null;
    }

    #remove(conversationKey: string, cursorKey: string, descriptor: PendingDeleteDescriptor): void {
        if (descriptor.timerId !== null) this.#timers.clearTimer(descriptor.timerId);
        const pendingByCursor = this.#pendingByConversationKey.get(conversationKey);
        if (!pendingByCursor) return;
        pendingByCursor.delete(cursorKey);
        if (pendingByCursor.size === 0) this.#pendingByConversationKey.delete(conversationKey);
    }

    #createNonce(): string {
        const nonce = this.#nextNonceId;
        this.#nextNonceId += 1;
        return String(nonce);
    }
}

export { ChatMessageDeleteUndoPendingRegistry };
export type { PendingDeleteDescriptor };
