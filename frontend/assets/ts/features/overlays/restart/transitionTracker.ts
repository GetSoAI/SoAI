/* SoAI - Restart transition evidence tracker [frontend/assets/ts/features/overlays/restart/transitionTracker.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { observePowerTransition } from '@features/overlays/powerTransitionObservation.ts';

interface RestartTransitionTrackerCallbacks {
    onInterrupted: () => void;
    onRecoveredConnection: () => void;
}

class RestartTransitionTracker {
    readonly #callbacks: RestartTransitionTrackerCallbacks;
    #unsubscribe: (() => void) | null = null;
    observeTransition = false;
    interruptionObserved = false;

    constructor(callbacks: RestartTransitionTrackerCallbacks) {
        this.#callbacks = callbacks;
    }

    begin(observeTransition: boolean): void {
        this.stop();
        this.observeTransition = observeTransition;
        if (!observeTransition) return;
        this.#unsubscribe = observePowerTransition({
            onInterrupted: () => {
                if (!this.observeTransition) return;
                this.interruptionObserved = true;
                this.#callbacks.onInterrupted();
            },
            onConnected: () => {
                if (this.observeTransition && this.interruptionObserved) this.#callbacks.onRecoveredConnection();
            }
        });
    }

    restoreInterruption(interruptionObserved: boolean): void {
        this.interruptionObserved = interruptionObserved;
    }

    stop(): void {
        this.#unsubscribe?.();
        this.#unsubscribe = null;
        this.observeTransition = false;
        this.interruptionObserved = false;
    }
}

export { RestartTransitionTracker };
