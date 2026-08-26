/* SoAI - Shared lifecycle scope [frontend/assets/ts/core/lifecycle/lifecycleScope.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getAbortControllerCtor } from '@core/environment/public.ts';

interface LifecycleRun {
    controller: AbortController;
    generation: number;
    signal: AbortSignal;
}

class LifecycleScope {
    #controller: AbortController | null;
    #generation: number;

    constructor() {
        this.#controller = null;
        this.#generation = 0;
    }

    begin(reason: string = 'reset'): LifecycleRun {
        if (this.#controller) {
            this.#controller.abort(reason);
        }
        this.#controller = new (getAbortControllerCtor())();
        this.#generation += 1;
        return this.current();
    }

    current(): LifecycleRun {
        const controller = this.#controller;
        if (!controller) {
            throw new Error('LifecycleScope is not initialized');
        }
        return {
            controller,
            generation: this.#generation,
            signal: controller.signal
        };
    }

    abort(reason: string = 'cleanup'): void {
        if (this.#controller) {
            this.#controller.abort(reason);
        }
        this.#controller = null;
        this.#generation += 1;
    }

    isCurrent(run: LifecycleRun): boolean {
        return run.controller === this.#controller && run.generation === this.#generation && !run.signal.aborted;
    }

    get controller(): AbortController | null {
        return this.#controller;
    }
}

export { LifecycleScope };
export type { LifecycleRun };
