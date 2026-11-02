/* SoAI - Shared lifecycle cleanup stack [frontend/assets/ts/core/lifecycle/cleanupStack.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';

type Cleanup = () => void;

interface CleanupStackHost {
    logError: (message: string, error: Error) => void;
}

class CleanupStack {
    readonly #host: CleanupStackHost;
    #cleanups: Cleanup[] = [];
    #status: 'active' | 'disposing' | 'disposed' = 'active';
    readonly #failures: Error[] = [];

    constructor(host: CleanupStackHost) {
        this.#host = host;
    }

    add(cleanup: Cleanup): Cleanup {
        if (this.#status !== 'active') {
            try {
                cleanup();
            } catch (error) {
                const failure = ensureError(error);
                this.#cleanups.push(cleanup);
                this.#failures.push(failure);
                throw failure;
            }
            throw new LifecycleCancellationError('CleanupStack is disposed', 'cleanup-stack-disposed');
        }
        this.#cleanups.push(cleanup);
        return cleanup;
    }

    dispose(): readonly Error[] {
        if (this.#status === 'disposing') return [new LifecycleCancellationError('CleanupStack disposal is already running', 'cleanup-stack-disposal-pending')];
        if (this.#status === 'disposed') return [...this.#failures];
        this.#status = 'disposing';
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
                this.#cleanups.push(cleanup);
                this.#failures.push(runtimeError);
                try {
                    this.#host.logError('CleanupStack cleanup failed', runtimeError);
                } catch (diagnosticError) {
                    this.#failures.push(ensureError(diagnosticError));
                }
            }
        }
        this.#status = 'disposed';
        return [...this.#failures];
    }

    get status(): 'active' | 'disposing' | 'disposed' {
        return this.#status;
    }

    get size(): number {
        return this.#cleanups.length;
    }
}

export { CleanupStack };
export type { Cleanup, CleanupStackHost };
