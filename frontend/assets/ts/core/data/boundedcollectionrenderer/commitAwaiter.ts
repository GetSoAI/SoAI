/* SoAI - Bounded collection initial-commit waiter lifecycle [frontend/assets/ts/core/data/boundedcollectionrenderer/commitAwaiter.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface CommitWaiter {
    resolve: (committed: boolean) => void;
    reject: (error: Error) => void;
    signal: AbortSignal | null;
    abort: () => void;
}

class CollectionCommitAwaiter {
    readonly #waiters = new Set<CommitWaiter>();
    #settled: boolean | Error | null = null;

    async wait(signal: AbortSignal | null): Promise<boolean> {
        if (signal?.aborted === true) return false;
        if (this.#settled instanceof Error) throw this.#settled;
        if (this.#settled !== null) return this.#settled;
        return await new Promise<boolean>((resolve, reject) => {
            let waiter: CommitWaiter;
            const abort = (): void => {
                this.#waiters.delete(waiter);
                resolve(false);
            };
            waiter = { resolve, reject, signal, abort };
            this.#waiters.add(waiter);
            signal?.addEventListener('abort', waiter.abort, { once: true });
        });
    }

    settle(committed: boolean | Error): void {
        if (this.#settled === null) this.#settled = committed;
        for (const waiter of this.#waiters) {
            waiter.signal?.removeEventListener('abort', waiter.abort);
            if (committed instanceof Error) waiter.reject(committed);
            else waiter.resolve(committed);
        }
        this.#waiters.clear();
    }
}

export { CollectionCommitAwaiter };
