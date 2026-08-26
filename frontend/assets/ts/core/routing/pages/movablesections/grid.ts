/* SoAI - Shared routing movable grid geometry and rendering [frontend/assets/ts/core/routing/pages/movablesections/grid.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getComputedStyleStrict } from '@core/environment/public.ts';
import { measureElementLayoutDimensions } from '@core/layout/elementGeometry.ts';
import type { GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import type { MovableGridMetrics, MovableGridSpace, MovableSectionId } from '@core/routing/pages/movablesections/types.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';

const GRID_METRIC_TOLERANCE_PX = 0.01;

const applyMovableGridLayout = <TSectionId extends MovableSectionId>(
    gridElement: HTMLElement,
    layout: Map<TSectionId, GridPosition>,
    options: {
        sectionIdAttribute: string;
        collapsedClassName: string;
        updateStyle: (element: Element, property: string, value: string) => void;
        applyGridPosition: (element: Element, position: GridPosition) => void;
    }
): void => {
    const collapsed = gridElement.classList.contains(options.collapsedClassName);
    for (const [id, position] of layout.entries()) {
        const element = dom.resolve(`[${options.sectionIdAttribute}="${CSS.escape(id)}"]`, gridElement);
        if (!element) {
            continue;
        }
        if (collapsed) {
            options.updateStyle(element, 'gridColumn', '');
            options.updateStyle(element, 'gridRow', '');
            continue;
        }
        options.applyGridPosition(element, position);
    }
};

const toggleMovableGridMode = (
    gridElement: HTMLElement,
    collapsed: boolean,
    options: {
        sectionSelector: string;
        collapsedClassName: string;
        updateStyle: (element: Element, property: string, value: string) => void;
    }
): void => {
    gridElement.classList.toggle(options.collapsedClassName, collapsed);
    const sections = dom.resolveAll(options.sectionSelector, gridElement);
    Array.from(sections).forEach((section: Element): void => {
        if (section instanceof HTMLElement) {
            section.classList.toggle(options.collapsedClassName, collapsed);
            if (collapsed) {
                options.updateStyle(section, 'gridColumn', '');
                options.updateStyle(section, 'gridRow', '');
            }
        }
    });
};

const measureMovableGridSpace = (grid: HTMLElement): MovableGridSpace => {
    const styles = getComputedStyleStrict(grid);
    return {
        width: measureElementLayoutDimensions(grid).width,
        paddingLeft: readMovableGridStyleNumber(styles, 'padding-left'),
        paddingRight: readMovableGridStyleNumber(styles, 'padding-right'),
        paddingTop: readMovableGridStyleNumber(styles, 'padding-top'),
        paddingBottom: readMovableGridStyleNumber(styles, 'padding-bottom'),
        columnGap: readMovableGridStyleNumber(styles, 'column-gap'),
        rowGap: readMovableGridStyleNumber(styles, 'row-gap')
    };
};

const resolveMovableGridCellWidth = (space: MovableGridSpace, columns: number): number => {
    if (!Number.isInteger(columns) || columns < 1) {
        throw new TypeError('Movable grid column count must be a positive integer');
    }
    const usableWidth = Math.max(0, space.width - space.paddingLeft - space.paddingRight - space.columnGap * Math.max(columns - 1, 0));
    return usableWidth / columns;
};

const applyMovableGridMetrics = (grid: HTMLElement, metrics: MovableGridMetrics, dependencies: { updateStyles: (element: Element, styles: Record<string, string>) => void }): void => {
    dependencies.updateStyles(grid, {
        '--grid-columns': String(metrics.columns),
        '--cell-height': `${metrics.cellHeight}px`,
        '--movable-section-content-scale': String(metrics.contentScale),
        '--movable-section-content-scale-inverse': String(1 / metrics.contentScale)
    });
    grid.setAttribute('data-columns', String(metrics.columns));
};

const movableGridMetricsEqual = (left: MovableGridMetrics | null, right: MovableGridMetrics): boolean => {
    if (!left || left.columns !== right.columns) {
        return false;
    }
    return Math.abs(left.paddingLeft - right.paddingLeft) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.paddingRight - right.paddingRight) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.paddingTop - right.paddingTop) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.paddingBottom - right.paddingBottom) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.columnGap - right.columnGap) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.rowGap - right.rowGap) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.cellWidth - right.cellWidth) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.cellHeight - right.cellHeight) <= GRID_METRIC_TOLERANCE_PX && Math.abs(left.contentScale - right.contentScale) <= GRID_METRIC_TOLERANCE_PX;
};

const readMovableGridStyleNumber = (styles: CSSStyleDeclaration, property: string): number => {
    const value = Number.parseFloat(styles.getPropertyValue(property));
    return isFiniteNumber(value) ? value : 0;
};

export { applyMovableGridLayout, applyMovableGridMetrics, measureMovableGridSpace, movableGridMetricsEqual, resolveMovableGridCellWidth, toggleMovableGridMode };
