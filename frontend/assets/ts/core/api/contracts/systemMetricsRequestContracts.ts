/* SoAI - Frontend system metrics request boundary contracts [frontend/assets/ts/core/api/contracts/systemMetricsRequestContracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonObject } from '@core/types/jsonValues.ts';

interface SystemMetricsHistoryRequest {
    metricKey: string;
    startTsMs: number;
    endTsMs: number;
    points: number;
    intervalMs?: number | undefined;
    aggregation: string;
}

const serializeSystemMetricsHistoryRequest = (request: SystemMetricsHistoryRequest): JsonObject => {
    const serialized: JsonObject = {
        'metric_key': request.metricKey,
        'start_ts_ms': request.startTsMs,
        'end_ts_ms': request.endTsMs,
        points: request.points,
        aggregation: request.aggregation
    };
    if (request.intervalMs !== undefined) serialized['interval_ms'] = request.intervalMs;
    return serialized;
};

export { serializeSystemMetricsHistoryRequest };
export type { SystemMetricsHistoryRequest };
