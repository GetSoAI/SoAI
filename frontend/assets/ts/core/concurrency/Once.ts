/* SoAI - Shared concurrency once [frontend/assets/ts/core/concurrency/Once.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

class OnceGuard {
    #didRun: boolean = false;
    #disposed: boolean = false;

    run(operation: () => void): void {
        if (this.#disposed) {
            throw new Error('OnceGuard cannot run after disposal.');
        }
        if (this.#didRun) {
            return;
        }
        this.#didRun = true;
        operation();
    }

    dispose(): void {
        this.#disposed = true;
    }

    hasRun(): boolean {
        return this.#didRun;
    }

    isDisposed(): boolean {
        return this.#disposed;
    }
}

export { OnceGuard };
