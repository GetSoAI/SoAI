/* SoAI - Resource reconciliation target coalescing and force-refresh queue [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationQueue.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { QueuedResourceAttempt, ResourceAttempt, ResourceAttemptExecutor, ResourceAttemptSource } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';

interface ResourceTargetSelection {
    targetReconciliationRevision: number;
    startsImmediately: boolean;
}

interface ResourceInvalidationSelection {
    invalidateActiveAttempt: boolean;
    startingAttempt: QueuedResourceAttempt | null;
}

class ResourceAttemptQueue {
    #queued: QueuedResourceAttempt | null = null;
    #starting: QueuedResourceAttempt | null = null;

    get current(): QueuedResourceAttempt | null {
        return this.#queued;
    }

    get hasStartingAttempt(): boolean {
        return this.#starting !== null;
    }

    select(options: { activeAttempt: ResourceAttempt | null; orphanedAttempt: boolean; source: ResourceAttemptSource; executor: ResourceAttemptExecutor; force: boolean; nextReconciliationRevision: number; acceptRevision(): number }): ResourceTargetSelection {
        if (options.activeAttempt) {
            if (!options.activeAttempt.authoritative) return this.#selectQueued(options);
            if (!options.force) return { targetReconciliationRevision: options.activeAttempt.targetReconciliationRevision, startsImmediately: false };
            return this.#selectQueued(options);
        }
        if (options.orphanedAttempt) return this.#selectQueued(options);
        if (this.#starting) {
            if (!options.force) return { targetReconciliationRevision: this.#starting.targetReconciliationRevision, startsImmediately: false };
            return this.#selectQueued(options);
        }
        const starting = this.#createAttempt(options);
        this.#starting = starting;
        try {
            this.#acceptReservedAttempt(starting, options.acceptRevision);
        } catch (error) {
            if (this.#starting === starting) this.#starting = null;
            throw error;
        }
        return { targetReconciliationRevision: starting.targetReconciliationRevision, startsImmediately: true };
    }

    take(): QueuedResourceAttempt | null {
        const queued = this.#queued;
        this.#queued = null;
        return queued;
    }

    takeStarting(targetReconciliationRevision: number): QueuedResourceAttempt | null {
        if (this.#starting?.targetReconciliationRevision !== targetReconciliationRevision) return null;
        const starting = this.#starting;
        this.#starting = null;
        return starting;
    }

    clear(): void {
        this.#queued = null;
        this.#starting = null;
    }

    selectInvalidation(options: { activeAttempt: ResourceAttempt | null; canStart: boolean; recoveryTemplate: Omit<QueuedResourceAttempt, 'targetReconciliationRevision'> | null; targetReconciliationRevision: number }): ResourceInvalidationSelection {
        const activeAttempt = options.activeAttempt;
        if (activeAttempt?.authoritative && activeAttempt.targetReconciliationRevision >= options.targetReconciliationRevision) {
            return { invalidateActiveAttempt: false, startingAttempt: null };
        }
        if (activeAttempt || this.#starting) {
            this.#retainNewestTarget(options.recoveryTemplate, options.targetReconciliationRevision);
            return { invalidateActiveAttempt: activeAttempt?.authoritative === true, startingAttempt: null };
        }
        if (!options.canStart || !options.recoveryTemplate) return { invalidateActiveAttempt: false, startingAttempt: null };
        const startingAttempt = this.take() ?? { ...options.recoveryTemplate, targetReconciliationRevision: options.targetReconciliationRevision };
        return { invalidateActiveAttempt: false, startingAttempt };
    }

    #selectQueued(options: { source: ResourceAttemptSource; executor: ResourceAttemptExecutor; nextReconciliationRevision: number; acceptRevision(): number }): ResourceTargetSelection {
        let targetReconciliationRevision = this.#queued?.targetReconciliationRevision ?? null;
        if (!this.#queued) {
            const queued = this.#createAttempt(options);
            this.#queued = queued;
            targetReconciliationRevision = queued.targetReconciliationRevision;
            try {
                this.#acceptReservedAttempt(queued, options.acceptRevision);
            } catch (error) {
                if (this.#queued === queued) this.#queued = null;
                throw error;
            }
        }
        if (targetReconciliationRevision === null) throw new Error('Resource reconciliation queue failed to reserve a target revision');
        return { targetReconciliationRevision, startsImmediately: false };
    }

    #createAttempt(options: { source: ResourceAttemptSource; executor: ResourceAttemptExecutor; nextReconciliationRevision: number }): QueuedResourceAttempt {
        return {
            targetReconciliationRevision: options.nextReconciliationRevision,
            source: options.source,
            executor: options.executor
        };
    }

    #retainNewestTarget(template: Omit<QueuedResourceAttempt, 'targetReconciliationRevision'> | null, targetReconciliationRevision: number): void {
        if (!template || (this.#queued && this.#queued.targetReconciliationRevision >= targetReconciliationRevision)) return;
        this.#queued = { ...template, targetReconciliationRevision };
    }

    #acceptReservedAttempt(attempt: QueuedResourceAttempt, acceptRevision: () => number): void {
        const acceptedRevision = acceptRevision();
        if (acceptedRevision !== attempt.targetReconciliationRevision) throw new Error('Resource reconciliation revision ownership changed during admission');
    }
}

export { ResourceAttemptQueue };
