/* SoAI - Charts feature older-history ghost series [frontend/assets/ts/features/charts/rendering/preview/historyGhost.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { OhlcData } from '@features/charts/component/chartComponentTypes.ts';

interface HistoryGhostSource {
    timestamps: Float64Array;
    dataLength: number;
    anchorIndex: number;
    values: Float64Array;
    ohlc: OhlcData | null;
    intervalMs: number;
    minStepMs: number;
    untilTs: number;
}

interface HistoryGhostPoint {
    timestamp: number;
    open: number;
    high: number;
    low: number;
    close: number;
}

interface ReferenceSample {
    open: number;
    high: number;
    low: number;
    close: number;
}

const REFERENCE_WINDOW = 48;
const DAMPING_FLOOR = 0.35;
const MEAN_REVERSION = 0.04;
const MAX_GHOST_POINTS = 4096;

const collectReference = (source: HistoryGhostSource): ReferenceSample[] => {
    const samples: ReferenceSample[] = [];
    for (let index = source.anchorIndex; index < source.dataLength && samples.length < REFERENCE_WINDOW; index++) {
        const close = source.ohlc ? source.ohlc.close[index] : source.values[index];
        const open = source.ohlc ? source.ohlc.open[index] : close;
        const high = source.ohlc ? source.ohlc.high[index] : close;
        const low = source.ohlc ? source.ohlc.low[index] : close;
        if (close === undefined || open === undefined || high === undefined || low === undefined) break;
        if (Number.isFinite(open) && Number.isFinite(high) && Number.isFinite(low) && Number.isFinite(close)) samples.push({ open, high, low, close });
    }
    return samples;
};

const reflectIndex = (step: number, length: number): number => {
    const period = length - 1;
    if (period <= 0) return 0;
    const offset = step % (2 * period);
    return offset <= period ? offset : 2 * period - offset;
};

const damping = (step: number, length: number): number => DAMPING_FLOOR + (1 - DAMPING_FLOOR) * Math.exp(-step / Math.max(1, length));

const buildHistoryGhost = (source: HistoryGhostSource): HistoryGhostPoint[] => {
    const anchorTs = source.timestamps[source.anchorIndex];
    if (anchorTs === undefined || !Number.isFinite(anchorTs) || !(source.intervalMs > 0) || anchorTs <= source.untilTs) return [];
    const reference = collectReference(source);
    const first = reference[0];
    if (!first) return [];
    const mean = reference.reduce((sum, sample) => sum + sample.close, 0) / reference.length;
    const stepMs = source.intervalMs * Math.max(1, Math.ceil(source.minStepMs / source.intervalMs));
    const ghost: HistoryGhostPoint[] = source.ohlc ? [] : [{ timestamp: anchorTs, open: first.close, high: first.close, low: first.close, close: first.close }];
    let edge = source.ohlc ? first.open : first.close;
    for (let step = 1; step <= MAX_GHOST_POINTS; step++) {
        const timestamp = anchorTs - step * stepMs;
        const weight = damping(step, reference.length);
        const current = reference[reflectIndex(step, reference.length)] ?? first;
        const previous = reference[reflectIndex(step - 1, reference.length)] ?? first;
        const drift = (mean - edge) * MEAN_REVERSION;
        if (source.ohlc) {
            const close = edge;
            const open = close + weight * (current.open - current.close) + drift;
            const high = Math.max(open, close) + weight * (current.high - Math.max(current.open, current.close));
            const low = Math.min(open, close) - weight * (Math.min(current.open, current.close) - current.low);
            ghost.push({ timestamp, open, high, low, close });
            edge = open;
        } else {
            edge += weight * (current.close - previous.close) + drift;
            ghost.push({ timestamp, open: edge, high: edge, low: edge, close: edge });
        }
        if (timestamp < source.untilTs) break;
    }
    return ghost;
};

export { buildHistoryGhost };
export type { HistoryGhostPoint, HistoryGhostSource };
