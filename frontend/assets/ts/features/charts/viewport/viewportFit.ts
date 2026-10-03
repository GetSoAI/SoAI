/* SoAI - Charts feature time viewport fitting [frontend/assets/ts/features/charts/viewport/viewportFit.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fitRange, type TimeViewportState } from '@features/charts/viewport/timeViewport.ts';
import { clampTimeViewport, resolveTailInsetPx, type ViewportBoundsInput } from '@features/charts/viewport/viewportBounds.ts';

type ViewportFit = { mode: 'data' } | { mode: 'duration'; durationMs: number };

const DATA_FIT: Readonly<ViewportFit> = Object.freeze({ mode: 'data' });
const DEFAULT_FIT_BAR_PX = 8;

const resolveFitStartTs = (fit: ViewportFit, input: ViewportBoundsInput): number => {
    const requestedStartTs = fit.mode === 'duration' ? input.newestTs - fit.durationMs : input.oldestLoadedTs;
    return input.newestTs - requestedStartTs >= input.intervalMs ? requestedStartTs : input.newestTs - input.intervalMs * Math.max(1, input.plotWidth / DEFAULT_FIT_BAR_PX);
};

const applyViewportFit = (state: TimeViewportState, fit: ViewportFit, input: ViewportBoundsInput): boolean => {
    const startTs = resolveFitStartTs(fit, input);
    const estimatedMsPerPx = (input.newestTs - startTs) / Math.max(1, input.plotWidth);
    if (!fitRange(state, input.plotWidth, startTs, input.newestTs, resolveTailInsetPx(input.plotWidth, input.intervalMs, estimatedMsPerPx))) return false;
    clampTimeViewport(state, input);
    return true;
};

const alignViewportToNewest = (state: TimeViewportState, input: ViewportBoundsInput): void => {
    state.rightEdgeTs = input.newestTs + resolveTailInsetPx(input.plotWidth, input.intervalMs, state.msPerPx) * state.msPerPx;
    clampTimeViewport(state, input);
};

const isNewestVisible = (state: TimeViewportState, newestTs: number): boolean => newestTs <= state.rightEdgeTs;

export { alignViewportToNewest, applyViewportFit, DATA_FIT, isNewestVisible };
export type { ViewportFit };
