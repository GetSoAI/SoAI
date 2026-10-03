/* SoAI - Chronological chart value append [frontend/assets/ts/features/charts/historyValueAppend.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type HistoryValuePoint = { timestamp: number; value?: number | undefined; sampleCount?: number | undefined };
type HistoryValueAppendResult = 'ignored' | 'updated' | 'appended';

const appendHistoryValue = (points: HistoryValuePoint[], timestamp: number, value: number, intervalMs: number, aggregation: string): HistoryValueAppendResult => {
    if (aggregation !== 'avg' && aggregation !== 'min' && aggregation !== 'max' && aggregation !== 'count' && aggregation !== 'delta') throw new TypeError(`Unsupported value history aggregation: ${aggregation}`);
    if (!Number.isFinite(timestamp) || !Number.isFinite(value) || !Number.isSafeInteger(intervalMs) || intervalMs <= 0) return 'ignored';
    const bucketTimestamp = Math.floor(timestamp / intervalMs) * intervalMs;
    const last = points[points.length - 1];
    if (last && bucketTimestamp < last.timestamp) return 'ignored';
    if (last && bucketTimestamp === last.timestamp) {
        const count = last.sampleCount;
        const previousValue = last.value;
        if (!Number.isSafeInteger(count) || count === undefined || count < 1 || previousValue === undefined || !Number.isFinite(previousValue)) return 'ignored';
        if (aggregation === 'avg') last.value = (previousValue * count + value) / (count + 1);
        else if (aggregation === 'min') last.value = Math.min(previousValue, value);
        else if (aggregation === 'max') last.value = Math.max(previousValue, value);
        else if (aggregation === 'count') last.value = previousValue + 1;
        else last.value = previousValue + value;
        last.sampleCount = count + 1;
        return 'updated';
    }
    const initialValue = aggregation === 'count' ? 1 : value;
    points.push({ timestamp: bucketTimestamp, value: initialValue, sampleCount: 1 });
    return 'appended';
};

export { appendHistoryValue };
export type { HistoryValueAppendResult };
