/* SoAI - Shared UI grid animator [frontend/assets/ts/core/ui/GridAnimator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import { findCompactedPosition, reserveCells } from '@core/ui/gridCollision.ts';

interface GridPosition {
    x: number;
    y: number;
    width: number;
    height: number;
}

interface PositionSnapshot {
    element: HTMLElement;
    gridX: number;
    gridY: number;
    gridWidth: number;
    gridHeight: number;
}

interface GridMetrics {
    cellWidth: number;
    cellHeight: number;
    columnGap: number;
    rowGap: number;
}

interface SpanConfig {
    width: number;
    height: number;
}

interface TargetPosition {
    x: number;
    y: number;
}

interface GridAnimatorOptions {
    gridElement: HTMLElement;
    getSections: (container: HTMLElement) => HTMLElement[];
    getSectionId: (section: HTMLElement) => string | null;
}

class GridAnimator {
    getSections: ((container: HTMLElement) => HTMLElement[]) | null;
    getSectionId: ((section: HTMLElement) => string | null) | null;
    gridElement: HTMLElement | null;
    positionSnapshot: Map<string, PositionSnapshot>;
    displacedElements: Set<HTMLElement>;

    constructor({ gridElement, getSections, getSectionId }: GridAnimatorOptions) {
        this.gridElement = gridElement;
        this.getSections = getSections;
        this.getSectionId = getSectionId;
        this.positionSnapshot = new Map();
        this.displacedElements = new Set();
    }

    capturePositions(excludeId: string | undefined, currentPositions: Map<string, GridPosition>): Map<string, PositionSnapshot> {
        const snapshot = new Map<string, PositionSnapshot>();
        const gridElement = this.gridElement;
        const getSections = this.getSections;
        const getSectionId = this.getSectionId;
        if (!gridElement || !getSections || !getSectionId) {
            this.positionSnapshot = snapshot;
            return snapshot;
        }
        const sections = getSections(gridElement);
        sections.forEach((section) => {
            const id = getSectionId(section);
            if (!id) {
                return;
            }
            if (id === excludeId) {
                return;
            }
            const position = currentPositions.get(id);
            if (!position) {
                return;
            }
            snapshot.set(id, {
                element: section,
                gridX: position.x,
                gridY: position.y,
                gridWidth: position.width,
                gridHeight: position.height
            });
        });
        this.positionSnapshot = snapshot;
        return snapshot;
    }

    computePreviewLayout(currentPositions: Map<string, GridPosition>, draggedId: string, targetPosition: TargetPosition, span: SpanConfig, columns: number): Map<string, GridPosition> {
        const preview = new Map<string, GridPosition>();
        preview.set(draggedId, {
            x: targetPosition.x,
            y: targetPosition.y,
            width: span.width,
            height: span.height
        });
        for (const [id, position] of currentPositions.entries()) {
            if (id !== draggedId) {
                preview.set(id, { ...position });
            }
        }
        return this.resolveCollisions(preview, draggedId, columns);
    }

    resolveCollisions(layout: Map<string, GridPosition>, priorityId: string, columns: number): Map<string, GridPosition> {
        const resolved = new Map<string, GridPosition>();
        const occupied = new Set<string>();
        const priorityPosition = layout.get(priorityId);
        if (priorityPosition) {
            const priorityX = clampNumber(priorityPosition.x, 0, columns - priorityPosition.width);
            resolved.set(priorityId, { ...priorityPosition, x: priorityX, y: Math.max(0, priorityPosition.y) });
            reserveCells(occupied, priorityX, Math.max(0, priorityPosition.y), priorityPosition.width, priorityPosition.height);
        }

        const sorted = Array.from(layout.entries())
            .filter(([id]) => id !== priorityId)
            .sort(([firstId, firstPosition], [secondId, secondPosition]) => {
                if (firstPosition.y !== secondPosition.y) {
                    return firstPosition.y - secondPosition.y;
                }
                if (firstPosition.x !== secondPosition.x) {
                    return firstPosition.x - secondPosition.x;
                }
                return firstId.localeCompare(secondId, 'en');
            });

        for (const [id, position] of sorted) {
            const { x: xCoordinate, y: yCoordinate } = findCompactedPosition(occupied, position.x, position.y, position.width, position.height, columns);
            resolved.set(id, { x: xCoordinate, y: yCoordinate, width: position.width, height: position.height });
            reserveCells(occupied, xCoordinate, yCoordinate, position.width, position.height);
        }
        return this.removeEmptyRows(resolved);
    }

    removeEmptyRows(layout: Map<string, GridPosition>): Map<string, GridPosition> {
        const occupiedRows = new Set<number>();
        for (const position of layout.values()) {
            for (let row = position.y; row < position.y + position.height; row += 1) {
                occupiedRows.add(row);
            }
        }
        const compacted = new Map<string, GridPosition>();
        for (const [id, position] of layout.entries()) {
            let emptyRowsAbove = 0;
            for (let row = 0; row < position.y; row += 1) {
                if (!occupiedRows.has(row)) {
                    emptyRowsAbove += 1;
                }
            }
            compacted.set(id, { ...position, y: position.y - emptyRowsAbove });
        }
        return compacted;
    }

    animateToPreview(previewLayout: Map<string, GridPosition>, metrics: GridMetrics | null | undefined): void {
        if (!metrics) {
            return;
        }
        const cellWidth = metrics.cellWidth + metrics.columnGap;
        const cellHeight = metrics.cellHeight + metrics.rowGap;
        const snapshot = this.positionSnapshot;

        for (const [id, firstPosition] of snapshot.entries()) {
            const newGridPosition = previewLayout.get(id);
            if (!newGridPosition) {
                continue;
            }

            const gridDeltaX = newGridPosition.x - firstPosition.gridX;
            const gridDeltaY = newGridPosition.y - firstPosition.gridY;
            const deltaX = gridDeltaX * cellWidth;
            const deltaY = gridDeltaY * cellHeight;

            if (Math.abs(deltaX) < 1 && Math.abs(deltaY) < 1) {
                this.clearElementDisplacement(firstPosition.element);
                continue;
            }

            this.displaceElement(firstPosition.element, deltaX, deltaY);
        }
    }

    displaceElement(element: HTMLElement, deltaX: number, deltaY: number): void {
        element.classList.add('is-displaced');
        element.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
        this.displacedElements.add(element);
    }

    clearElementDisplacement(element: HTMLElement): void {
        element.style.transform = '';
        element.classList.remove('is-displaced');
        this.displacedElements.delete(element);
    }

    clearAllAnimations(): void {
        for (const element of this.displacedElements) {
            element.style.transform = '';
            element.classList.remove('is-displaced');
        }
        this.displacedElements.clear();
    }

    clearSnapshot(): void {
        this.positionSnapshot.clear();
    }

    destroy(): void {
        this.clearAllAnimations();
        this.positionSnapshot.clear();
        this.gridElement = null;
        this.getSections = null;
        this.getSectionId = null;
    }
}

export { GridAnimator };
