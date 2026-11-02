/* SoAI - Pane capacity decisions in layout coordinates [frontend/assets/ts/core/pagepanes/capacity.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isCompactLayout } from '@core/layout/compact.ts';
import type { GeometryDimensions } from '@core/layout/elementGeometry.ts';

type PaneCapacity = 1 | 2 | 3;

interface PaneCapacityMeasurement {
    connected: boolean;
    contentWidth: number;
    gap: number;
    paneBorderWidth: number;
    viewport: GeometryDimensions;
}

const resolvePaneCapacity = (measurement: PaneCapacityMeasurement, previous: PaneCapacity | null): PaneCapacity | null => {
    const { connected, contentWidth, gap, paneBorderWidth, viewport } = measurement;
    if (!connected || !Number.isFinite(contentWidth) || contentWidth <= 0 || !Number.isFinite(viewport.width) || !Number.isFinite(viewport.height) || viewport.width <= 0 || viewport.height <= 0) return null;
    if (!Number.isFinite(gap) || gap < 0 || !Number.isFinite(paneBorderWidth) || paneBorderWidth < 0) throw new Error('Pane capacity requires non-negative layout spacing');
    if (isCompactLayout(viewport)) return 1;
    const widthFor = (count: PaneCapacity): number => (contentWidth - gap * (count - 1) - paneBorderWidth * count) / count;
    const thresholdFor = (count: PaneCapacity): number => (previous !== null && count <= previous ? 840 : 864);
    if (viewport.width >= 3440 && widthFor(3) >= thresholdFor(3)) return 3;
    if (widthFor(2) >= thresholdFor(2)) return 2;
    return 1;
};

export { resolvePaneCapacity };
export type { PaneCapacity, PaneCapacityMeasurement };
