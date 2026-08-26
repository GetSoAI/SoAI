/* SoAI - Stream resource activation policy [frontend/assets/ts/core/realtime/streammanager/resources/resourceActivationPolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceEntry } from '@core/realtime/streammanager/types.ts';
interface AutoResourceStart {
    name: string;
    autoStart: boolean;
    status: string;
    pending: boolean;
}

const hasResourceSubscribers = (resource: ResourceEntry): boolean => resource.listeners.size > 0 || resource.typedSubscribers.size > 0;

const hasResourceLiveDemand = (resource: ResourceEntry): boolean => resource.config.autoStart || hasResourceSubscribers(resource);

const hasResourceDemand = (resource: ResourceEntry): boolean => hasResourceLiveDemand(resource) || resource.pendingStart !== null;

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

export { hasResourceDemand, hasResourceLiveDemand, hasResourceSubscribers, listAutoResourceStarts, listReconnectResources, startListenedResources };
export type { AutoResourceStart };
