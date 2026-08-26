/* SoAI - Shared UI grid collision [frontend/assets/ts/core/ui/gridCollision.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';

interface GridCellPosition {
    x: number;
    y: number;
}

const cellKey = (xCoordinate: number, yCoordinate: number): string => `${xCoordinate}:${yCoordinate}`;

function reserveCells(occupied: Set<string>, xCoordinate: number, yCoordinate: number, width: number, height: number): void {
    for (let row = yCoordinate; row < yCoordinate + height; row++) {
        for (let column = xCoordinate; column < xCoordinate + width; column++) {
            occupied.add(cellKey(column, row));
        }
    }
}

function isCellFree(occupied: Set<string>, xCoordinate: number, yCoordinate: number, width: number, height: number, columns: number): boolean {
    if (xCoordinate < 0 || yCoordinate < 0 || xCoordinate + width > columns) {
        return false;
    }
    for (let row = yCoordinate; row < yCoordinate + height; row++) {
        for (let column = xCoordinate; column < xCoordinate + width; column++) {
            if (occupied.has(cellKey(column, row))) {
                return false;
            }
        }
    }
    return true;
}

function findFreePosition(occupied: Set<string>, startX: number, startY: number, width: number, height: number, columns: number): GridCellPosition {
    if (columns < 1 || width < 1 || height < 1 || width > columns) {
        throw new Error('Invalid grid collision dimensions');
    }
    let xCoordinate = clampNumber(startX, 0, columns - width);
    let yCoordinate = Math.max(0, startY);
    while (!isCellFree(occupied, xCoordinate, yCoordinate, width, height, columns)) {
        xCoordinate++;
        if (xCoordinate + width > columns) {
            xCoordinate = 0;
            yCoordinate++;
        }
    }
    return { x: xCoordinate, y: yCoordinate };
}

function findCompactedPosition(occupied: Set<string>, preferredX: number, preferredY: number, width: number, height: number, columns: number): GridCellPosition {
    if (columns < 1 || width < 1 || height < 1 || width > columns) {
        throw new Error('Invalid grid compaction dimensions');
    }
    const clampedX = clampNumber(preferredX, 0, columns - width);
    const maxPreferredY = Math.max(0, preferredY);
    for (let yCoordinate = 0; yCoordinate <= maxPreferredY; yCoordinate += 1) {
        if (isCellFree(occupied, clampedX, yCoordinate, width, height, columns)) {
            return { x: clampedX, y: yCoordinate };
        }
        for (let xCoordinate = 0; xCoordinate <= columns - width; xCoordinate += 1) {
            if (xCoordinate !== clampedX && isCellFree(occupied, xCoordinate, yCoordinate, width, height, columns)) {
                return { x: xCoordinate, y: yCoordinate };
            }
        }
    }
    return findFreePosition(occupied, clampedX, maxPreferredY, width, height, columns);
}

export { reserveCells, isCellFree, findFreePosition, findCompactedPosition };
