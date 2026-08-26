/* SoAI - Bounded chat message post-render batch scheduler [frontend/assets/ts/features/chat/message/postrender/chatPostRenderBatchScheduler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getCancelAnimationFrame, getRequestAnimationFrame } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ChatPostRenderCommit, ChatPostRenderContainerKey, ChatQueuedPostRenderMode } from '@features/chat/message/types.ts';
import type { ChatMessage } from '@features/chat/ChatTypes.ts';
import type { ChatPostRenderCapabilities } from '@features/chat/message/chatMessagePostRenderCapabilities.ts';

type ChatQueuedPostRenderEntry = {
    readonly callbacks: Set<ChatPostRenderCommit>;
    mode: ChatQueuedPostRenderMode;
    renderKey: ChatPostRenderContainerKey;
    readonly target: HTMLElement;
    assistantMessage: ChatMessage | null;
    capabilities: ChatPostRenderCapabilities | null;
    imageLifecyclePrepared: boolean;
    revision: number;
};

type ChatPostRenderBatchSchedulerDependencies = {
    execute: (entry: ChatQueuedPostRenderEntry) => void;
    reportError: (error: Error, context: string) => void;
};

const MAX_TARGETS_PER_FRAME = 4;

const resolveModePriority = (mode: ChatQueuedPostRenderMode): number => {
    if (mode === 'initialConversation') return 0;
    if (mode === 'canonicalFull') return 1;
    if (mode === 'full') return 2;
    return 3;
};

const renderKeysEqual = (left: ChatPostRenderContainerKey, right: ChatPostRenderContainerKey): boolean => {
    return left.conversationId === right.conversationId && left.epoch === right.epoch;
};

class ChatPostRenderBatchScheduler {
    readonly #dependencies: ChatPostRenderBatchSchedulerDependencies;
    readonly #entries: Map<HTMLElement, ChatQueuedPostRenderEntry>;
    readonly #latestRevisionByTarget: WeakMap<HTMLElement, number>;
    #frameId: number | null;
    #isDisposed: boolean;

    constructor(dependencies: ChatPostRenderBatchSchedulerDependencies) {
        this.#dependencies = dependencies;
        this.#entries = new Map();
        this.#latestRevisionByTarget = new WeakMap();
        this.#frameId = null;
        this.#isDisposed = false;
    }

    dispose(): void {
        this.#isDisposed = true;
        if (this.#frameId !== null) {
            getCancelAnimationFrame()(this.#frameId);
            this.#frameId = null;
        }
        for (const entry of this.#entries.values()) this.#settleCallbacks(entry);
        this.#entries.clear();
    }

    hasPendingWork(): boolean {
        return !this.#isDisposed && (this.#entries.size > 0 || this.#frameId !== null);
    }

    enqueue(inputArguments: { target: HTMLElement; mode: ChatQueuedPostRenderMode; renderKey: ChatPostRenderContainerKey; assistantMessage: ChatMessage | null; capabilities: ChatPostRenderCapabilities | null; imageLifecyclePrepared: boolean; onCommitted?: ChatPostRenderCommit }): { revision: number; shouldPrepareInitial: boolean } {
        if (this.#isDisposed) {
            if (inputArguments.onCommitted !== undefined) this.#settleCallback(inputArguments.onCommitted);
            return { revision: 0, shouldPrepareInitial: false };
        }
        const existing = this.#entries.get(inputArguments.target);
        const shouldPrepareInitial = inputArguments.mode === 'initialConversation' && (existing === undefined || (existing.mode === 'initialConversation' && !renderKeysEqual(existing.renderKey, inputArguments.renderKey)));
        const revision = (this.#latestRevisionByTarget.get(inputArguments.target) ?? 0) + 1;
        this.#latestRevisionByTarget.set(inputArguments.target, revision);
        if (existing === undefined) {
            const callbacks = new Set<ChatPostRenderCommit>();
            if (inputArguments.onCommitted !== undefined) callbacks.add(inputArguments.onCommitted);
            this.#entries.set(inputArguments.target, {
                callbacks,
                mode: inputArguments.mode,
                renderKey: inputArguments.renderKey,
                target: inputArguments.target,
                assistantMessage: inputArguments.assistantMessage,
                capabilities: inputArguments.capabilities,
                imageLifecyclePrepared: inputArguments.imageLifecyclePrepared,
                revision
            });
        } else {
            const previousCapabilities = existing.capabilities;
            if (resolveModePriority(inputArguments.mode) > resolveModePriority(existing.mode)) existing.mode = inputArguments.mode;
            existing.renderKey = inputArguments.renderKey;
            existing.assistantMessage = inputArguments.assistantMessage;
            existing.capabilities = previousCapabilities === null || inputArguments.capabilities === null ? null : inputArguments.capabilities;
            if (inputArguments.mode === 'initialConversation' && existing.mode !== 'initialConversation') {
                existing.imageLifecyclePrepared = false;
            } else if (inputArguments.mode !== 'initialConversation' || shouldPrepareInitial) {
                existing.imageLifecyclePrepared = inputArguments.imageLifecyclePrepared;
            }
            existing.revision = revision;
            if (inputArguments.onCommitted !== undefined) existing.callbacks.add(inputArguments.onCommitted);
        }
        this.#schedule();
        return { revision, shouldPrepareInitial };
    }

    completeInitialPreparation(target: HTMLElement, revision: number, imageLifecyclePrepared: boolean): void {
        const entry = this.#entries.get(target) ?? null;
        if (entry === null || entry.revision !== revision || entry.mode !== 'initialConversation') return;
        entry.imageLifecyclePrepared = imageLifecyclePrepared;
    }

    isLatest(entry: ChatQueuedPostRenderEntry): boolean {
        return !this.#isDisposed && this.#latestRevisionByTarget.get(entry.target) === entry.revision;
    }

    #flush(): void {
        if (this.#isDisposed) return;
        const batch: ChatQueuedPostRenderEntry[] = [];
        for (const [target, entry] of this.#entries) {
            this.#entries.delete(target);
            batch.push(entry);
            if (batch.length >= MAX_TARGETS_PER_FRAME) break;
        }
        for (const entry of batch) {
            try {
                this.#dependencies.execute(entry);
            } catch (error) {
                this.#dependencies.reportError(ensureError(error), 'Chat post-render target execution failed');
            } finally {
                this.#settleCallbacks(entry);
            }
        }
        if (this.#entries.size > 0) this.#schedule();
    }

    #schedule(): void {
        if (this.#frameId !== null || this.#isDisposed) return;
        this.#frameId = getRequestAnimationFrame()(() => {
            this.#frameId = null;
            this.#flush();
        });
    }

    #settleCallbacks(entry: ChatQueuedPostRenderEntry): void {
        for (const callback of entry.callbacks) this.#settleCallback(callback);
        entry.callbacks.clear();
    }

    #settleCallback(callback: ChatPostRenderCommit): void {
        try {
            callback();
        } catch (error) {
            this.#dependencies.reportError(ensureError(error), 'Chat terminal post-render callback failed');
        }
    }
}

export { ChatPostRenderBatchScheduler };
export type { ChatQueuedPostRenderEntry };
