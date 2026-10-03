/* SoAI - Charts feature geometry [frontend/assets/ts/features/charts/layout/geometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartDimensions, RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import { isUsableViewport, leftEdgeTs, type TimeViewportState } from '@features/charts/viewport/timeViewport.ts';

const createRenderGeometry = (dims: ChartDimensions, time: TimeViewportState, intervalMs: number): RenderGeometry | null => {
    if (dims.chartWidth <= 0 || !isUsableViewport(time)) return null;
    const frame = { plotLeft: dims.left, plotWidth: dims.chartWidth, rightEdgeTs: time.rightEdgeTs, msPerPx: time.msPerPx };
    const startTs = leftEdgeTs(frame);
    return { ...frame, startTs, endTs: time.rightEdgeTs, span: time.rightEdgeTs - startTs, slotWidth: intervalMs / time.msPerPx };
};

export { createRenderGeometry };
