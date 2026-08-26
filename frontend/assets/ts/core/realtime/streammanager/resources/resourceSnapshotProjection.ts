/* SoAI - Reconciled resource snapshot projection [frontend/assets/ts/core/realtime/streammanager/resources/resourceSnapshotProjection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import type { ResourceEntry } from '@core/realtime/streammanager/types.ts';

const projectReconciliationSnapshot = (resource: ResourceEntry, snapshot: ResourceReconciliationSnapshot): boolean => {
    if (resource.reconciler.snapshot !== snapshot) return false;
    resource.value = snapshot.value;
    resource.status = snapshot.status;
    resource.error = snapshot.error;
    resource.warning = snapshot.retained;
    resource.maintenance = snapshot.maintenance;
    resource.updatedAt = snapshot.authoritativeUpdatedAtMonotonicMs === null ? null : Date.now() - Math.max(0, performance.now() - snapshot.authoritativeUpdatedAtMonotonicMs);
    resource.lastSnapshot = null;
    return true;
};

const bindResourceReconciliation = (resource: ResourceEntry, onTransition: (snapshot: ResourceReconciliationSnapshot) => void): void => {
    resource.reconciliationUnsubscribe?.();
    resource.reconciliationUnsubscribe = resource.reconciler.subscribe(
        (snapshot): void => {
            if (projectReconciliationSnapshot(resource, snapshot)) onTransition(snapshot);
        },
        { immediate: true }
    );
};

export { bindResourceReconciliation, projectReconciliationSnapshot };
