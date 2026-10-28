/* SoAI - Fixed-row collection scroll extent and viewport ranges [frontend/assets/ts/core/data/boundedcollectionrenderer/gridScrollExtent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getComputedStyleStrict } from '@core/environment/public.ts';
import { resolveCollectionScrollRoot } from '@core/data/boundedcollectionrenderer/scrollRoot.ts';
import type { CollectionRange, CollectionRangePolicy } from '@core/data/boundedcollectionrenderer/range.ts';
import type { CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';

class CollectionGridScrollExtent {
    #container: HTMLElement | null = null;
    #originalStart = '';
    #originalEnd = '';
    #originalStartPriority = '';
    #originalEndPriority = '';
    #paddingStart = 0;
    #paddingEnd = 0;

    constructor(alignRows: boolean) {
        if (!alignRows) throw new Error('Complete grid scroll extents require row alignment');
    }

    capture(container: HTMLElement, ids: readonly string[], policy: CollectionRangePolicy): CollectionViewportAnchor | null {
        if (ids.length === 0) return null;
        const geometry = this.#measure(container);
        const row = Math.floor(Math.max(0, geometry.position - geometry.paddingStart + geometry.gap) / geometry.stride);
        const index = Math.min(row * policy.rowSize, ids.length - 1);
        const identifier = ids[index];
        if (identifier === undefined) return null;
        return { identifier, offset: geometry.paddingStart + Math.floor(index / policy.rowSize) * geometry.stride - geometry.position, atStart: geometry.position === 0 };
    }

    restore(container: HTMLElement, anchor: CollectionViewportAnchor, ids: readonly string[], policy: CollectionRangePolicy): void {
        const index = ids.indexOf(anchor.identifier);
        if (index < 0) return;
        const geometry = this.#measure(container);
        geometry.root.scrollTop = anchor.atStart ? 0 : geometry.paddingStart + Math.floor(index / policy.rowSize) * geometry.stride - anchor.offset;
    }

    range(container: HTMLElement, total: number, policy: CollectionRangePolicy, preferredRange: CollectionRange | null): CollectionRange {
        const geometry = this.#measure(container);
        const totalRows = Math.ceil(total / policy.rowSize);
        const minimumRows = policy.pageSize / policy.rowSize;
        const visibleRows = Math.ceil(geometry.viewport / geometry.stride) + 1;
        const maximumRows = minimumRows * policy.retainedPageCount;
        if (geometry.viewport > 0 && visibleRows > maximumRows) throw new Error('Fixed collection grid viewport exceeds its retained row ceiling');
        const retainedRows = Math.min(totalRows, maximumRows, geometry.viewport > 0 ? Math.max(minimumRows, visibleRows + 4) : minimumRows);
        const firstVisibleRow = Math.floor(Math.max(0, geometry.position - geometry.paddingStart) / geometry.stride);
        const preferredRow = preferredRange === null ? Math.max(0, firstVisibleRow - 2) : Math.floor(preferredRange.start / policy.rowSize);
        const startRow = Math.min(preferredRow, Math.max(0, totalRows - retainedRows));
        return { start: startRow * policy.rowSize, end: Math.min(total, (startRow + retainedRows) * policy.rowSize) };
    }

    apply(container: HTMLElement, range: CollectionRange, total: number, policy: CollectionRangePolicy): void {
        const geometry = this.#measure(container);
        const before = Math.floor(range.start / policy.rowSize) * geometry.stride;
        const after = (Math.ceil(total / policy.rowSize) - Math.ceil(range.end / policy.rowSize)) * geometry.stride;
        container.style.setProperty('padding-block-start', `${geometry.paddingStart + before}px`);
        container.style.setProperty('padding-block-end', `${geometry.paddingEnd + after}px`);
    }

    dispose(): void {
        if (this.#container !== null) {
            this.#container.style.setProperty('padding-block-start', this.#originalStart, this.#originalStartPriority);
            this.#container.style.setProperty('padding-block-end', this.#originalEnd, this.#originalEndPriority);
        }
        this.#container = null;
        this.#paddingStart = 0;
        this.#paddingEnd = 0;
    }

    #measure(container: HTMLElement): { root: HTMLElement; stride: number; gap: number; paddingStart: number; paddingEnd: number; viewport: number; position: number } {
        const root = resolveCollectionScrollRoot(container);
        if (!(root instanceof HTMLElement) || root === container || container.parentElement !== root) throw new Error('Fixed collection grids require a direct enclosing scroll viewport');
        const style = getComputedStyleStrict(container);
        const rowHeight = Number.parseFloat(style.gridAutoRows);
        const gap = style.rowGap === 'normal' || style.rowGap === '' ? 0 : Number.parseFloat(style.rowGap);
        if (!/^\d+(?:\.\d+)?px$/.test(style.gridAutoRows) || !Number.isFinite(rowHeight) || rowHeight <= 0 || !Number.isFinite(gap) || gap < 0) throw new Error('Fixed collection grids require a positive pixel row height and a nonnegative gap');
        if (this.#container !== container) {
            this.dispose();
            this.#container = container;
            this.#originalStart = container.style.getPropertyValue('padding-block-start');
            this.#originalEnd = container.style.getPropertyValue('padding-block-end');
            this.#originalStartPriority = container.style.getPropertyPriority('padding-block-start');
            this.#originalEndPriority = container.style.getPropertyPriority('padding-block-end');
            this.#paddingStart = Number.parseFloat(style.paddingBlockStart) || 0;
            this.#paddingEnd = Number.parseFloat(style.paddingBlockEnd) || 0;
        }
        return {
            root,
            stride: rowHeight + gap,
            gap,
            paddingStart: this.#paddingStart,
            paddingEnd: this.#paddingEnd,
            viewport: root.clientHeight,
            position: root.scrollTop
        };
    }
}

export { CollectionGridScrollExtent };
