/* SoAI - Indicators feature mappers [frontend/assets/ts/features/indicators/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { isArray, isBoolean, isNullOrUndefined, isNumber, isObject } from '@core/typeGuards.ts';
import type { BundleInfo, BundleResource, DiagnosticsSnapshot } from '@features/indicators/contracts.ts';

const normalizeBundleResources = (value: JsonValue | BundleResource[] | null | undefined): BundleResource[] | undefined => {
    if (!isArray(value)) {
        return undefined;
    }

    const resources: BundleResource[] = [];
    for (const entry of value) {
        if (!entry || !isObject(entry)) {
            continue;
        }

        const pendingValue = entry['pending'];
        const statusValue = entry['status'];
        resources.push({
            pending: isBoolean(pendingValue) ? pendingValue : undefined,
            status: typeof statusValue === 'string' ? statusValue : undefined
        });
    }

    return resources;
};

const normalizeBundles = (value: JsonValue | BundleInfo[] | null | undefined): BundleInfo[] => {
    if (!isArray(value)) {
        return [];
    }

    const bundles: BundleInfo[] = [];
    for (const entry of value) {
        if (!entry || !isObject(entry)) {
            continue;
        }

        const nameValue = entry['name'];
        const resourcesValue = entry['resources'];
        bundles.push({
            name: typeof nameValue === 'string' ? nameValue : undefined,
            resources: normalizeBundleResources(resourcesValue)
        });
    }

    return bundles;
};

const normalizeDiagnosticsSnapshot = (value: JsonValue | DiagnosticsSnapshot | null | undefined): { bundles: BundleInfo[]; queueDepth: number | null } => {
    if (!isObject(value)) {
        return { bundles: [], queueDepth: null };
    }

    const bundleValue = value['bundles'];
    const queueDepthValue = value['queueDepth'];
    if (isNullOrUndefined(queueDepthValue)) {
        return { bundles: normalizeBundles(bundleValue), queueDepth: null };
    }

    if (!isNumber(queueDepthValue) || queueDepthValue < 0 || Number.isNaN(queueDepthValue)) {
        return { bundles: normalizeBundles(bundleValue), queueDepth: null };
    }

    return {
        queueDepth: queueDepthValue,
        bundles: normalizeBundles(bundleValue)
    };
};

const countPendingBundleResources = (resources: BundleResource[] | undefined): number => {
    if (!isArray(resources)) {
        return 0;
    }

    return resources.filter((entry) => entry && (Boolean(entry.pending) || entry.status === 'initializing' || entry.status === 'idle')).length;
};

export { countPendingBundleResources, normalizeBundles, normalizeBundleResources, normalizeDiagnosticsSnapshot };
