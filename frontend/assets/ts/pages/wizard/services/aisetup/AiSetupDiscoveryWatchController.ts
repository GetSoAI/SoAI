/* SoAI - Wizard AI setup bounded automatic discovery reconciliation [frontend/assets/ts/pages/wizard/services/aisetup/AiSetupDiscoveryWatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { minutesToMs } from '@core/time/durations.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isAbortError } from '@core/errors/abort.ts';
import { errorHandler } from '@core/errorHandler.ts';

interface DiscoveryWatch {
    startedAt: number;
    attempt: number;
    timerId: number | null;
}

const DISCOVERY_STALL_MS = minutesToMs(5);

class AiSetupDiscoveryWatchController {
    readonly #onStalled: () => void;
    readonly #refresh: () => Promise<void>;
    readonly #timers = new ResourceTracker();
    readonly #watches = new Map<string, DiscoveryWatch>();
    readonly #stalled = new Set<string>();
    #refreshing: Promise<void> | null = null;
    #disposed = false;

    constructor(onStalled: () => void, refresh: () => Promise<void>) {
        this.#onStalled = onStalled;
        this.#refresh = refresh;
    }

    get stalled(): ReadonlySet<string> {
        return this.#stalled;
    }

    arm(itemId: string): void {
        if (this.#disposed || this.#watches.has(itemId) || this.#stalled.has(itemId)) return;
        const watch: DiscoveryWatch = { startedAt: monotonicMs(), attempt: 0, timerId: null };
        this.#watches.set(itemId, watch);
        this.#schedule(itemId, watch);
    }

    clear(itemId: string): void {
        const watch = this.#watches.get(itemId);
        if (watch?.timerId !== null && watch?.timerId !== undefined) this.#timers.clearTimer(watch.timerId);
        this.#watches.delete(itemId);
        this.#stalled.delete(itemId);
    }

    dispose(): void {
        this.#disposed = true;
        this.#timers.cleanup();
        this.#watches.clear();
    }

    #schedule(itemId: string, watch: DiscoveryWatch): void {
        const remaining = DISCOVERY_STALL_MS - (monotonicMs() - watch.startedAt);
        if (remaining <= 0) {
            this.#watches.delete(itemId);
            this.#stalled.add(itemId);
            this.#onStalled();
            return;
        }
        watch.timerId = this.#timers.setTimeout(
            () => {
                watch.timerId = null;
                void this.#reconcile(itemId, watch).catch((error) => errorHandler.error('WizardAiSetup', 'Automatic discovery reconciliation failed', ensureError(error)));
            },
            Math.min(remaining, 1000 * Math.min(30, 2 ** watch.attempt))
        );
    }

    async #reconcile(itemId: string, watch: DiscoveryWatch): Promise<void> {
        if (this.#disposed || this.#watches.get(itemId) !== watch) return;
        try {
            this.#refreshing ??= this.#refresh();
            await this.#refreshing;
        } catch (error) {
            const runtimeError = ensureError(error);
            if (!this.#disposed && watch.attempt === 0 && !isAbortError(runtimeError)) errorHandler.warn('WizardAiSetup', 'Automatic model discovery refresh failed', runtimeError);
        } finally {
            this.#refreshing = null;
            watch.attempt += 1;
            if (!this.#disposed && this.#watches.get(itemId) === watch) this.#schedule(itemId, watch);
        }
    }
}

export { AiSetupDiscoveryWatchController };
