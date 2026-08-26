/* SoAI - Resource reconciliation abort cleanup and bounded quarantine ownership [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationRetirement.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceAttempt } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

class ResourceAttemptRetirement {
    #orphanedAttempt: ResourceAttempt | null = null;
    #deferredRecovery = false;

    get hasOrphan(): boolean {
        return this.#orphanedAttempt !== null;
    }

    invalidate(attempt: ResourceAttempt | null, cleanupDeadlineMs: number, quarantine: (attempt: ResourceAttempt) => void): void {
        if (!attempt) return;
        attempt.authoritative = false;
        this.#abort(attempt, cleanupDeadlineMs, (): void => quarantine(attempt));
    }

    enforceDeadline(attempt: ResourceAttempt, cleanupDeadlineMs: number, quarantine: () => void): void {
        this.#abort(attempt, cleanupDeadlineMs, quarantine);
    }

    clearCleanupTimer(attempt: ResourceAttempt): void {
        if (attempt.cleanupTimer === null) return;
        window.clearTimeout(attempt.cleanupTimer);
        attempt.cleanupTimer = null;
    }

    quarantine(attempt: ResourceAttempt): boolean {
        this.clearCleanupTimer(attempt);
        attempt.authoritative = false;
        const orphanedAttempt = this.#orphanedAttempt;
        if (orphanedAttempt !== null) {
            this.#orphanedAttempt = null;
            this.#deferredRecovery = false;
            this.disposeAttempt(orphanedAttempt);
            this.disposeAttempt(attempt);
            return false;
        }
        this.#orphanedAttempt = attempt;
        return true;
    }

    consumeDeferredRecovery(): boolean {
        const deferredRecovery = this.#deferredRecovery;
        this.#deferredRecovery = false;
        return deferredRecovery;
    }

    releaseOrphan(identity: symbol): boolean {
        if (this.#orphanedAttempt?.identity !== identity) return false;
        this.#orphanedAttempt = null;
        return true;
    }

    disposeAttempt(attempt: ResourceAttempt): void {
        attempt.authoritative = false;
        attempt.controller.abort();
        this.clearCleanupTimer(attempt);
    }

    #abort(attempt: ResourceAttempt, cleanupDeadlineMs: number, quarantine: () => void): void {
        attempt.controller.abort();
        if (attempt.cleanupTimer !== null) return;
        attempt.cleanupTimer = window.setTimeout(quarantine, cleanupDeadlineMs);
    }
}

export { ResourceAttemptRetirement };
