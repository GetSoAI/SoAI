/* SoAI - Routed page activation gate for prepared navigation candidates [frontend/assets/ts/core/routing/pages/basepage/PageActivationGate.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { raceWithAbortSignal } from '@core/errors/abort.ts';
import { createDeferred, type Deferred } from '@core/runtime/deferred.ts';
import type { PageRuntimePhases } from '@core/runtime/pageRuntimeContracts.ts';

class PageActivationGate {
    #pending: Deferred<void> | null = null;

    defer(): void {
        if (this.#pending) throw new Error('Page activation is already deferred');
        this.#pending = createDeferred<void>();
    }

    activate(): void {
        const pending = this.#pending;
        this.#pending = null;
        pending?.resolve(undefined);
    }

    cancel(): void {
        this.activate();
    }

    phases(phases: PageRuntimePhases): PageRuntimePhases {
        return {
            prepare: async (parameters, context): Promise<void> => {
                const pending = this.#pending;
                if (pending) await raceWithAbortSignal(pending.promise, context.signal);
                if (!context.signal.aborted) await phases.prepare(parameters, context);
            },
            afterReveal: async (context): Promise<void> => phases.afterReveal(context)
        };
    }
}

export { PageActivationGate };
