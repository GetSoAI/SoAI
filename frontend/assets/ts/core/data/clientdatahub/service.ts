/* SoAI - Normalized collection channel ownership [frontend/assets/ts/core/data/clientdatahub/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { LifecycleCancellationError } from '@core/errors/lifecycleCancellation.ts';
import { CleanupStack } from '@core/lifecycle/cleanupStack.ts';
import { throwCollectedCleanupFailures } from '@core/lifecycle/cleanup.ts';
import { CollectionResourceStore } from '@core/data/clientdatahub/collectionResourceStore.ts';
import { normalizeResourceItemList } from '@core/data/clientdatahub/guards.ts';
import type { CollectionResourceSnapshot, LocalCollectionOperation, OptimisticCollectionOperation, OptimisticTerminalStatus } from '@core/data/clientdatahub/collectionResourceContracts.ts';
import type { ClientDataHubDependencies, CollectionChannelDefinition, ResourceListener } from '@core/data/clientdatahub/types.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { isArray } from '@core/typeGuards.ts';

interface CollectionListenerRegistration {
    readonly listener: ResourceListener;
}

class CollectionResourceChannel {
    readonly #definition: CollectionChannelDefinition;
    readonly #dependencies: Pick<ClientDataHubDependencies, 'subscribeResourceState' | 'refreshResource'>;
    readonly #store: CollectionResourceStore;
    readonly #listeners = new Set<CollectionListenerRegistration>();
    readonly #listenerDiagnosticTimes = new Map<CollectionListenerRegistration, number>();
    #connection: CleanupStack | null = null;
    #acquiring: CleanupStack | null = null;
    #disposed = false;
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
        this.#requireActive();
        this.#requireConnectionAdmission();
        const registration = { listener };
        this.#listeners.add(registration);
        try {
            if (emitInitial) this.#deliver(registration, this.#store.snapshot);
            this.#requireActive();
            this.#connect();
        } catch (error) {
            this.#listeners.delete(registration);
            this.#listenerDiagnosticTimes.delete(registration);
            throw error;
        }
        let active = true;
        let failure: Error | null = null;
        return (): void => {
            if (failure !== null) throw failure;
            if (!active) return;
            active = false;
            this.#listeners.delete(registration);
            this.#listenerDiagnosticTimes.delete(registration);
            try {
                if (this.#listeners.size === 0) this.#disconnect();
            } catch (error) {
                failure = ensureError(error);
                throw failure;
            }
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
        this.#disposed = true;
        this.#listeners.clear();
        this.#listenerDiagnosticTimes.clear();
        this.#disconnect();
    }

    #requireActive(): void {
        if (this.#disposed) throw new LifecycleCancellationError('Collection channel is disposed', 'collection-channel-disposed');
    }

    #requireConnectionAdmission(): void {
        const connection = this.#connection;
        if (connection === null || connection.status === 'active') return;
        throwCollectedCleanupFailures(connection.dispose());
        throw new LifecycleCancellationError('Collection source release is unconfirmed', 'collection-source-release-pending');
    }

    #connect(): void {
        this.#requireConnectionAdmission();
        if (this.#connection) return;
        const connection = new CleanupStack({ logError: (message, error) => errorHandler.debug('ClientDataHub', message, error) });
        this.#connection = connection;
        this.#acquiring = connection;
        try {
            const unsubscribe = this.#dependencies.subscribeResourceState(this.#definition.resource, (snapshot): void => {
                if (!this.#disposed && this.#connection === connection && connection.status === 'active') this.#applyResourceSnapshot(snapshot);
            });
            if (this.#acquiring === connection) this.#acquiring = null;
            connection.add(unsubscribe);
        } catch (error) {
            if (this.#acquiring === connection) this.#acquiring = null;
            const cleanupFailures = connection.dispose();
            if (cleanupFailures.length === 0 && this.#connection === connection) this.#connection = null;
            throwCollectedCleanupFailures([...new Set([ensureError(error), ...cleanupFailures])]);
        }
    }

    #disconnect(): void {
        const connection = this.#connection;
        if (!connection) return;
        const failures = connection.dispose();
        throwCollectedCleanupFailures(failures);
        if (this.#acquiring === connection) throw new LifecycleCancellationError('Collection source acquisition has not returned its release handle', 'collection-source-acquisition-pending');
        if (this.#connection === connection) this.#connection = null;
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
        for (const registration of [...this.#listeners]) this.#deliver(registration, snapshot);
        return snapshot;
    }

    #deliver(registration: CollectionListenerRegistration, snapshot: CollectionResourceSnapshot): void {
        if (this.#disposed || !this.#listeners.has(registration)) return;
        try {
            registration.listener(snapshot);
        } catch (error) {
            const now = performance.now();
            const lastReportedAt = this.#listenerDiagnosticTimes.get(registration) ?? Number.NEGATIVE_INFINITY;
            if (now - lastReportedAt < 30_000) return;
            this.#listenerDiagnosticTimes.set(registration, now);
            errorHandler.warn('ClientDataHub', `Collection listener failed for ${this.#definition.resource}`, ensureError(error));
        }
    }
}

export { CollectionResourceChannel };
