/* SoAI - RAG ingestion pause resume scheduling [frontend/assets/ts/features/chat/ragingestion/RagIngestionPauseController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import { sleepMs } from '@core/primitives/sleepMs.ts';
import { monotonicMs } from '@core/time/clock.ts';

interface RagIngestionPauseControllerDependencies {
    getPausedUntilMs: () => number;
    isStopped: () => boolean;
    resume: () => void;
    warn: (message: string, error: Error) => void;
}

class RagIngestionPauseController {
    #dependencies: RagIngestionPauseControllerDependencies;
    #scheduled = false;
    #generation = 0;

    constructor(dependencies: RagIngestionPauseControllerDependencies) {
        this.#dependencies = dependencies;
    }

    reset(): void {
        this.#generation += 1;
        this.#scheduled = false;
    }

    schedule(): void {
        if (this.#scheduled) {
            return;
        }
        this.#scheduled = true;
        void this.#resumeAfterPause(this.#generation).catch((error) => {
            this.#dependencies.warn('Unhandled pause resume scheduling failure', ensureError(error));
        });
    }

    #isCurrent(generation: number): boolean {
        return this.#generation === generation && !this.#dependencies.isStopped();
    }

    async #resumeAfterPause(generation: number): Promise<void> {
        try {
            await sleepMs(Math.max(0, this.#dependencies.getPausedUntilMs() - monotonicMs()));
            if (!this.#isCurrent(generation)) {
                return;
            }
            this.#scheduled = false;
            this.#dependencies.resume();
        } catch (error) {
            if (!this.#isCurrent(generation)) {
                return;
            }
            this.#scheduled = false;
            this.#dependencies.warn('Failed to resume ingestion after pause window', ensureError(error));
        }
    }
}

export { RagIngestionPauseController };
