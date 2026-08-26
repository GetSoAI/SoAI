/* SoAI - Chat composer draft save chain [frontend/assets/ts/features/chat/composerdraft/composerDraftSaveChain.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { errorHandler } from '@core/errorHandler.ts';

class ComposerDraftSaveChain {
    readonly #chains = new Map<string, Promise<void>>();
    readonly #versions = new Map<string, number>();

    enqueue(conversationId: string, operation: (isCurrent: () => boolean) => Promise<void>): Promise<void> {
        const previous = this.#chains.get(conversationId) ?? Promise.resolve();
        const version = this.#advanceVersion(conversationId);
        const next = previous
            .catch((error) => {
                errorHandler.debug('ChatComposerDraftSaveChain', 'Previous draft save task failed before queued save', ensureError(error));
            })
            .then(async () => {
                if (!this.#isCurrentVersion(conversationId, version)) {
                    return;
                }
                await operation(() => this.#isCurrentVersion(conversationId, version));
            })
            .finally(() => {
                this.#dropChainIfCurrent(conversationId, version, next);
            });
        this.#chains.set(conversationId, next);
        return next;
    }

    async runImmediately(conversationId: string, operation: (isCurrent: () => boolean) => Promise<void>): Promise<void> {
        const previous = this.#chains.get(conversationId) ?? Promise.resolve();
        const version = this.#advanceVersion(conversationId);
        const previousSettlement = previous.catch((error) => {
            errorHandler.debug('ChatComposerDraftSaveChain', 'Previous draft save task failed before immediate save', ensureError(error));
        });
        const immediate = operation(() => this.#isCurrentVersion(conversationId, version));
        const next = immediate
            .finally(async () => {
                await previousSettlement;
            })
            .finally(() => this.#dropChainIfCurrent(conversationId, version, next));
        this.#chains.set(conversationId, next);
        await next;
    }

    wait(conversationId: string): Promise<void> {
        return this.#chains.get(conversationId) ?? Promise.resolve();
    }

    #advanceVersion(conversationId: string): number {
        const version = (this.#versions.get(conversationId) ?? 0) + 1;
        this.#versions.set(conversationId, version);
        return version;
    }

    #isCurrentVersion(conversationId: string, version: number): boolean {
        return this.#versions.get(conversationId) === version;
    }

    #dropChainIfCurrent(conversationId: string, version: number, promise: Promise<void>): void {
        if (this.#chains.get(conversationId) !== promise) {
            return;
        }
        this.#chains.delete(conversationId);
        if (this.#isCurrentVersion(conversationId, version)) {
            this.#versions.delete(conversationId);
        }
    }
}

export { ComposerDraftSaveChain };
