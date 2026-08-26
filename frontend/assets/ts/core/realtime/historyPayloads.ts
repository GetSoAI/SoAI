/* SoAI - Shared realtime history payloads [frontend/assets/ts/core/realtime/historyPayloads.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { MetricsHistoryPayload } from '@core/realtime/metricsHistoryContracts.ts';

interface TimestampValueHistoryPayload {
    timestamps: number[];
    values: number[];
    intervalMs: number;
}

const readTimestampValueHistoryPayload = (response: MetricsHistoryPayload): TimestampValueHistoryPayload => {
    const timestamps = response.timestampsMs;
    const values = response.values;
    if (timestamps.length !== values.length) throw new TypeError('Metrics history timestamps and values must have matching lengths');
    return {
        timestamps,
        values: values.map((value) => value ?? Number.NaN),
        intervalMs: response.intervalMs
    };
};

export { readTimestampValueHistoryPayload };
export type { TimestampValueHistoryPayload };
