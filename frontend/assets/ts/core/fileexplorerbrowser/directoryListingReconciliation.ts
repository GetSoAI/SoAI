/* SoAI - Finite filesystem listing invalidation and read admission [frontend/assets/ts/core/fileexplorerbrowser/directoryListingReconciliation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DirectoryListingFailure } from '@core/fileexplorerbrowser/directoryListingFailure.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { TIMEOUTS } from '@core/constants.ts';
import { getWindow } from '@core/environment/public.ts';
import { waitForTimerDelay } from '@core/concurrency/timerDelay.ts';
import { createAbortError, raceWithAbortSignal, runWithAbortSignalScope, throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { withAbortableTimeout } from '@core/primitives/withAbortableTimeout.ts';
import { createDeferred } from '@core/runtime/deferred.ts';

interface DirectoryListingCycle {
    readonly completion: Promise<boolean>;
    readonly controller: AbortController;
    readonly startedAtMs: number;
}

interface DirectoryListingReconciliationOptions {
    readonly replace: (signal: AbortSignal, canCommit: () => boolean) => Promise<boolean>;
    readonly markStale: (recovering?: boolean) => void;
    readonly reportFailure: (error: Error) => void;
}

class DirectoryListingReconciliation {
    readonly #options: DirectoryListingReconciliationOptions;
    #generation = 0;
    #cycle: DirectoryListingCycle | null = null;
    #read: Promise<void> | null = null;
    #exhausted = false;
    #disposed = false;

    constructor(options: DirectoryListingReconciliationOptions) {
        this.#options = options;
    }

    async read<Result>(operation: (canCommit: () => boolean) => Promise<Result>, authoritative = false): Promise<Result> {
        if (this.#disposed) throw createAbortError('Disposed listing cannot begin a read');
        const predecessor = this.#cycle;
        this.#cycle = null;
        const completion = createDeferred<void>();
        this.#read = completion.promise;
        const generation = this.#generation;
        const canCommit = (): boolean => !this.#disposed && this.#read === completion.promise && generation === this.#generation;
        predecessor?.controller.abort();
        try {
            if (predecessor) this.#options.markStale();
            if (this.#disposed || this.#read !== completion.promise) throw createAbortError('Listing read was superseded during admission');
            const result = await operation(canCommit);
            if (authoritative && result === true && canCommit()) this.#exhausted = false;
            return result;
        } finally {
            if (this.#read === completion.promise) this.#read = null;
            completion.resolve();
        }
    }

    invalidate(recover = false): Promise<boolean> {
        if (this.#disposed) return Promise.resolve(false);
        this.#generation += 1;
        const current = this.#cycle;
        if (current) {
            this.#options.markStale();
            return current.completion;
        }
        if (this.#exhausted && !recover) {
            this.#options.markStale();
            return Promise.resolve(false);
        }
        const completion = createDeferred<boolean>();
        const cycle: DirectoryListingCycle = { completion: completion.promise, controller: new AbortController(), startedAtMs: monotonicMs() };
        this.#cycle = cycle;
        try {
            this.#options.markStale(recover);
        } catch (error) {
            if (this.#cycle === cycle) {
                this.#cycle = null;
                this.#exhausted = true;
            }
            cycle.controller.abort();
            completion.reject(ensureError(error));
            return completion.promise;
        }
        const reconcile = async (): Promise<boolean> => {
            try {
                const remainingMs = TIMEOUTS.API_REQUEST - (monotonicMs() - cycle.startedAtMs);
                if (remainingMs <= 0) throw new DirectoryListingFailure('timeout', 'Listing reconciliation exceeded its admission deadline');
                return await withAbortableTimeout(
                    (deadlineSignal) =>
                        runWithAbortSignalScope([deadlineSignal, cycle.controller.signal], async (signal) => {
                            for (let attempt = 0; attempt < 2; attempt += 1) {
                                await waitForTimerDelay(getWindow(), TIMEOUTS.DEBOUNCE, signal);
                                while (this.#read) await raceWithAbortSignal(this.#read, signal);
                                throwIfAborted(signal);
                                if (monotonicMs() - cycle.startedAtMs >= TIMEOUTS.API_REQUEST) throw new DirectoryListingFailure('timeout', 'Listing reconciliation deadline elapsed before the next candidate');
                                const generation = this.#generation;
                                const canCommit = (): boolean => this.#cycle === cycle && !signal.aborted && monotonicMs() - cycle.startedAtMs < TIMEOUTS.API_REQUEST && generation === this.#generation;
                                const committed = await this.#options.replace(signal, canCommit);
                                if (canCommit()) return committed;
                            }
                            throwIfAborted(signal);
                            throw new DirectoryListingFailure('changed', 'Listing invalidation exceeded the candidate and trailing read budget');
                        }),
                    { timeoutMs: remainingMs, timeoutMessage: 'Directory listing reconciliation timed out' }
                );
            } catch (error) {
                if (this.#cycle === cycle && !cycle.controller.signal.aborted) this.#options.reportFailure(monotonicMs() - cycle.startedAtMs >= TIMEOUTS.API_REQUEST ? new DirectoryListingFailure('timeout', 'Directory listing reconciliation timed out') : ensureError(error));
                return false;
            }
        };
        const finish = (reconciled: boolean): void => {
            if (this.#cycle === cycle) {
                this.#cycle = null;
                this.#exhausted = !reconciled;
                if (!reconciled) this.#options.markStale();
            }
            completion.resolve(reconciled);
        };
        void reconcile().then(
            (reconciled) => {
                try {
                    finish(reconciled);
                } catch (error) {
                    completion.reject(ensureError(error));
                }
            },
            (error) => {
                if (this.#cycle === cycle) {
                    this.#cycle = null;
                    this.#exhausted = true;
                }
                completion.reject(ensureError(error));
            }
        );
        return completion.promise;
    }

    dispose(): void {
        this.#disposed = true;
        const cycle = this.#cycle;
        this.#cycle = null;
        cycle?.controller.abort();
    }
}

export { DirectoryListingReconciliation };
