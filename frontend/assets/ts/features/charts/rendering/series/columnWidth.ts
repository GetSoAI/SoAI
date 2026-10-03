/* SoAI - Time aligned chart column sizing [frontend/assets/ts/features/charts/rendering/series/columnWidth.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RenderGeometry } from '@features/charts/rendering/renderingModels.ts';
import type { VisiblePointsWithBuffers } from '@features/charts/renderingTypes.ts';

const resolveColumnWidthFromSpacing = (slotWidth: number, localSpacing: number, maximumWidth: number, fraction: number): number => Math.max(1, Math.min(maximumWidth, slotWidth * fraction, localSpacing * 0.85));

const resolveVisibleColumnWidth = (geometry: RenderGeometry, points: VisiblePointsWithBuffers, index: number, maximumWidth: number, fraction: number): number => {
    const xCoordinate = points.x[index];
    if (xCoordinate === undefined) return 1;
    let localSpacing = Infinity;
    for (const neighbor of [index - 1, index + 1]) {
        if (neighbor < 0 || neighbor >= points.length || !points.valid[neighbor]) continue;
        const neighborX = points.x[neighbor];
        if (neighborX !== undefined) localSpacing = Math.min(localSpacing, Math.abs(neighborX - xCoordinate));
    }
    return resolveColumnWidthFromSpacing(geometry.slotWidth, localSpacing, maximumWidth, fraction);
};

export { resolveVisibleColumnWidth };
