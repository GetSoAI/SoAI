/* SoAI - Normalized collection channel ownership [frontend/assets/ts/core/data/clientdatahub/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionResourceStore } from '@core/data/clientdatahub/collectionResourceStore.ts';
import { normalizeResourceItemList } from '@core/data/clientdatahub/guards.ts';
import type { CollectionResourceSnapshot, LocalCollectionOperation, OptimisticCollectionOperation, OptimisticTerminalStatus } from '@core/data/clientdatahub/collectionResourceContracts.ts';
import type { ClientDataHubDependencies, CollectionChannelDefinition, ResourceListener } from '@core/data/clientdatahub/types.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { isArray } from '@core/typeGuards.ts';

class CollectionResourceChannel {
    readonly #definition: CollectionChannelDefinition;
    readonly #dependencies: Pick<ClientDataHubDependencies, 'subscribeResourceState' | 'refreshResource'>;
    readonly #store: CollectionResourceStore;
    readonly #listeners = new Set<ResourceListener>();
    readonly #listenerDiagnosticTimes = new Map<ResourceListener, number>();
    #unsubscribeResource: (() => void) | null = null;
    #recoveryTask: Promise<void> | null = null;
    #protocolFaultReported = false;

    constructor(definition: CollectionChannelDefinition, dependencies: Pick<ClientDataHubDependencies, 'subscribeResourceState' | 'refreshResource'>) {
        this.#definition = definition;
        this.#dependencies = dependencies;
        this.#store = new CollectionResourceStore(definition.resource, definition.trackBy);
    }

    get snapshot(): CollectionResourceSnapshot {
        return this.#store.snapshot;
    }

    hasPendingOptimisticOperation(itemId: string): boolean {
        return this.#store.hasPendingOptimisticOperation(itemId);
    }

    addListener(listener: ResourceListener, emitInitial: boolean): () => void {
        this.#listeners.add(listener);
        if (emitInitial) this.#deliver(listener, this.#store.snapshot);
        this.#connect();
        let active = true;
        return (): void => {
            if (!active) return;
            active = false;
            this.#listeners.delete(listener);
            this.#listenerDiagnosticTimes.delete(listener);
            if (this.#listeners.size === 0) this.#disconnect();
        };
    }

    applyLocalOperation(operation: LocalCollectionOperation): CollectionResourceSnapshot {
        return this.#publish(this.#store.applyLocalOperation(operation));
    }

    beginOptimisticOperation(operation: OptimisticCollectionOperation): CollectionResourceSnapshot {
        return this.#publish(this.#store.beginOptimisticOperation(operation));
    }

    markOptimisticOperationTerminal(operationId: string, status: OptimisticTerminalStatus): CollectionResourceSnapshot {
        const snapshot = this.#publish(this.#store.markOptimisticOperationTerminal(operationId, status));
        if (status !== 'succeeded') this.#requestRecovery();
        return snapshot;
    }

    dispose(): void {
        this.#listeners.clear();
        this.#listenerDiagnosticTimes.clear();
        this.#disconnect();
    }

    #connect(): void {
        if (this.#unsubscribeResource) return;
        this.#unsubscribeResource = this.#dependencies.subscribeResourceState(this.#definition.resource, (snapshot): void => this.#applyResourceSnapshot(snapshot));
    }

    #disconnect(): void {
        const unsubscribe = this.#unsubscribeResource;
        this.#unsubscribeResource = null;
        unsubscribe?.();
    }

    #applyResourceSnapshot(snapshot: ResourceReconciliationSnapshot): void {
        const committedAt = snapshot.authoritativeUpdatedAtMonotonicMs ?? snapshot.staleSinceMonotonicMs ?? performance.now();
        if (snapshot.status === 'ready' && !isArray(snapshot.value)) {
            this.#rejectProtocolValue(snapshot, committedAt, new Error('Ready collection value is not an array'));
            return;
        }
        try {
            const value = snapshot.status === 'ready' ? normalizeResourceItemList(snapshot.value, `${this.#definition.resource} resource`) : null;
            const next = this.#store.applyResourceState({
                status: snapshot.status,
                value,
                revision: snapshot.committedReconciliationRevision,
                committedAtMonotonicMs: committedAt,
                source: snapshot.authoritativeSource ?? 'stream',
                reason: snapshot.authoritativeReason ?? snapshot.transitionType
            });
            if (snapshot.status === 'ready') this.#protocolFaultReported = false;
            this.#publish(next);
        } catch (error) {
            this.#rejectProtocolValue(snapshot, committedAt, ensureError(error));
        }
    }

    #rejectProtocolValue(snapshot: ResourceReconciliationSnapshot, committedAt: number, error: Error): void {
        this.#publish(
            this.#store.applyResourceState({
                status: 'error',
                value: null,
                revision: snapshot.committedReconciliationRevision,
                committedAtMonotonicMs: committedAt,
                source: snapshot.authoritativeSource ?? 'stream',
                reason: 'malformed-ready-value'
            })
        );
        if (!this.#protocolFaultReported) {
            this.#protocolFaultReported = true;
            errorHandler.warn('ClientDataHub', `Collection resource ${this.#definition.resource} published a malformed ready value`, error);
        }
        this.#requestRecovery();
    }

    #requestRecovery(): void {
        if (this.#recoveryTask) return;
        const task = this.#dependencies
            .refreshResource(this.#definition.resource)
            .then((): void => {})
            .catch((error): void => {
                errorHandler.debug('ClientDataHub', `Collection recovery failed for ${this.#definition.resource}`, ensureError(error));
            })
            .finally((): void => {
                if (this.#recoveryTask === task) this.#recoveryTask = null;
            });
        this.#recoveryTask = task;
    }

    #publish(snapshot: CollectionResourceSnapshot): CollectionResourceSnapshot {
        for (const listener of [...this.#listeners]) this.#deliver(listener, snapshot);
        return snapshot;
    }

    #deliver(listener: ResourceListener, snapshot: CollectionResourceSnapshot): void {
        try {
            listener(snapshot);
        } catch (error) {
            const now = performance.now();
            const lastReportedAt = this.#listenerDiagnosticTimes.get(listener) ?? Number.NEGATIVE_INFINITY;
            if (now - lastReportedAt < 30_000) return;
            this.#listenerDiagnosticTimes.set(listener, now);
            errorHandler.warn('ClientDataHub', `Collection listener failed for ${this.#definition.resource}`, ensureError(error));
        }
    }
}

export { CollectionResourceChannel };
