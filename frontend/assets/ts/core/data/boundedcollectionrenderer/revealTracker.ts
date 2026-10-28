/* SoAI - Bounded collection reveal request lifecycle [frontend/assets/ts/core/data/boundedcollectionrenderer/revealTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

interface PendingCollectionReveal {
    generation: number;
    resolve: (revealed: boolean) => void;
    release: () => void;
}

class CollectionRevealTracker {
    #pending: PendingCollectionReveal | null = null;

    begin(generation: number, signal: AbortSignal | null, onAbort: () => void): Promise<boolean> {
        return new Promise<boolean>((resolve) => {
            const abort = (): void => {
                if (this.#pending?.generation === generation) onAbort();
            };
            signal?.addEventListener('abort', abort, { once: true });
            this.#pending = { generation, resolve, release: () => signal?.removeEventListener('abort', abort) };
        });
    }

    isPending(): boolean {
        return this.#pending !== null;
    }

    isCurrent(generation: number): boolean {
        return this.#pending?.generation === generation;
    }

    finish(identifier: string, generation: number, container: HTMLElement | null, resolveItemIdentifier: (element: HTMLElement) => string | null, behavior: ScrollBehavior): void {
        if (!this.isCurrent(generation) || container === null) return;
        for (const child of container.children) {
            if (child instanceof HTMLElement && child.dataset['collectionId'] === identifier) {
                const candidate = dom.resolveAll('*', child).find((element) => element instanceof HTMLElement && resolveItemIdentifier(element) === identifier);
                const target = candidate instanceof HTMLElement ? candidate : child;
                target.scrollIntoView({ block: 'center', inline: 'nearest', behavior });
                this.settle(true);
                return;
            }
        }
        this.settle(false);
    }

    settle(revealed: boolean): void {
        const pending = this.#pending;
        this.#pending = null;
        pending?.release();
        pending?.resolve(revealed);
    }
}

export { CollectionRevealTracker };
