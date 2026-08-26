/* SoAI - Shared lifecycle cleanup stack [frontend/assets/ts/core/lifecycle/cleanupStack.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';

type Cleanup = () => void;

interface CleanupStackHost {
    logError: (message: string, error: Error) => void;
}

class CleanupStack {
    readonly #host: CleanupStackHost;
    #cleanups: Cleanup[] = [];
    #disposed: boolean = false;

    constructor(host: CleanupStackHost) {
        this.#host = host;
    }

    add(cleanup: Cleanup): Cleanup {
        if (this.#disposed) {
            throw new Error('CleanupStack is disposed');
        }
        this.#cleanups.push(cleanup);
        return cleanup;
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        const cleanups = this.#cleanups;
        this.#cleanups = [];
        for (let index = cleanups.length - 1; index >= 0; index -= 1) {
            const cleanup = cleanups[index];
            if (cleanup === undefined) {
                continue;
            }
            try {
                cleanup();
            } catch (error) {
                const runtimeError = ensureError(error);
                this.#host.logError('CleanupStack cleanup failed', runtimeError);
            }
        }
    }

    get size(): number {
        return this.#cleanups.length;
    }
}

export { CleanupStack };
export type { Cleanup, CleanupStackHost };
