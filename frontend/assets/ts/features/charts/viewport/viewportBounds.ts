/* SoAI - Charts feature time viewport bounds [frontend/assets/ts/features/charts/viewport/viewportBounds.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { resolveContentInset, type TimeViewportState } from '@features/charts/viewport/timeViewport.ts';

interface ViewportBoundsInput {
    plotWidth: number;
    intervalMs: number;
    newestTs: number;
    oldestLoadedTs: number;
    oldestNavigableTs: number | null;
    maxDataPoints: number;
}

const MAX_BAR_PX = 48;
const MIN_VISIBLE_DATA_RATIO = 0.15;
const INTERVAL_SAMPLE_LIMIT = 64;
const FALLBACK_INTERVAL_MS = 1000;

const resolveSeriesIntervalMs = (expectedIntervalMs: number, timestamps: Float64Array, dataLength: number): number => {
    if (Number.isFinite(expectedIntervalMs) && expectedIntervalMs > 0) return expectedIntervalMs;
    const deltas: number[] = [];
    for (let index = dataLength - 1; index > 0 && deltas.length < INTERVAL_SAMPLE_LIMIT; index -= 1) {
        const delta = (timestamps[index] ?? Number.NaN) - (timestamps[index - 1] ?? Number.NaN);
        if (Number.isFinite(delta) && delta > 0) deltas.push(delta);
    }
    deltas.sort((left, right) => left - right);
    return deltas[deltas.length >> 1] ?? FALLBACK_INTERVAL_MS;
};

const resolveTailInsetPx = (plotWidth: number, intervalMs: number, msPerPx: number): number => resolveContentInset(plotWidth, intervalMs / msPerPx);

const clampViewportScale = (msPerPx: number, input: ViewportBoundsInput): number => {
    const minimum = input.intervalMs / MAX_BAR_PX;
    const horizonTs = input.oldestNavigableTs ?? input.newestTs - input.intervalMs * input.maxDataPoints;
    const span = Math.max(input.intervalMs, input.newestTs - horizonTs);
    const maximum = Math.max(minimum, span / Math.max(1, input.plotWidth - resolveContentInset(input.plotWidth, 0) * 2));
    return clampNumber(msPerPx, minimum, maximum);
};

const clampViewportRightEdge = (rightEdgeTs: number, msPerPx: number, input: ViewportBoundsInput): number => {
    const insetPx = resolveTailInsetPx(input.plotWidth, input.intervalMs, msPerPx);
    const maximum = input.newestTs + insetPx * msPerPx;
    const minimum = input.oldestNavigableTs === null ? input.oldestLoadedTs + input.plotWidth * MIN_VISIBLE_DATA_RATIO * msPerPx : input.oldestNavigableTs + (input.plotWidth - insetPx) * msPerPx;
    return minimum > maximum ? maximum : clampNumber(rightEdgeTs, minimum, maximum);
};

const clampTimeViewport = (state: TimeViewportState, input: ViewportBoundsInput): void => {
    state.msPerPx = clampViewportScale(state.msPerPx, input);
    state.rightEdgeTs = clampViewportRightEdge(state.rightEdgeTs, state.msPerPx, input);
};

export { clampTimeViewport, clampViewportRightEdge, clampViewportScale, resolveSeriesIntervalMs, resolveTailInsetPx };
export type { ViewportBoundsInput };
