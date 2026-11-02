/* SoAI - Shared concurrency latest request [frontend/assets/ts/core/concurrency/latestRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleScope } from '@core/lifecycle/lifecycleScope.ts';

interface LatestRequestRun {
    readonly signal: AbortSignal;
    isCurrent(): boolean;
    isStale(): boolean;
}

class LatestRequestController {
    readonly #scope = new LifecycleScope();

    invalidate(): void {
        this.#scope.abort('latest-request-invalidated');
    }

    async runLatest<T>(operation: (run: LatestRequestRun) => Promise<T>, staleResult: T | null = null): Promise<T | null> {
        const lifetime = this.#scope.begin('latest-request-superseded');
        const run: LatestRequestRun = {
            signal: lifetime.signal,
            isCurrent: () => this.#scope.isCurrent(lifetime),
            isStale: () => !this.#scope.isCurrent(lifetime)
        };
        try {
            if (run.isStale()) return staleResult;
            const result = await operation(run);
            return run.isCurrent() ? result : staleResult;
        } catch (error) {
            if (run.isStale()) return staleResult;
            throw error;
        } finally {
            this.#scope.complete(lifetime);
        }
    }
}

export { LatestRequestController };
export type { LatestRequestRun };
