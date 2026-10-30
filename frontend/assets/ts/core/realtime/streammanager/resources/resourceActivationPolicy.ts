/* SoAI - Stream resource activation policy [frontend/assets/ts/core/realtime/streammanager/resources/resourceActivationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isSubscriptionOwnedResource, isResourceRecoveryBlocked } from '@core/realtime/streammanager/resources/resourceReconciliationPolicy.ts';
import type { ResourceEntry } from '@core/realtime/streammanager/types.ts';
interface AutoResourceStart {
    name: string;
    autoStart: boolean;
    status: string;
    pending: boolean;
}

const hasResourceSubscribers = (resource: ResourceEntry): boolean => resource.listeners.size > 0 || resource.typedSubscribers.size > 0;

const hasResourceLiveDemand = (resource: ResourceEntry): boolean => resource.config.autoStart || hasResourceSubscribers(resource);

const hasResourceDemand = (resource: ResourceEntry): boolean => hasResourceLiveDemand(resource) || (!isSubscriptionOwnedResource(resource.name) && resource.pendingStart !== null);

const releaseResourceDemand = (resource: ResourceEntry): void => {
    const active = hasResourceLiveDemand(resource);
    resource.reconciler.setLiveDemand(active);
    if (!active && isSubscriptionOwnedResource(resource.name)) resource.reconciler.reset({ preserveValue: true });
};

const invalidateResourceDemand = (resource: ResourceEntry, reason: string, start: () => void): void => {
    if (!hasResourceLiveDemand(resource) || resource.reconciler.snapshot.maintenance) return;
    const snapshot = resource.reconciler.snapshot;
    if (isResourceRecoveryBlocked(snapshot)) return;
    if (snapshot.status === 'error' && resource.reconciler.reconciling) return;
    resource.reconciler.invalidate(reason);
    if (hasResourceLiveDemand(resource) && !resource.reconciler.reconciling) start();
};

const listAutoResourceStarts = (resources: ReadonlyMap<string, ResourceEntry>): AutoResourceStart[] =>
    Array.from(resources.values()).map((resource) => ({
        name: resource.name,
        autoStart: resource.config.autoStart,
        status: resource.status,
        pending: resource.pendingStart !== null
    }));

const startListenedResources = (resources: ReadonlyMap<string, ResourceEntry>, startOwned: (name: string) => void): void => {
    resources.forEach((resource, name) => {
        if (hasResourceSubscribers(resource) && resource.status === 'unavailable' && resource.pendingStart === null) startOwned(name);
    });
};

const listReconnectResources = (resources: ReadonlyMap<string, ResourceEntry>): string[] => {
    const names: string[] = [];
    resources.forEach((resource) => {
        if (hasResourceDemand(resource) && (resource.config.websocketOnly || resource.config.fetch !== null)) names.push(resource.name);
    });
    return names;
};

export { invalidateResourceDemand, releaseResourceDemand, hasResourceDemand, hasResourceLiveDemand, hasResourceSubscribers, listAutoResourceStarts, listReconnectResources, startListenedResources };
export type { AutoResourceStart };
