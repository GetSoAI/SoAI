/* SoAI - Single-owner bounded resource reconciliation [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciler.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ResourceRecoverySupervisor } from '@core/realtime/streammanager/resources/resourceRecoverySupervisor.ts';
import { createResourceAttempt, executeResourceAttempt } from '@core/realtime/streammanager/resources/resourceReconciliationExecution.ts';
import { admitResourceReconciliation, admitResourceRecovery } from '@core/realtime/streammanager/resources/resourceReconciliationAdmission.ts';
import { DEFAULT_RECONCILIATION_POLICY, validateReconciliationPolicy } from '@core/realtime/streammanager/resources/resourceReconciliationPolicy.ts';
import { ResourceAttemptQueue } from '@core/realtime/streammanager/resources/resourceReconciliationQueue.ts';
import { ResourceAttemptRetirement } from '@core/realtime/streammanager/resources/resourceReconciliationRetirement.ts';
import { ResourcePushOrdering } from '@core/realtime/streammanager/resources/resourcePushOrdering.ts';
import { ResourceReconciliationTransitions } from '@core/realtime/streammanager/resources/resourceReconciliationTransitions.ts';
import type { PushCommitContext, QueuedResourceAttempt, ReconciliationPolicy, ResourceAttempt, ResourceAttemptExecutor, ResourceReconcileOptions, ResourceReconciliationListener, ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { createImmutableResourceValue } from '@core/realtime/streammanager/resources/resourceValue.ts';
import { ResourceWaiterRegistry } from '@core/realtime/streammanager/resources/resourceWaiterRegistry.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

export class ResourceReconciler {
    readonly #name: string;
    readonly #policy: ReconciliationPolicy;
    readonly #transitions: ResourceReconciliationTransitions;
    readonly #waiters = new ResourceWaiterRegistry();
    readonly #recovery: ResourceRecoverySupervisor;
    readonly #pushOrdering = new ResourcePushOrdering();
    readonly #attemptQueue = new ResourceAttemptQueue();
    readonly #attemptRetirement = new ResourceAttemptRetirement();
    #activeAttempt: ResourceAttempt | null = null;
    #recoveryTemplate: Omit<QueuedResourceAttempt, 'targetReconciliationRevision'> | null = null;
    #maintenance = false;
    #disposed = false;

    constructor(name: string, policy: ReconciliationPolicy = DEFAULT_RECONCILIATION_POLICY) {
        this.#name = name.trim();
        if (!this.#name) throw new Error('Resource reconciler requires a name');
        this.#policy = validateReconciliationPolicy(policy);
        this.#transitions = new ResourceReconciliationTransitions(this.#name);
        this.#recovery = new ResourceRecoverySupervisor(this.#policy);
    }

    get snapshot(): ResourceReconciliationSnapshot {
        return this.#transitions.snapshot;
    }

    get reconciling(): boolean {
        return this.#activeAttempt !== null || this.#attemptRetirement.hasOrphan || this.#attemptQueue.hasStartingAttempt || this.#attemptQueue.current !== null || this.#recovery.scheduled;
    }

    subscribe(listener: ResourceReconciliationListener, options: { immediate?: boolean } = {}): () => void {
        if (this.#disposed) throw new Error(`Resource ${this.#name} is disposed`);
        return this.#transitions.subscribe(listener, options);
    }

    setLiveDemand(active: boolean): void {
        if (this.#disposed) return;
        this.#recovery.setLiveDemand(active);
        if (this.snapshot.status === 'error' || this.snapshot.status === 'recovering') this.#scheduleRecovery();
    }

    reconcile(executor: ResourceAttemptExecutor, options: ResourceReconcileOptions = {}): Promise<JsonValue | null> {
        return admitResourceReconciliation({
            name: this.#name,
            executor,
            options,
            attemptQueue: this.#attemptQueue,
            activeAttempt: this.#activeAttempt,
            hasOrphanedAttempt: this.#attemptRetirement.hasOrphan,
            waiters: this.#waiters,
            getSnapshot: () => this.snapshot,
            isDisposed: () => this.#disposed,
            isInMaintenance: () => this.#maintenance,
            acceptRevision: () => this.#transitions.acceptReconciliation(),
            setRecoveryTemplate: (template): void => {
                this.#recoveryTemplate = template;
            },
            startAttempt: (attempt): void => this.#startAttempt(attempt)
        });
    }

    invalidate(reason: string): void {
        if (this.#disposed || this.#maintenance || this.snapshot.status === 'disconnected') return;
        const targetReconciliationRevision = this.#transitions.invalidate(reason);
        this.#queueInvalidation(targetReconciliationRevision);
    }

    rejectPush(error: Error): void {
        if (this.#disposed || this.#maintenance || this.snapshot.status === 'disconnected') return;
        const targetReconciliationRevision = this.#transitions.rejectPush(error);
        this.#queueInvalidation(targetReconciliationRevision);
    }

    markUnavailable(reason: string): void {
        if (this.#disposed || this.snapshot.status === 'disconnected') return;
        this.#attemptRetirement.invalidate(this.#activeAttempt, this.#policy.abortCleanupDeadlineMs, (attempt): void => this.#quarantineAttempt(attempt));
        this.#attemptQueue.clear();
        this.#recovery.cancel();
        this.#waiters.resolve(this.snapshot.desiredReconciliationRevision, null);
        this.#transitions.markUnavailable(reason);
    }

    reportOperationalFailure(error: Error): void {
        if (this.#disposed || this.#maintenance || this.snapshot.status === 'disconnected') return;
        const failedThroughRevision = this.snapshot.desiredReconciliationRevision;
        this.#transitions.markError(error, 'operational-failure');
        this.#waiters.reject(error, failedThroughRevision);
        this.#scheduleRecovery();
    }

    seedInitialValue(value: JsonValue): void {
        if (this.#disposed || this.snapshot.revision !== 0) throw new Error(`Resource ${this.#name} initial value is already established`);
        const immutableValue = createImmutableResourceValue(value);
        this.#transitions.commitPush({
            value: immutableValue,
            transportEpoch: 0,
            receiveSequence: 1,
            source: 'initial',
            reason: 'registered-initial-value',
            committedAtMonotonicMs: performance.now()
        });
        this.#recovery.markHealthy();
    }

    commitPush(value: JsonValue, context: PushCommitContext): boolean {
        if (this.#disposed || this.#maintenance || this.snapshot.status === 'disconnected' || !this.#pushOrdering.accepts(context, this.snapshot.transportEpoch, this.snapshot.receiveSequence)) return false;
        const immutableValue = createImmutableResourceValue(value);
        this.#attemptQueue.clear();
        this.#recovery.cancel();
        this.#attemptRetirement.invalidate(this.#activeAttempt, this.#policy.abortCleanupDeadlineMs, (attempt): void => this.#quarantineAttempt(attempt));
        this.#pushOrdering.record(context);
        const expectedTransitionRevision = this.snapshot.revision + 1;
        const reconciliationRevision = this.#transitions.commitPush({
            value: immutableValue,
            transportEpoch: context.transportEpoch,
            receiveSequence: context.receiveSequence,
            source: 'websocket-push',
            reason: 'complete-push',
            committedAtMonotonicMs: performance.now()
        });
        this.#waiters.resolve(reconciliationRevision, immutableValue);
        if (this.snapshot.revision === expectedTransitionRevision) this.#recovery.markHealthy();
        return true;
    }

    replaceTransportEpoch(transportEpoch: number): void {
        if (!Number.isSafeInteger(transportEpoch) || transportEpoch <= this.snapshot.transportEpoch) throw new Error('Transport epoch must advance monotonically');
        this.#attemptRetirement.invalidate(this.#activeAttempt, this.#policy.abortCleanupDeadlineMs, (attempt): void => this.#quarantineAttempt(attempt));
        this.#attemptQueue.clear();
        this.#waiters.cancel(`Resource ${this.#name} transport was replaced`, 'transport-replaced');
        this.#transitions.replaceTransportEpoch(transportEpoch);
    }

    disconnect(): void {
        if (this.#disposed) return;
        this.#cancelOwnedWork(`Resource ${this.#name} disconnected`, 'resource-disconnected');
        this.#transitions.disconnect();
    }

    enterMaintenance(reason: string): void {
        if (this.#disposed || this.#maintenance) return;
        this.#maintenance = true;
        this.#cancelOwnedWork(`Resource ${this.#name} entered maintenance`, 'maintenance-entered');
        this.#transitions.enterMaintenance(reason);
    }

    exitMaintenance(): void {
        if (this.#disposed || !this.#maintenance) return;
        this.#maintenance = false;
        this.#transitions.exitMaintenance();
        this.#scheduleRecovery();
    }

    reset(options: { preserveValue: boolean }): void {
        if (this.#disposed) return;
        this.#maintenance = false;
        this.#cancelOwnedWork(`Resource ${this.#name} was reset`, 'resource-reset');
        this.#recoveryTemplate = null;
        this.#transitions.reset(options.preserveValue);
    }

    dispose(): void {
        if (this.#disposed) return;
        this.#disposed = true;
        this.#recovery.dispose();
        const activeAttempt = this.#activeAttempt;
        if (activeAttempt) {
            this.#attemptRetirement.disposeAttempt(activeAttempt);
            this.#activeAttempt = null;
        }
        this.#attemptQueue.clear();
        this.#waiters.cancel(`Resource ${this.#name} disposed`, 'resource-disposed');
        this.#transitions.dispose();
    }
    #queueInvalidation(targetReconciliationRevision: number): void {
        if (this.snapshot.desiredReconciliationRevision !== targetReconciliationRevision || this.snapshot.committedReconciliationRevision >= targetReconciliationRevision || this.snapshot.status === 'unavailable' || this.snapshot.status === 'disconnected' || this.snapshot.maintenance) return;
        const selection = this.#attemptQueue.selectInvalidation({ activeAttempt: this.#activeAttempt, canStart: !this.#attemptRetirement.hasOrphan, recoveryTemplate: this.#recoveryTemplate, targetReconciliationRevision });
        if (selection.invalidateActiveAttempt) this.#attemptRetirement.invalidate(this.#activeAttempt, this.#policy.abortCleanupDeadlineMs, (attempt): void => this.#quarantineAttempt(attempt));
        if (selection.startingAttempt) {
            this.#recovery.cancel();
            this.#startAttempt(selection.startingAttempt);
        }
    }

    #startAttempt(queued: QueuedResourceAttempt): void {
        if (this.#disposed || this.#maintenance) return;
        const attempt = createResourceAttempt(this.#name, queued, this.snapshot);
        this.#activeAttempt = attempt;
        this.#transitions.beginAttempt();
        attempt.promise = this.#runAttempt(attempt);
    }

    async #runAttempt(attempt: ResourceAttempt): Promise<void> {
        const outcome = await executeResourceAttempt({
            name: this.#name,
            policy: this.#policy,
            attempt,
            ownsAttempt: (candidate) => this.#ownsAttempt(candidate),
            handleDeadline: (candidate) => this.#handleAttemptDeadline(candidate)
        });
        if (outcome.type === 'success' && this.#ownsAttempt(attempt)) this.#commitValue(outcome.value, attempt.targetReconciliationRevision, attempt.source, 'reconciled', this.snapshot.receiveSequence);
        if (outcome.type === 'failed' && this.#ownsAttempt(attempt)) {
            this.#transitions.markError(outcome.error, 'finite-attempt-exhausted');
            this.#waiters.reject(outcome.error, attempt.targetReconciliationRevision);
        }
        this.#attemptRetirement.clearCleanupTimer(attempt);
        if (this.#attemptRetirement.releaseOrphan(attempt.identity)) {
            const queued = this.#attemptQueue.take();
            if (queued && !this.#disposed && !this.#maintenance && !this.#activeAttempt) this.#startAttempt(queued);
            else if (this.snapshot.status !== 'ready') this.#scheduleRecovery();
            return;
        }
        if (this.#activeAttempt?.identity !== attempt.identity) return;
        this.#activeAttempt = null;
        const queued = this.#attemptQueue.take();
        if (queued && !this.#disposed && !this.#maintenance) this.#startAttempt(queued);
        else if (this.#attemptRetirement.consumeDeferredRecovery() || outcome.type === 'failed' || this.snapshot.status === 'error' || this.snapshot.status === 'recovering') this.#scheduleRecovery();
    }

    #ownsAttempt(attempt: ResourceAttempt): boolean {
        return !this.#disposed && !this.#maintenance && attempt.authoritative && this.#activeAttempt?.identity === attempt.identity && attempt.transportEpoch === this.snapshot.transportEpoch && attempt.lifecycleGeneration === this.snapshot.lifecycleGeneration && attempt.configurationRevision === this.snapshot.configurationRevision;
    }

    #commitValue(value: JsonValue, reconciliationRevision: number, source: string, reason: string, receiveSequence: number): void {
        const expectedTransitionRevision = this.snapshot.revision + 1;
        this.#transitions.commitValue({ value, reconciliationRevision, source, reason, receiveSequence, committedAtMonotonicMs: performance.now() });
        this.#waiters.resolve(reconciliationRevision, value);
        if (this.snapshot.revision === expectedTransitionRevision) this.#recovery.markHealthy();
    }

    #cancelOwnedWork(message: string, reason: string): void {
        this.#attemptRetirement.invalidate(this.#activeAttempt, this.#policy.abortCleanupDeadlineMs, (attempt): void => this.#quarantineAttempt(attempt));
        this.#attemptQueue.clear();
        this.#recovery.cancel();
        this.#waiters.cancel(message, reason);
    }
    #handleAttemptDeadline(attempt: ResourceAttempt): void {
        if (!this.#ownsAttempt(attempt)) return;
        this.#attemptRetirement.enforceDeadline(attempt, this.#policy.abortCleanupDeadlineMs, (): void => this.#quarantineAttempt(attempt));
    }

    #quarantineAttempt(attempt: ResourceAttempt): void {
        if (this.#activeAttempt?.identity !== attempt.identity) return;
        const throughRevision = this.#attemptQueue.current?.targetReconciliationRevision ?? attempt.targetReconciliationRevision;
        const quarantined = this.#attemptRetirement.quarantine(attempt);
        this.#activeAttempt = null;
        if (!quarantined) {
            const error = new Error(`Resource ${this.#name} orphan capacity exhausted`);
            this.#attemptQueue.clear();
            this.#transitions.markError(error, 'orphan-capacity-exhausted');
            this.#waiters.reject(error, throughRevision);
            this.#scheduleRecovery();
            return;
        }
        const queued = this.#attemptQueue.take();
        if (queued && !this.#disposed && !this.#maintenance) {
            this.#startAttempt(queued);
            return;
        }
        const error = new Error(`Resource ${this.#name} abort cleanup deadline exceeded`);
        if ((this.snapshot.status === 'initializing' || this.snapshot.status === 'recovering') && attempt.transportEpoch === this.snapshot.transportEpoch && attempt.lifecycleGeneration === this.snapshot.lifecycleGeneration && attempt.configurationRevision === this.snapshot.configurationRevision && this.snapshot.committedReconciliationRevision <= throughRevision) {
            this.#transitions.markError(error, 'abort-cleanup-deadline');
            this.#waiters.reject(error, throughRevision);
        }
    }

    #scheduleRecovery(): void {
        this.#recovery.schedule(
            () => !this.#disposed && !this.#maintenance && !this.#activeAttempt && !this.#attemptRetirement.hasOrphan && this.#recoveryTemplate !== null,
            (): void => {
                const template = this.#recoveryTemplate;
                if (!template) return;
                admitResourceRecovery({
                    attemptQueue: this.#attemptQueue,
                    activeAttempt: this.#activeAttempt,
                    hasOrphanedAttempt: this.#attemptRetirement.hasOrphan,
                    template,
                    snapshot: this.snapshot,
                    acceptRevision: () => this.#transitions.acceptReconciliation(),
                    startAttempt: (attempt): void => this.#startAttempt(attempt)
                });
            }
        );
    }
}
