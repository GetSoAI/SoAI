/* SoAI - Chat attach knowledge refresh lifecycle controller [frontend/assets/ts/pages/chat/controllers/modals/chatattach/ChatAttachKnowledgeRefreshLifecycleController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { countProcessingRagDocuments, type RagDocumentsPage } from '@features/chat/public.ts';
import type { ChatAttachKnowledgeRefreshHost } from '@pages/chat/controllers/modals/chatattach/contracts.ts';

class ChatAttachKnowledgeRefreshLifecycleController {
    readonly #host: ChatAttachKnowledgeRefreshHost;
    readonly #signal: AbortSignal;
    #loadSequence = 0;
    #pollTimer: number | null = null;
    #refreshAbortController: AbortController | null = null;

    constructor(host: ChatAttachKnowledgeRefreshHost, signal: AbortSignal) {
        this.#host = host;
        this.#signal = signal;
    }

    nextSequence(): number {
        this.#loadSequence += 1;
        return this.#loadSequence;
    }

    invalidate(): void {
        this.#loadSequence += 1;
    }

    abortRefresh(): void {
        const controller = this.#refreshAbortController;
        this.#refreshAbortController = null;
        if (controller !== null && !controller.signal.aborted) {
            controller.abort();
        }
    }

    replaceRefreshAbortController(): AbortController {
        this.abortRefresh();
        const controller = new AbortController();
        const abortRefreshController = (): void => {
            controller.abort();
        };
        if (this.#signal.aborted) {
            controller.abort();
            return controller;
        }
        this.#signal.addEventListener('abort', abortRefreshController, {
            once: true,
            signal: controller.signal
        });
        this.#refreshAbortController = controller;
        return controller;
    }

    releaseRefreshAbortController(controller: AbortController): void {
        if (this.#refreshAbortController === controller) {
            this.#refreshAbortController = null;
        }
        if (!controller.signal.aborted) {
            controller.abort();
        }
    }

    syncPoll(active: boolean, page: RagDocumentsPage | null, pollDelayMs: number, refresh: () => void): void {
        this.clearPoll();
        if (!active || page === null || countProcessingRagDocuments(page.statusCounts) <= 0) {
            return;
        }
        this.#pollTimer = this.#host.shared.pageResources.setTimer(() => {
            this.#pollTimer = null;
            if (active) {
                refresh();
            }
        }, pollDelayMs);
    }

    clearPoll(): void {
        if (this.#pollTimer === null) {
            return;
        }
        this.#host.shared.pageResources.clearTimer(this.#pollTimer);
        this.#pollTimer = null;
    }

    isCurrent(active: boolean, sequence: number, conversationId: string, currentConversationId: string | null, signal: AbortSignal): boolean {
        return active && !this.#signal.aborted && !signal.aborted && sequence === this.#loadSequence && currentConversationId === conversationId;
    }
}

export { ChatAttachKnowledgeRefreshLifecycleController };
