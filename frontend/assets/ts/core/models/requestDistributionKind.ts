/* SoAI - Shared models request distribution kind [frontend/assets/ts/core/models/requestDistributionKind.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type RequestDistributionChartKind = 'pie3d' | 'bars3d' | 'spheres3d' | 'coinstack3d';

const REQUEST_DISTRIBUTION_CHART_KINDS: readonly RequestDistributionChartKind[] = ['pie3d', 'bars3d', 'spheres3d', 'coinstack3d'];

const REQUEST_DISTRIBUTION_MAX_VISIBLE_ENTRIES = 20;

const REQUEST_DISTRIBUTION_MINIMUM_ENTRY_SIZES: Readonly<Record<RequestDistributionChartKind, { width: number; height: number }>> = Object.freeze({
    pie3d: { width: 12, height: 12 },
    bars3d: { width: 14, height: 1 },
    spheres3d: { width: 32, height: 32 },
    coinstack3d: { width: 1, height: 8 }
});

const getRequestDistributionVisibleEntryCapacity = (kind: RequestDistributionChartKind, width: number, height: number): number => {
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
        return 1;
    }
    const minimumSize = REQUEST_DISTRIBUTION_MINIMUM_ENTRY_SIZES[kind];
    let capacity: number;
    if (kind === 'pie3d') {
        capacity = Math.floor(Math.min(width, height) / minimumSize.width);
    } else if (kind === 'bars3d') {
        capacity = Math.floor(width / minimumSize.width);
    } else if (kind === 'spheres3d') {
        capacity = Math.floor(width / minimumSize.width) * Math.floor(height / minimumSize.height);
    } else {
        capacity = Math.floor(height / minimumSize.height);
    }
    return Math.max(1, Math.min(REQUEST_DISTRIBUTION_MAX_VISIBLE_ENTRIES, capacity));
};

export { getRequestDistributionVisibleEntryCapacity, REQUEST_DISTRIBUTION_CHART_KINDS, REQUEST_DISTRIBUTION_MAX_VISIBLE_ENTRIES };
export type { RequestDistributionChartKind };
