/* SoAI - Shared frontend API types hardware [frontend/assets/ts/core/api/types/hardware.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RequestOptions } from '@core/api/types/request.ts';

interface HardwareHistoryConfig {
    component?: string;
    identifier?: string;
    startTsMs?: number;
    endTsMs?: number;
    points?: number;
    intervalMs?: number;
    aggregation?: string;
    minutes?: number;
    gpuIndex?: number;
    options?: { signal?: AbortSignal };
}

interface KillProcessOptions {
    signal?: number;
    useSudo?: boolean;
}

interface HardwareSnapshotOptions extends RequestOptions {
    components?: readonly string[];
    useCache?: boolean;
}

export type { HardwareHistoryConfig, HardwareSnapshotOptions, KillProcessOptions };
