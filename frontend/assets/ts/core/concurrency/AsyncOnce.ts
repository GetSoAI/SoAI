/* SoAI - Shared concurrency async once [frontend/assets/ts/core/concurrency/AsyncOnce.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class AsyncOnceGuard<T> {
    #disposed: boolean = false;
    #promise: Promise<T> | null = null;

    run(operation: () => Promise<T>): Promise<T> {
        if (this.#disposed) {
            return Promise.reject(new Error('AsyncOnceGuard cannot run after disposal.'));
        }
        const existing = this.#promise;
        if (existing) {
            return existing;
        }
        const inFlight = operation();
        const guarded = inFlight.catch((error) => {
            if (this.#promise === guarded) {
                this.#promise = null;
            }
            throw error;
        });
        this.#promise = guarded;
        return guarded;
    }

    dispose(): void {
        this.#disposed = true;
    }

    isDisposed(): boolean {
        return this.#disposed;
    }
}

export { AsyncOnceGuard };
