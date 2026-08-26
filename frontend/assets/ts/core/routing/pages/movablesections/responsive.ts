/* SoAI - Shared routing movable grid responsive resolution [frontend/assets/ts/core/routing/pages/movablesections/responsive.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { clampNumber } from '@core/primitives/clampNumber.ts';
import { measureMovableGridSpace, resolveMovableGridCellWidth } from '@core/routing/pages/movablesections/grid.ts';
import type { MovableGridMetrics, MovableGridPresentation, MovableGridSettings, MovableGridSpace } from '@core/routing/pages/movablesections/types.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const validateMovableGridSettings = (settings: MovableGridSettings): void => {
    if (!Number.isInteger(settings.columns) || settings.columns < 1) {
        throw new TypeError('Movable grid columns must be a positive integer');
    }
    if (!isFiniteNumber(settings.baseCellHeight) || settings.baseCellHeight <= 0 || !isFiniteNumber(settings.dragThreshold) || settings.dragThreshold < 0 || !isFiniteNumber(settings.dragScale) || settings.dragScale <= 0) {
        throw new TypeError('Movable grid dimensions and drag settings must be finite and valid');
    }
    if (settings.responsive.type === 'content-scale') {
        if (!isFiniteNumber(settings.responsive.referenceCellWidth) || settings.responsive.referenceCellWidth <= 0) {
            throw new TypeError('Movable grid reference cell width must be a positive finite number');
        }
        if (!isFiniteNumber(settings.responsive.minimumContentScale) || settings.responsive.minimumContentScale <= 0 || settings.responsive.minimumContentScale > 1) {
            throw new TypeError('Movable grid minimum content scale must be greater than zero and at most one');
        }
        return;
    }
    let previousWidth = Number.NEGATIVE_INFINITY;
    for (const breakpoint of settings.responsive.breakpoints) {
        if (!isFiniteNumber(breakpoint.maxWidth) || breakpoint.maxWidth <= previousWidth || !Number.isInteger(breakpoint.columns) || breakpoint.columns < 1 || breakpoint.columns > settings.columns) {
            throw new TypeError('Movable grid breakpoints must be ordered with valid widths and columns');
        }
        previousWidth = breakpoint.maxWidth;
    }
};

const computeMovableBreakpointColumns = (width: number, settings: MovableGridSettings): number => {
    if (settings.responsive.type !== 'breakpoints') {
        throw new TypeError('Movable breakpoint columns require a breakpoint responsive policy');
    }
    for (const breakpoint of settings.responsive.breakpoints) {
        if (width <= breakpoint.maxWidth) {
            return breakpoint.columns;
        }
    }
    return settings.columns;
};

const resolveContentScaleColumns = (space: MovableGridSpace, settings: MovableGridSettings): number => {
    if (settings.responsive.type !== 'content-scale') {
        throw new TypeError('Movable content scale columns require a content-scale responsive policy');
    }
    const minimumCellWidth = settings.responsive.referenceCellWidth * settings.responsive.minimumContentScale;
    for (let columns = settings.columns; columns >= 2; columns -= 1) {
        if (resolveMovableGridCellWidth(space, columns) >= minimumCellWidth) {
            return columns;
        }
    }
    return 1;
};

const resolveMetricsForColumns = (space: MovableGridSpace, settings: MovableGridSettings, columns: number): MovableGridMetrics | null => {
    const cellWidth = resolveMovableGridCellWidth(space, columns);
    if (!isFiniteNumber(cellWidth) || cellWidth <= 0) {
        return null;
    }
    let contentScale = 1;
    let cellHeight = settings.baseCellHeight;
    if (settings.responsive.type === 'content-scale' && columns > 1) {
        const widthRatio = cellWidth / settings.responsive.referenceCellWidth;
        contentScale = clampNumber(widthRatio, settings.responsive.minimumContentScale, 1);
        cellHeight = settings.baseCellHeight * contentScale;
    }
    return {
        columns,
        paddingLeft: space.paddingLeft,
        paddingRight: space.paddingRight,
        paddingTop: space.paddingTop,
        paddingBottom: space.paddingBottom,
        columnGap: space.columnGap,
        rowGap: space.rowGap,
        cellWidth,
        cellHeight,
        contentScale
    };
};

const resolveMovableGridPresentation = (grid: HTMLElement, settings: MovableGridSettings): MovableGridPresentation | null => {
    const space = measureMovableGridSpace(grid);
    if (space.width <= 0) {
        return null;
    }
    const columns = settings.responsive.type === 'content-scale' ? resolveContentScaleColumns(space, settings) : computeMovableBreakpointColumns(measureLayoutViewport(grid).width, settings);
    const metrics = resolveMetricsForColumns(space, settings, columns);
    if (!metrics) {
        return null;
    }
    return {
        collapsed: settings.responsive.type === 'breakpoints' && columns === 1,
        metrics
    };
};

const resolveMovableGridMetricsForColumns = (grid: HTMLElement, settings: MovableGridSettings, columns: number): MovableGridMetrics | null => {
    return resolveMetricsForColumns(measureMovableGridSpace(grid), settings, columns);
};

const createInitialMovableGridPresentation = (settings: MovableGridSettings): MovableGridPresentation => ({
    collapsed: false,
    metrics: {
        columns: settings.columns,
        paddingLeft: 0,
        paddingRight: 0,
        paddingTop: 0,
        paddingBottom: 0,
        columnGap: 0,
        rowGap: 0,
        cellWidth: settings.responsive.type === 'content-scale' ? settings.responsive.referenceCellWidth : 0,
        cellHeight: settings.baseCellHeight,
        contentScale: 1
    }
});

export { createInitialMovableGridPresentation, resolveMovableGridMetricsForColumns, resolveMovableGridPresentation, validateMovableGridSettings };
