/* SoAI - Charts feature timestamp index [frontend/assets/ts/features/charts/component/data/timestampIndex.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isFin, TIMESTAMP_EPSILON } from '@features/charts/component/chartComponentStatics.ts';

const findTimestampSlot = (timestamps: Float64Array, dataLength: number, timestamp: number): { index: number; exact: boolean } => {
    if (!isFin(timestamp) || dataLength === 0) return { index: 0, exact: false };
    let low = 0;
    let high = dataLength - 1;
    while (low <= high) {
        const mid = (low + high) >> 1;
        const value = timestamps[mid];
        if (value === undefined || !isFin(value)) {
            high = mid - 1;
            continue;
        }
        const delta = Math.abs(value - timestamp);
        if (delta <= TIMESTAMP_EPSILON) return { index: mid, exact: true };
        if (value < timestamp) low = mid + 1;
        else high = mid - 1;
    }
    return { index: low, exact: false };
};

const findFirstIndexAtOrAfter = (timestamps: Float64Array, dataLength: number, timestamp: number): number => {
    let low = 0;
    let high = dataLength - 1;
    let candidate = -1;
    while (low <= high) {
        const mid = (low + high) >> 1;
        const value = timestamps[mid];
        if (value !== undefined && value >= timestamp) {
            candidate = mid;
            high = mid - 1;
        } else low = mid + 1;
    }
    return candidate;
};

const findLastIndexAtOrBefore = (timestamps: Float64Array, dataLength: number, timestamp: number): number => {
    let low = 0;
    let high = dataLength - 1;
    let candidate = -1;
    while (low <= high) {
        const mid = (low + high) >> 1;
        const value = timestamps[mid];
        if (value !== undefined && value <= timestamp) {
            candidate = mid;
            low = mid + 1;
        } else high = mid - 1;
    }
    return candidate;
};

export { findFirstIndexAtOrAfter, findLastIndexAtOrBefore, findTimestampSlot };
