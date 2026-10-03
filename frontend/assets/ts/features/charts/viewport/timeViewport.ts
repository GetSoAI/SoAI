/* SoAI - Charts feature canonical time viewport [frontend/assets/ts/features/charts/viewport/timeViewport.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface TimeViewportState {
    rightEdgeTs: number;
    msPerPx: number;
    followLive: boolean;
}

interface TimeAxisFrame {
    plotLeft: number;
    plotWidth: number;
    rightEdgeTs: number;
    msPerPx: number;
}

const MIN_CONTENT_INSET_PX = 8;
const MAX_CONTENT_INSET_RATIO = 0.2;
const CONTENT_INSET_BAR_RATIO = 0.55;

const isUsableViewport = (state: TimeViewportState): boolean => Number.isFinite(state.rightEdgeTs) && Number.isFinite(state.msPerPx) && state.msPerPx > 0;

const resolveContentInset = (plotWidth: number, barPx: number): number => Math.min(plotWidth / 2, Math.max(MIN_CONTENT_INSET_PX, Math.min(plotWidth * MAX_CONTENT_INSET_RATIO, Number.isFinite(barPx) ? barPx * CONTENT_INSET_BAR_RATIO : 0)));

const plotRight = (frame: TimeAxisFrame): number => frame.plotLeft + frame.plotWidth;

const timeToX = (frame: TimeAxisFrame, timestamp: number): number => plotRight(frame) - (frame.rightEdgeTs - timestamp) / frame.msPerPx;

const xToTime = (frame: TimeAxisFrame, xCoordinate: number): number => frame.rightEdgeTs - (plotRight(frame) - xCoordinate) * frame.msPerPx;

const leftEdgeTs = (frame: TimeAxisFrame): number => frame.rightEdgeTs - frame.plotWidth * frame.msPerPx;

const panByPixels = (state: TimeViewportState, deltaPx: number): void => {
    state.rightEdgeTs -= deltaPx * state.msPerPx;
};

const fitRange = (state: TimeViewportState, plotWidth: number, startTs: number, endTs: number, tailInsetPx: number): boolean => {
    const usableWidth = plotWidth - tailInsetPx;
    if (!(usableWidth > 0) || !Number.isFinite(startTs) || !Number.isFinite(endTs) || endTs <= startTs) return false;
    state.msPerPx = (endTs - startTs) / usableWidth;
    state.rightEdgeTs = endTs + tailInsetPx * state.msPerPx;
    return true;
};

export { fitRange, isUsableViewport, leftEdgeTs, panByPixels, plotRight, resolveContentInset, timeToX, xToTime };
export type { TimeAxisFrame, TimeViewportState };
