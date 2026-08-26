/* SoAI - Transactional resource snapshot transitions [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationTransitions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ResourceReconciliationListener, ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

const LISTENER_DIAGNOSTIC_INTERVAL_MS = 30_000;

class ResourceReconciliationTransitions {
    readonly #name: string;
    readonly #listeners = new Set<ResourceReconciliationListener>();
    readonly #listenerDiagnosticTimes = new Map<ResourceReconciliationListener, number>();
    #snapshot: ResourceReconciliationSnapshot;
    #disposed = false;

    constructor(name: string) {
        this.#name = name;
        this.#snapshot = Object.freeze({
            name,
            value: null,
            status: 'unavailable',
            revision: 0,
            lifecycleGeneration: 0,
            configurationRevision: 0,
            desiredReconciliationRevision: 0,
            committedReconciliationRevision: 0,
            transportEpoch: 0,
            receiveSequence: 0,
            transitionType: 'initial-state',
            authoritativeSource: null,
            authoritativeReason: null,
            authoritativeUpdatedAtMonotonicMs: null,
            staleSinceMonotonicMs: null,
            retained: false,
            maintenance: false,
            error: null
        });
    }

    get snapshot(): ResourceReconciliationSnapshot {
        return this.#snapshot;
    }

    subscribe(listener: ResourceReconciliationListener, options: { immediate?: boolean } = {}): () => void {
        if (this.#disposed) throw new Error(`Resource ${this.#name} is disposed`);
        this.#listeners.add(listener);
        if (options.immediate !== false) this.#deliver(listener, this.#snapshot);
        let active = true;
        return (): void => {
            if (!active) return;
            active = false;
            this.#listeners.delete(listener);
            this.#listenerDiagnosticTimes.delete(listener);
        };
    }

    acceptReconciliation(): number {
        const desiredReconciliationRevision = this.#snapshot.desiredReconciliationRevision + 1;
        this.#commit({ desiredReconciliationRevision, transitionType: 'reconciliation-accepted' });
        return desiredReconciliationRevision;
    }

    invalidate(reason: string): number {
        const desiredReconciliationRevision = this.#snapshot.desiredReconciliationRevision + 1;
        this.#commit({
            desiredReconciliationRevision,
            transitionType: 'invalidation',
            status: 'recovering',
            authoritativeReason: reason,
            staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now(),
            retained: this.#snapshot.value !== null,
            error: null
        });
        return desiredReconciliationRevision;
    }

    beginAttempt(): void {
        this.#commit({
            status: this.#snapshot.value === null ? 'initializing' : 'recovering',
            transitionType: 'attempt-started',
            error: null,
            retained: this.#snapshot.value !== null
        });
    }

    commitValue(values: { value: JsonValue; reconciliationRevision: number; source: string; reason: string; receiveSequence: number; committedAtMonotonicMs: number }): void {
        this.#commit({
            value: values.value,
            status: 'ready',
            committedReconciliationRevision: values.reconciliationRevision,
            receiveSequence: values.receiveSequence,
            transitionType: values.reason,
            authoritativeSource: values.source,
            authoritativeReason: values.reason,
            authoritativeUpdatedAtMonotonicMs: values.committedAtMonotonicMs,
            staleSinceMonotonicMs: null,
            retained: false,
            error: null
        });
    }

    commitPush(values: { value: JsonValue; transportEpoch: number; receiveSequence: number; source: string; reason: string; committedAtMonotonicMs: number }): number {
        const reconciliationRevision = this.#snapshot.desiredReconciliationRevision + 1;
        this.#commit({
            value: values.value,
            status: 'ready',
            desiredReconciliationRevision: reconciliationRevision,
            committedReconciliationRevision: reconciliationRevision,
            transportEpoch: values.transportEpoch,
            receiveSequence: values.receiveSequence,
            transitionType: values.reason,
            authoritativeSource: values.source,
            authoritativeReason: values.reason,
            authoritativeUpdatedAtMonotonicMs: values.committedAtMonotonicMs,
            staleSinceMonotonicMs: null,
            retained: false,
            error: null
        });
        return reconciliationRevision;
    }

    markRecovering(reason: string): void {
        this.#commit({
            status: 'recovering',
            transitionType: reason,
            authoritativeReason: reason,
            staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now(),
            retained: this.#snapshot.value !== null,
            error: null
        });
    }

    markError(error: Error, reason: string): void {
        this.#commit({
            status: 'error',
            transitionType: reason,
            error,
            authoritativeReason: reason,
            retained: this.#snapshot.value !== null,
            staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now()
        });
    }

    markUnavailable(reason: string): void {
        this.#commit({
            value: null,
            transitionType: reason,
            status: 'unavailable',
            authoritativeSource: null,
            authoritativeReason: reason,
            authoritativeUpdatedAtMonotonicMs: null,
            staleSinceMonotonicMs: null,
            retained: false,
            error: null
        });
    }

    rejectPush(error: Error): number {
        const desiredReconciliationRevision = this.#snapshot.desiredReconciliationRevision + 1;
        this.#commit({
            desiredReconciliationRevision,
            transitionType: 'malformed-complete-push',
            status: 'recovering',
            error,
            authoritativeReason: 'malformed-complete-push',
            staleSinceMonotonicMs: this.#snapshot.staleSinceMonotonicMs ?? performance.now(),
            retained: this.#snapshot.value !== null
        });
        return desiredReconciliationRevision;
    }

    replaceTransportEpoch(transportEpoch: number): void {
        this.#commit({
            transportEpoch,
            transitionType: 'transport-replaced',
            receiveSequence: 0,
            status: this.#snapshot.value === null ? 'unavailable' : 'recovering',
            staleSinceMonotonicMs: this.#snapshot.value === null ? null : performance.now(),
            retained: this.#snapshot.value !== null,
            authoritativeReason: 'transport-replaced'
        });
    }

    disconnect(reason = 'disconnect'): void {
        this.#commit({
            status: 'disconnected',
            transitionType: 'disconnected',
            staleSinceMonotonicMs: this.#snapshot.value === null ? null : performance.now(),
            retained: this.#snapshot.value !== null,
            authoritativeReason: reason,
            error: null
        });
    }

    enterMaintenance(reason: string): void {
        this.#commit({ maintenance: true, status: 'disconnected', transitionType: 'maintenance-entered', retained: this.#snapshot.value !== null, authoritativeReason: reason, error: null });
    }

    exitMaintenance(): void {
        this.#commit({
            maintenance: false,
            transitionType: 'maintenance-ended',
            status: this.#snapshot.value === null ? 'unavailable' : 'recovering',
            retained: this.#snapshot.value !== null,
            staleSinceMonotonicMs: this.#snapshot.value === null ? null : (this.#snapshot.staleSinceMonotonicMs ?? performance.now()),
            authoritativeReason: 'maintenance-ended'
        });
    }

    reset(preserveValue: boolean): void {
        const value = preserveValue ? this.#snapshot.value : null;
        this.#commit({
            value,
            status: value === null ? 'unavailable' : 'recovering',
            transitionType: 'reset',
            lifecycleGeneration: this.#snapshot.lifecycleGeneration + 1,
            configurationRevision: this.#snapshot.configurationRevision + 1,
            authoritativeSource: null,
            authoritativeReason: 'reset',
            authoritativeUpdatedAtMonotonicMs: preserveValue ? this.#snapshot.authoritativeUpdatedAtMonotonicMs : null,
            staleSinceMonotonicMs: value === null ? null : performance.now(),
            retained: value !== null,
            maintenance: false,
            error: null
        });
    }

    dispose(): void {
        this.#disposed = true;
        this.#listeners.clear();
        this.#listenerDiagnosticTimes.clear();
    }

    #commit(changes: Partial<ResourceReconciliationSnapshot>): void {
        if (this.#disposed) return;
        this.#snapshot = Object.freeze({ ...this.#snapshot, ...changes, revision: this.#snapshot.revision + 1 });
        for (const listener of [...this.#listeners]) this.#deliver(listener, this.#snapshot);
    }

    #deliver(listener: ResourceReconciliationListener, snapshot: ResourceReconciliationSnapshot): void {
        try {
            listener(snapshot);
        } catch (error) {
            const now = performance.now();
            const lastReportedAt = this.#listenerDiagnosticTimes.get(listener) ?? Number.NEGATIVE_INFINITY;
            if (now - lastReportedAt < LISTENER_DIAGNOSTIC_INTERVAL_MS) return;
            this.#listenerDiagnosticTimes.set(listener, now);
            errorHandler.warn('ResourceReconciler', `Listener failed for ${this.#name}`, ensureError(error));
        }
    }
}

export { ResourceReconciliationTransitions };
