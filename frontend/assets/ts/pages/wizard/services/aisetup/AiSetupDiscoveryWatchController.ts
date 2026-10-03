/* SoAI - Wizard AI setup deferred discovery watch [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupDiscoveryWatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { minutesToMs } from '@core/time/durations.ts';

const DISCOVERY_STALL_MS = minutesToMs(5);

class AiSetupDiscoveryWatchController {
    readonly #onStalled: () => void;
    readonly #timers = new ResourceTracker();
    readonly #timerIds = new Map<string, number>();
    readonly #stalled = new Set<string>();
    #disposed = false;

    constructor(onStalled: () => void) {
        this.#onStalled = onStalled;
    }

    get stalled(): ReadonlySet<string> {
        return this.#stalled;
    }

    arm(itemId: string): void {
        if (this.#disposed || this.#timerIds.has(itemId) || this.#stalled.has(itemId)) return;
        const timerId = this.#timers.setTimeout(() => {
            this.#timerIds.delete(itemId);
            this.#stalled.add(itemId);
            this.#onStalled();
        }, DISCOVERY_STALL_MS);
        this.#timerIds.set(itemId, timerId);
    }

    restart(itemId: string): void {
        this.clear(itemId);
        this.arm(itemId);
    }

    clear(itemId: string): void {
        const timerId = this.#timerIds.get(itemId);
        if (timerId !== undefined) this.#timers.clearTimer(timerId);
        this.#timerIds.delete(itemId);
        this.#stalled.delete(itemId);
    }

    dispose(): void {
        this.#disposed = true;
        this.#timers.cleanup();
        this.#timerIds.clear();
    }
}

export { AiSetupDiscoveryWatchController };
