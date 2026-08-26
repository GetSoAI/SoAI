/* SoAI - Canonical per-page concurrency scope for chat [frontend/assets/ts/pages/chat/controllers/page/concurrency/ChatConcurrencyController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ConversationActivationSnapshot = {
    readonly sequence: number;
    readonly signal: AbortSignal;
};

class ChatConcurrencyController {
    #conversationActivationAbort: AbortController;
    #conversationActivationSequence: number;
    #workerRenderEpoch: number;
    #renderSequenceByScope: Map<string, number>;

    constructor() {
        this.#conversationActivationAbort = new AbortController();
        this.#conversationActivationSequence = 0;
        this.#workerRenderEpoch = 0;
        this.#renderSequenceByScope = new Map();
    }

    beginConversationActivation(): ConversationActivationSnapshot {
        this.#conversationActivationAbort.abort();
        this.#conversationActivationAbort = new AbortController();
        this.#conversationActivationSequence += 1;
        return this.captureConversationActivationSnapshot();
    }

    captureConversationActivationSnapshot(): ConversationActivationSnapshot {
        return { sequence: this.#conversationActivationSequence, signal: this.#conversationActivationAbort.signal };
    }

    isConversationActivationSnapshotCurrent(activation: ConversationActivationSnapshot, expectedConversationId: string, currentConversationId: string | null): boolean {
        if (activation.signal.aborted) {
            return false;
        }
        if (this.#conversationActivationSequence !== activation.sequence) {
            return false;
        }
        return currentConversationId === expectedConversationId;
    }

    isConversationActivationSnapshotLive(activation: ConversationActivationSnapshot): boolean {
        if (activation.signal.aborted) {
            return false;
        }
        return this.#conversationActivationSequence === activation.sequence;
    }

    clearConversationActivation(): void {
        this.#conversationActivationAbort.abort();
        this.#conversationActivationAbort = new AbortController();
        this.#conversationActivationSequence += 1;
    }

    bumpWorkerRenderEpoch(): number {
        this.#workerRenderEpoch += 1;
        return this.#workerRenderEpoch;
    }

    getWorkerRenderEpoch(): number {
        return this.#workerRenderEpoch;
    }

    beginRenderSequence(scope: string): number {
        const currentToken = this.#renderSequenceByScope.get(scope);
        const nextToken = (currentToken === undefined ? 0 : currentToken) + 1;
        this.#renderSequenceByScope.set(scope, nextToken);
        return nextToken;
    }

    isRenderSequenceCurrent(scope: string, token: number): boolean {
        return this.#renderSequenceByScope.get(scope) === token;
    }
}

export { ChatConcurrencyController };
export type { ConversationActivationSnapshot };
