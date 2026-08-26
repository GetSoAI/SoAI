/* SoAI - Streaming timeline post-render reconciliation queue [frontend/assets/ts/features/chat/message/postrender/streamingTimelinePostRenderQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createMicrotaskScheduler } from '@core/primitives/microtaskScheduler.ts';
import { reconcileStreamingSpinnerStatusSubtree } from '@features/chat/stream/streamMessageSpinnerStatusRuntime.ts';
import { reconcileThinkingPreviewSubtree } from '@features/chat/stream/streamThinkingPreviewRuntime.ts';

type StreamingTimelineRenderKey = {
    conversationId: string;
    epoch: number;
};

interface StreamingTimelinePostRenderQueueDependencies {
    getCurrentConversationId: () => string | null;
    getWorkerRenderEpoch: () => number;
    isDisposed: () => boolean;
    notifyDomChanged: () => void;
}

class StreamingTimelinePostRenderQueue {
    readonly #dependencies: StreamingTimelinePostRenderQueueDependencies;
    readonly #queue: Set<HTMLElement>;
    readonly #renderKeyByContainer: WeakMap<HTMLElement, StreamingTimelineRenderKey>;
    readonly #scheduleFlush: () => void;

    constructor(dependencies: StreamingTimelinePostRenderQueueDependencies) {
        this.#dependencies = dependencies;
        this.#queue = new Set();
        this.#renderKeyByContainer = new WeakMap();
        this.#scheduleFlush = createMicrotaskScheduler(() => this.#flush(), {
            label: 'StreamingTimelinePostRenderQueue',
            isDisposed: () => this.#dependencies.isDisposed()
        });
    }

    dispose(): void {
        this.#queue.clear();
    }

    hasPendingWork(): boolean {
        return this.#queue.size > 0;
    }

    queue(container: HTMLElement): void {
        if (this.#dependencies.isDisposed()) {
            return;
        }
        const conversationId = this.#dependencies.getCurrentConversationId();
        if (conversationId !== null) {
            this.#renderKeyByContainer.set(container, {
                conversationId,
                epoch: this.#dependencies.getWorkerRenderEpoch()
            });
        }
        this.#queue.add(container);
        this.#scheduleFlush();
    }

    #targetIsCurrent(target: HTMLElement): boolean {
        const key = this.#renderKeyByContainer.get(target) ?? null;
        if (key === null) {
            return true;
        }
        const currentConversationId = this.#dependencies.getCurrentConversationId();
        return currentConversationId !== null && currentConversationId === key.conversationId && this.#dependencies.getWorkerRenderEpoch() === key.epoch;
    }

    #collectCurrentTargets(): HTMLElement[] {
        const targets = Array.from(this.#queue);
        this.#queue.clear();
        const currentTargets: HTMLElement[] = [];
        for (const target of targets) {
            if (!target.isConnected || !this.#targetIsCurrent(target)) {
                continue;
            }
            currentTargets.push(target);
        }
        const currentTargetSet = new Set(currentTargets);
        return currentTargets.filter((target) => {
            let ancestor = target.parentElement;
            while (ancestor !== null) {
                if (currentTargetSet.has(ancestor)) {
                    return false;
                }
                ancestor = ancestor.parentElement;
            }
            return true;
        });
    }

    #flush(): void {
        if (this.#dependencies.isDisposed()) {
            this.#queue.clear();
            return;
        }
        let changed = false;
        for (const target of this.#collectCurrentTargets()) {
            reconcileThinkingPreviewSubtree(target);
            reconcileStreamingSpinnerStatusSubtree(target);
            changed = true;
        }
        if (changed) {
            this.#dependencies.notifyDomChanged();
        }
    }
}

export { StreamingTimelinePostRenderQueue };
