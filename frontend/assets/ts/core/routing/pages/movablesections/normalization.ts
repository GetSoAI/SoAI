/* SoAI - Shared routing normalization [frontend/assets/ts/core/routing/pages/movablesections/normalization.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { clampNumber } from '@core/primitives/clampNumber.ts';
import type { MovableSectionBlueprint, MovableSectionId } from '@core/routing/pages/movablesections/types.ts';
import type { GridPosition } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { isObject } from '@core/typeGuards.ts';
import { readClampedRoundedIntegerOrFallbackValue } from '@core/types/numberCoercionReaders.ts';
import { findCompactedPosition, reserveCells } from '@core/ui/gridCollision.ts';

const parseGridPosition = (value: GridPosition | JsonValue | null | undefined, columns: number): GridPosition | null => {
    if (!isObject(value)) {
        return null;
    }
    const widthValue = 'width' in value ? value['width'] : null;
    const heightValue = 'height' in value ? value['height'] : null;
    const xValue = 'x' in value ? value['x'] : null;
    const yValue = 'y' in value ? value['y'] : null;
    const width = readClampedRoundedIntegerOrFallbackValue(widthValue, 1, 1, Math.max(1, columns));
    const height = readClampedRoundedIntegerOrFallbackValue(heightValue, 1, 1, undefined);
    const maxX = Math.max(0, columns - width);
    const xCoordinate = readClampedRoundedIntegerOrFallbackValue(xValue, 0, 0, maxX);
    const yCoordinate = readClampedRoundedIntegerOrFallbackValue(yValue, 0, 0, undefined);
    return { x: xCoordinate, y: yCoordinate, width, height };
};

const toStoredSectionsMap = <TSectionId extends MovableSectionId>(value: JsonValue | null | undefined, isSectionId: (candidate: string) => candidate is TSectionId): Map<TSectionId, GridPosition | JsonValue | null | undefined> | null => {
    if (!isObject(value)) {
        return null;
    }
    const entries: Array<[TSectionId, GridPosition | JsonValue | null | undefined]> = [];
    for (const [key, item] of Object.entries(value)) {
        if (isSectionId(key)) {
            entries.push([key, item]);
        }
    }
    return new Map(entries);
};

const getDisplayLayout = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>, currentColumns: number, collapsed: boolean, desktopColumns: number): Map<TSectionId, GridPosition> => {
    if (currentColumns === desktopColumns) {
        return source;
    }
    return collapsed ? buildSequentialLayout(source) : adaptLayoutForColumns(source, currentColumns);
};

const filterLayoutBySectionIds = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>, sectionIds: ReadonlySet<TSectionId>): Map<TSectionId, GridPosition> => {
    const filtered = new Map<TSectionId, GridPosition>();
    for (const [id, position] of source.entries()) {
        if (sectionIds.has(id)) {
            filtered.set(id, position);
        }
    }
    return filtered;
};

const buildSequentialLayout = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>): Map<TSectionId, GridPosition> => {
    const ordered = Array.from(source.entries()).sort(([, first], [, second]): number => (first.y !== second.y ? first.y - second.y : first.x - second.x));
    const sequential: Map<TSectionId, GridPosition> = new Map();
    let nextRow = 0;
    for (const [id, position] of ordered) {
        const height = Math.max(1, Math.round(position.height));
        sequential.set(id, { x: 0, y: nextRow, width: 1, height });
        nextRow += height;
    }
    return sequential;
};

const adaptLayoutForColumns = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>, targetColumns: number): Map<TSectionId, GridPosition> => {
    const ordered = Array.from(source.entries()).sort(([, first], [, second]): number => (first.y !== second.y ? first.y - second.y : first.x - second.x));
    const adapted: Map<TSectionId, GridPosition> = new Map();
    const occupied: Set<string> = new Set();
    for (const [id, position] of ordered) {
        const clampedWidth = clampNumber(Math.round(position.width), 1, targetColumns);
        const height = Math.max(1, Math.round(position.height));
        const maxX = Math.max(0, targetColumns - clampedWidth);
        const preferredX = clampNumber(Math.round(position.x), 0, maxX);
        const preferredY = Math.max(0, Math.round(position.y));
        const slot = findCompactedPosition(occupied, preferredX, preferredY, clampedWidth, height, targetColumns);
        adapted.set(id, { x: slot.x, y: slot.y, width: clampedWidth, height });
        reserveCells(occupied, slot.x, slot.y, clampedWidth, height);
    }
    return adapted;
};

const normalizeLayout = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition | JsonValue | null | undefined> | null, blueprints: ReadonlyMap<TSectionId, MovableSectionBlueprint>, columns: number): Map<TSectionId, GridPosition> => {
    const defaults = new Map<TSectionId, GridPosition>();
    for (const [id, blueprint] of blueprints.entries()) {
        const layout = parseGridPosition(blueprint.layout, columns);
        if (!layout) {
            throw new Error(`Invalid movable layout blueprint for section "${id}"`);
        }
        defaults.set(id, layout);
    }
    return normalizeSectionPositions(source ?? new Map<TSectionId, GridPosition | JsonValue | null | undefined>(), defaults, blueprints, columns);
};

const normalizeSectionPositions = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition | JsonValue | null | undefined>, defaults: Map<TSectionId, GridPosition>, blueprints: ReadonlyMap<TSectionId, MovableSectionBlueprint>, columns: number): Map<TSectionId, GridPosition> => {
    const candidates: Array<[TSectionId, GridPosition]> = [];
    for (const id of blueprints.keys()) {
        const defaultPosition = defaults.get(id) ?? { x: 0, y: 0, width: 1, height: 1 };
        const storedPosition = parseGridPosition(source.get(id), columns);
        candidates.push([id, storedPosition ?? defaultPosition]);
    }
    return compactLayoutEntries(candidates, columns);
};

const compactLayout = <TSectionId extends MovableSectionId>(source: Map<TSectionId, GridPosition>, columns: number): Map<TSectionId, GridPosition> => {
    return compactLayoutEntries(Array.from(source.entries()), columns);
};

const compactLayoutEntries = <TSectionId extends MovableSectionId>(entries: Array<[TSectionId, GridPosition]>, columns: number): Map<TSectionId, GridPosition> => {
    const occupied: Set<string> = new Set();
    const normalized: Map<TSectionId, GridPosition> = new Map();
    const ordered = entries.sort(([, first], [, second]): number => (first.y !== second.y ? first.y - second.y : first.x - second.x));
    for (const [id, raw] of ordered) {
        const width = readClampedRoundedIntegerOrFallbackValue(raw.width, 1, 1, columns);
        const height = readClampedRoundedIntegerOrFallbackValue(raw.height, 1, 1, undefined);
        const maxX = Math.max(0, columns - width);
        const startX = readClampedRoundedIntegerOrFallbackValue(raw.x, 0, 0, maxX);
        const startY = readClampedRoundedIntegerOrFallbackValue(raw.y, 0, 0, undefined);
        const slot = findCompactedPosition(occupied, startX, startY, width, height, columns);
        normalized.set(id, { x: slot.x, y: slot.y, width, height });
        reserveCells(occupied, slot.x, slot.y, width, height);
    }
    return normalized;
};

export { compactLayout, filterLayoutBySectionIds, getDisplayLayout, normalizeLayout, parseGridPosition, toStoredSectionsMap };
