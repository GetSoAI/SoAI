/* SoAI - Shared concurrency latest request [frontend/assets/ts/core/concurrency/latestRequest.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface LatestRequestRun {
    readonly signal: AbortSignal;
    isCurrent(): boolean;
    isStale(): boolean;
}

interface LatestRequestInternalRun extends LatestRequestRun {
    readonly controller: AbortController;
    readonly sequence: number;
}

class LatestRequestController {
    #controller: AbortController | null = null;
    #sequence = 0;

    #start(): LatestRequestInternalRun {
        this.#abort();
        const controller = new AbortController();
        this.#controller = controller;
        const sequence = this.#sequence + 1;
        this.#sequence = sequence;
        return {
            controller,
            sequence,
            signal: controller.signal,
            isCurrent: (): boolean => this.#isCurrent(sequence, controller),
            isStale: (): boolean => !this.#isCurrent(sequence, controller)
        };
    }

    #abort(): void {
        this.#controller?.abort();
        this.#controller = null;
    }

    invalidate(): void {
        this.#abort();
        this.#sequence += 1;
    }

    #isCurrent(sequence: number, controller: AbortController): boolean {
        return this.#sequence === sequence && this.#controller === controller && !controller.signal.aborted;
    }

    #complete(sequence: number, controller: AbortController): void {
        if (this.#sequence === sequence && this.#controller === controller) {
            this.#controller = null;
        }
    }

    async runLatest<T>(operation: (run: LatestRequestRun) => Promise<T>, staleResult: T | null = null): Promise<T | null> {
        const run = this.#start();
        try {
            const result = await operation(run);
            return run.isCurrent() ? result : staleResult;
        } catch (error) {
            if (run.isStale()) {
                return staleResult;
            }
            throw error;
        } finally {
            this.#complete(run.sequence, run.controller);
        }
    }
}

export { LatestRequestController };
export type { LatestRequestRun };
