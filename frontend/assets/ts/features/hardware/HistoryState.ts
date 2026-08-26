/* SoAI - Hardware feature history state [frontend/assets/ts/features/hardware/HistoryState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface HistoryLineEntry {
    timestamp: number;
    value?: number | undefined;
    open?: number | undefined;
    high?: number | undefined;
    low?: number | undefined;
    close?: number | undefined;
}

interface HistoryMetadataEntry {
    aggregation?: string | undefined;
    intervalMs: number;
    monitoringIntervalMs?: number | undefined;
    maxPoints?: number | undefined;
    effectivePoints?: number | undefined;
    points?: number | undefined;
    requestedPoints?: number | undefined;
}

interface HistoryCandleEntry {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
    value?: number | undefined;
    mode?: string | undefined;
    sourceMode?: string | undefined;
}

type HistoryCandleBucketEntry = HistoryCandleEntry & {
    count: number;
};

interface HistorySnapshot {
    lineData: HistoryLineEntry[];
    lineMetadata: HistoryMetadataEntry | null;
    candleData: HistoryCandleEntry[];
    candleMetadata: HistoryMetadataEntry | null;
    candleBuckets: Map<number, HistoryCandleBucketEntry>;
    lineHistoryExhausted?: boolean | undefined;
    candlestickHistoryExhausted?: boolean | undefined;
    lastResolvedCandlestickIntervalSec?: number | undefined;
}

interface HistorySource {
    historyData: HistoryLineEntry[];
    historyMetadata: HistoryMetadataEntry | null;
    candlestickData: HistoryCandleEntry[];
    candlestickMetadata: HistoryMetadataEntry | null;
    candlestickBuckets: Map<number, HistoryCandleBucketEntry>;
    lineHistoryExhausted: boolean;
    candlestickHistoryExhausted: boolean;
    lastResolvedCandlestickIntervalMs: number | undefined;
}

const cloneLineSeries = (entries: readonly HistoryLineEntry[]): HistoryLineEntry[] => entries.map((entry) => ({ ...entry }));

const cloneCandleSeries = (entries: readonly HistoryCandleEntry[]): HistoryCandleEntry[] => entries.map((entry) => ({ ...entry }));

const cloneMetadata = (metadata: HistoryMetadataEntry | null): HistoryMetadataEntry | null => (metadata ? { ...metadata } : null);

const cloneBuckets = (buckets: ReadonlyMap<number, HistoryCandleBucketEntry>): Map<number, HistoryCandleBucketEntry> => {
    const cloned = new Map<number, HistoryCandleBucketEntry>();
    for (const [key, value] of buckets.entries()) {
        cloned.set(key, { ...value });
    }
    return cloned;
};

class HistoryStateManager {
    snapshot(source: HistorySource | null): HistorySnapshot | null {
        if (!source) return null;
        return {
            lineData: cloneLineSeries(source.historyData),
            lineMetadata: cloneMetadata(source.historyMetadata),
            candleData: cloneCandleSeries(source.candlestickData),
            candleMetadata: cloneMetadata(source.candlestickMetadata),
            candleBuckets: cloneBuckets(source.candlestickBuckets),
            lineHistoryExhausted: source.lineHistoryExhausted,
            candlestickHistoryExhausted: source.candlestickHistoryExhausted,
            lastResolvedCandlestickIntervalSec: Number.isFinite(source.lastResolvedCandlestickIntervalMs) ? source.lastResolvedCandlestickIntervalMs : undefined
        };
    }

    restore(target: HistorySource | null, snapshot: HistorySnapshot | null): void {
        if (!target || !snapshot) return;
        target.historyData = cloneLineSeries(snapshot.lineData);
        target.historyMetadata = cloneMetadata(snapshot.lineMetadata);
        target.candlestickData = cloneCandleSeries(snapshot.candleData);
        target.candlestickMetadata = cloneMetadata(snapshot.candleMetadata);
        target.candlestickBuckets = cloneBuckets(snapshot.candleBuckets);
        if (snapshot.lineHistoryExhausted !== undefined) target.lineHistoryExhausted = snapshot.lineHistoryExhausted;
        if (snapshot.candlestickHistoryExhausted !== undefined) target.candlestickHistoryExhausted = snapshot.candlestickHistoryExhausted;
        if (Number.isFinite(snapshot.lastResolvedCandlestickIntervalSec)) target.lastResolvedCandlestickIntervalMs = snapshot.lastResolvedCandlestickIntervalSec;
    }
}

export { HistoryStateManager };
export type { HistorySnapshot, HistorySource };
