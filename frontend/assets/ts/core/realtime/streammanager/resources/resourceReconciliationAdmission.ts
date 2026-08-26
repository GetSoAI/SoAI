/* SoAI - Reentrant-safe resource reconciliation admission [frontend/assets/ts/core/realtime/streammanager/resources/resourceReconciliationAdmission.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { createAbortError } from '@core/errors/abort.ts';
import type { ResourceAttemptQueue } from '@core/realtime/streammanager/resources/resourceReconciliationQueue.ts';
import type { QueuedResourceAttempt, ResourceAttempt, ResourceAttemptExecutor, ResourceReconcileOptions, ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { ResourceWaiterRegistry } from '@core/realtime/streammanager/resources/resourceWaiterRegistry.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ResourceReconciliationAdmission {
    name: string;
    executor: ResourceAttemptExecutor;
    options: ResourceReconcileOptions;
    attemptQueue: ResourceAttemptQueue;
    activeAttempt: ResourceAttempt | null;
    hasOrphanedAttempt: boolean;
    waiters: ResourceWaiterRegistry;
    getSnapshot: () => ResourceReconciliationSnapshot;
    isDisposed: () => boolean;
    isInMaintenance: () => boolean;
    acceptRevision: () => number;
    setRecoveryTemplate: (template: Omit<QueuedResourceAttempt, 'targetReconciliationRevision'>) => void;
    startAttempt: (attempt: QueuedResourceAttempt) => void;
}

interface ResourceRecoveryAdmission {
    attemptQueue: ResourceAttemptQueue;
    activeAttempt: ResourceAttempt | null;
    hasOrphanedAttempt: boolean;
    template: Omit<QueuedResourceAttempt, 'targetReconciliationRevision'>;
    snapshot: ResourceReconciliationSnapshot;
    acceptRevision: () => number;
    startAttempt: (attempt: QueuedResourceAttempt) => void;
}

const admitResourceRecovery = (admission: ResourceRecoveryAdmission): void => {
    const selection = admission.attemptQueue.select({
        activeAttempt: admission.activeAttempt,
        orphanedAttempt: admission.hasOrphanedAttempt,
        source: admission.template.source,
        executor: admission.template.executor,
        force: true,
        nextReconciliationRevision: admission.snapshot.desiredReconciliationRevision + 1,
        acceptRevision: admission.acceptRevision
    });
    if (!selection.startsImmediately) return;
    const starting = admission.attemptQueue.takeStarting(selection.targetReconciliationRevision);
    if (starting) admission.startAttempt(starting);
};

const admitResourceReconciliation = (admission: ResourceReconciliationAdmission): Promise<JsonValue | null> => {
    if (admission.isDisposed()) return Promise.reject(new Error(`Resource ${admission.name} is disposed`));
    if (admission.isInMaintenance()) return Promise.reject(new Error(`Resource ${admission.name} is in maintenance`));
    if (admission.options.signal?.aborted) return Promise.reject(createAbortError());
    const acceptedSnapshot = admission.getSnapshot();
    if (acceptedSnapshot.status === 'disconnected') return Promise.reject(new Error(`Resource ${admission.name} disconnected`));
    const source = admission.options.source ?? 'fetch';
    admission.setRecoveryTemplate({ source, executor: admission.executor });
    if (!admission.options.force && acceptedSnapshot.status === 'ready') return Promise.resolve(acceptedSnapshot.value);
    const selection = admission.attemptQueue.select({
        activeAttempt: admission.activeAttempt,
        orphanedAttempt: admission.hasOrphanedAttempt,
        source,
        executor: admission.executor,
        force: admission.options.force === true,
        nextReconciliationRevision: acceptedSnapshot.desiredReconciliationRevision + 1,
        acceptRevision: admission.acceptRevision
    });
    const targetRevision = selection.targetReconciliationRevision;
    const waiter = admission.waiters.create(targetRevision, admission.options.signal ?? null);
    if (admission.isDisposed()) {
        admission.waiters.reject(new Error(`Resource ${admission.name} disposed`), targetRevision);
        return waiter;
    }
    if (admission.isInMaintenance()) {
        admission.waiters.reject(new Error(`Resource ${admission.name} is in maintenance`), targetRevision);
        return waiter;
    }
    const snapshot = admission.getSnapshot();
    if (snapshot.lifecycleGeneration !== acceptedSnapshot.lifecycleGeneration || snapshot.configurationRevision !== acceptedSnapshot.configurationRevision) {
        admission.waiters.reject(new Error(`Resource ${admission.name} ownership changed`), targetRevision);
        return waiter;
    }
    if (snapshot.committedReconciliationRevision >= targetRevision) {
        admission.waiters.resolve(snapshot.committedReconciliationRevision, snapshot.value);
        return waiter;
    }
    if (snapshot.status === 'disconnected') {
        admission.waiters.reject(new Error(`Resource ${admission.name} disconnected`), targetRevision);
        return waiter;
    }
    if (selection.startsImmediately) {
        const starting = admission.attemptQueue.takeStarting(targetRevision);
        if (starting) admission.startAttempt(starting);
        else admission.waiters.reject(new Error(`Resource ${admission.name} ownership changed`), targetRevision);
    }
    return waiter;
};

export { admitResourceReconciliation, admitResourceRecovery };
export type { ResourceReconciliationAdmission, ResourceRecoveryAdmission };
