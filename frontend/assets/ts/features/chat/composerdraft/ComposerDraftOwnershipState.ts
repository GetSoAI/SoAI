/* SoAI - Composer draft ownership and transfer state [frontend/assets/ts/features/chat/composerdraft/ComposerDraftOwnershipState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ComposerDraftTransferMode = 'restore' | 'adopt-current';
type ComposerDraftOwnerPhase = 'loading' | 'ready' | 'degraded';

interface ComposerDraftOwnershipSnapshot {
    readonly conversationId: string | null;
    readonly generation: number;
    readonly mutationToken: number;
    readonly mode: ComposerDraftTransferMode;
}

class ComposerDraftOwnershipState {
    #conversationId: string | null;
    #generation = 0;
    #mutationToken = 0;
    #phase: ComposerDraftOwnerPhase = 'ready';
    #mode: ComposerDraftTransferMode = 'restore';
    #highestDeferredRevision = 0;
    #loadingMutationToken = 0;

    constructor(conversationId: string | null) {
        this.#conversationId = conversationId;
    }

    get conversationId(): string | null {
        return this.#conversationId;
    }

    get phase(): ComposerDraftOwnerPhase {
        return this.#phase;
    }

    begin(conversationId: string | null, mode: ComposerDraftTransferMode): ComposerDraftOwnershipSnapshot {
        this.#generation += 1;
        this.#conversationId = conversationId;
        this.#phase = 'loading';
        this.#mode = mode;
        this.#highestDeferredRevision = 0;
        this.#loadingMutationToken = this.#mutationToken;
        return this.snapshot();
    }

    snapshot(): ComposerDraftOwnershipSnapshot {
        return {
            conversationId: this.#conversationId,
            generation: this.#generation,
            mutationToken: this.#mutationToken,
            mode: this.#mode
        };
    }

    isCurrent(snapshot: ComposerDraftOwnershipSnapshot, signal?: AbortSignal): boolean {
        return signal?.aborted !== true && snapshot.generation === this.#generation && snapshot.conversationId === this.#conversationId;
    }

    noteMutation(): void {
        this.#mutationToken += 1;
    }

    discard(conversationId: string): boolean {
        if (this.#conversationId !== conversationId) return false;
        this.#generation += 1;
        this.#conversationId = null;
        this.#phase = 'ready';
        this.#highestDeferredRevision = 0;
        return true;
    }

    surfaceChangedSince(snapshot: ComposerDraftOwnershipSnapshot): boolean {
        return this.#mutationToken !== snapshot.mutationToken;
    }

    deferRevision(revision: number): void {
        if (revision > this.#highestDeferredRevision) {
            this.#highestDeferredRevision = revision;
        }
    }

    highestDeferredRevision(snapshot: ComposerDraftOwnershipSnapshot): number {
        return this.isCurrent(snapshot) ? this.#highestDeferredRevision : 0;
    }

    isLocalProjectionAuthoritative(): boolean {
        return this.#phase !== 'loading' || this.#mode === 'adopt-current' || this.#mutationToken !== this.#loadingMutationToken;
    }

    finish(snapshot: ComposerDraftOwnershipSnapshot, degraded: boolean): void {
        if (!this.isCurrent(snapshot) || this.#phase !== 'loading') {
            return;
        }
        this.#phase = degraded ? 'degraded' : 'ready';
        this.#highestDeferredRevision = 0;
    }
}

export { ComposerDraftOwnershipState };
export type { ComposerDraftOwnershipSnapshot, ComposerDraftTransferMode };
