/* SoAI - Shared realtime build diagnostics snapshot [frontend/assets/ts/core/realtime/streammanager/diagnostics/buildDiagnosticsSnapshot.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BundleDefinition, DiagnosticsSnapshot, ResourceEntry, ResourceStatus } from '@core/realtime/streammanager/types.ts';

const buildDiagnosticsSnapshot = (options: { resources: Map<string, ResourceEntry>; bundles: Map<string, BundleDefinition>; ready: boolean }): DiagnosticsSnapshot => {
    let queueDepth = 0;
    const resourcesSnapshot: Array<{
        name: string;
        status: ResourceStatus;
        pending: boolean;
        updatedAt: number | null;
        autoStart: boolean;
    }> = [];

    options.resources.forEach((resource) => {
        if (resource.reconciler.reconciling || resource.status !== 'ready') {
            queueDepth += 1;
        }
        resourcesSnapshot.push({
            name: resource.name,
            status: resource.status,
            pending: resource.reconciler.reconciling,
            updatedAt: resource.updatedAt,
            autoStart: !!resource.config.autoStart
        });
    });

    const bundlesSnapshot: Array<{
        name: string;
        ready: boolean;
        resources: Array<{ alias: string; name: string; status: ResourceStatus; pending: boolean }>;
    }> = [];

    options.bundles.forEach((bundle) => {
        const list: Array<{ alias: string; name: string; status: ResourceStatus; pending: boolean }> = [];
        Object.entries(bundle.resources).forEach(([alias, resourceName]) => {
            const resource = options.resources.get(resourceName) || null;
            list.push({
                alias,
                name: resourceName,
                status: resource?.status ?? 'unavailable',
                pending: resource?.reconciler.reconciling ?? false
            });
        });
        bundlesSnapshot.push({
            name: bundle.name,
            ready: list.every((entry) => entry.status === 'ready' && !entry.pending),
            resources: list
        });
    });

    return { queueDepth, resources: resourcesSnapshot, bundles: bundlesSnapshot, ready: options.ready };
};

export { buildDiagnosticsSnapshot };
