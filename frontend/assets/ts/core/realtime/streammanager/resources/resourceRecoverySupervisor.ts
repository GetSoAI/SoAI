/* SoAI - Demand-owned resource recovery backoff supervisor [frontend/assets/ts/core/realtime/streammanager/resources/resourceRecoverySupervisor.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ReconciliationPolicy } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

class ResourceRecoverySupervisor {
    readonly #policy: ReconciliationPolicy;
    #timer: number | null = null;
    #failureCount = 0;
    #healthySinceMonotonicMs: number | null = null;
    #liveDemand = false;
    #disposed = false;

    constructor(policy: ReconciliationPolicy) {
        this.#policy = policy;
    }

    get scheduled(): boolean {
        return this.#timer !== null;
    }

    setLiveDemand(active: boolean): void {
        if (this.#disposed) return;
        this.#liveDemand = active;
        if (!active) this.cancel();
    }

    markHealthy(): void {
        if (this.#disposed) return;
        this.cancel();
        const now = performance.now();
        if (this.#healthySinceMonotonicMs === null) {
            this.#healthySinceMonotonicMs = now;
            return;
        }
        if (now - this.#healthySinceMonotonicMs >= this.#policy.recoveryResetAfterMs) {
            this.#failureCount = 0;
            this.#healthySinceMonotonicMs = now;
        }
    }

    schedule(eligible: () => boolean, recover: () => void): void {
        if (this.#disposed || !this.#liveDemand || this.#timer !== null || !eligible()) return;
        const now = performance.now();
        if (this.#healthySinceMonotonicMs !== null && now - this.#healthySinceMonotonicMs >= this.#policy.recoveryResetAfterMs) this.#failureCount = 0;
        this.#healthySinceMonotonicMs = null;
        const cap = Math.min(this.#policy.recoveryMaximumDelayMs, this.#policy.recoveryInitialDelayMs * 2 ** this.#failureCount);
        this.#failureCount += 1;
        const delay = Math.max(1, Math.floor(Math.random() * cap));
        this.#timer = window.setTimeout((): void => {
            this.#timer = null;
            if (this.#disposed || !this.#liveDemand || !eligible()) return;
            recover();
        }, delay);
    }

    cancel(): void {
        if (this.#timer === null) return;
        window.clearTimeout(this.#timer);
        this.#timer = null;
    }

    dispose(): void {
        this.#disposed = true;
        this.cancel();
    }
}

export { ResourceRecoverySupervisor };
