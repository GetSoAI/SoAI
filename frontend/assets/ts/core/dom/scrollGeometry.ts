/* SoAI - Pure shared scroll geometry decisions [frontend/assets/ts/core/dom/scrollGeometry.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

type ScrollDirection = 'backward' | 'forward' | 'stationary';

interface ScrollEdgeInput {
    position: number;
    extent: number;
    viewport: number;
    tolerance: number;
}

interface ScrollEdgeMeasurement {
    atStart: boolean;
    atEnd: boolean;
    startDistance: number;
    endDistance: number;
}

const finiteNonNegative = (value: number): number => (Number.isFinite(value) ? Math.max(0, value) : 0);

const normalizeScrollPosition = (position: number, maximum: number): number => {
    const normalizedMaximum = finiteNonNegative(maximum);
    if (!Number.isFinite(position)) return 0;
    return Math.min(normalizedMaximum, Math.max(0, position));
};

const resolveScrollDirection = (previousPosition: number, currentPosition: number): ScrollDirection => {
    const previous = finiteNonNegative(previousPosition);
    const current = finiteNonNegative(currentPosition);
    if (current > previous) return 'forward';
    if (current < previous) return 'backward';
    return 'stationary';
};

const measureScrollEdges = ({ position, extent, viewport, tolerance }: ScrollEdgeInput): ScrollEdgeMeasurement => {
    const normalizedExtent = finiteNonNegative(extent);
    const normalizedViewport = finiteNonNegative(viewport);
    const maximum = Math.max(0, normalizedExtent - normalizedViewport);
    const normalizedPosition = normalizeScrollPosition(position, maximum);
    const normalizedTolerance = finiteNonNegative(tolerance);
    const startDistance = normalizedPosition;
    const endDistance = Math.max(0, maximum - normalizedPosition);
    return {
        atStart: startDistance <= normalizedTolerance,
        atEnd: endDistance <= normalizedTolerance,
        startDistance,
        endDistance
    };
};

export { measureScrollEdges, normalizeScrollPosition, resolveScrollDirection };
export type { ScrollDirection, ScrollEdgeInput, ScrollEdgeMeasurement };
