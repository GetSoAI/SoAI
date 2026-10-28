/* SoAI - Bounded collection geometry-aware build range planning [frontend/assets/ts/core/data/boundedcollectionrenderer/buildPlanning.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { DEFAULT_COLLECTION_RANGE_POLICY, createBackwardRange, createForwardRange, createInitialRange, createRowAlignedRangePolicy, createTargetRange, reconcileRangeAfterDataChange, type CollectionRange, type CollectionRangePolicy } from '@core/data/boundedcollectionrenderer/range.ts';
import { indexExistingCollectionNodes } from '@core/data/boundedcollectionrenderer/transaction.ts';
import type { CollectionBuild, CollectionEdge, CollectionViewportAnchor } from '@core/data/boundedcollectionrenderer/types.ts';
import { measureGridColumnCount } from '@core/layout/elementGeometry.ts';

type CollectionRangePlan = (policy: CollectionRangePolicy) => CollectionRange;

interface CollectionUpdateRangeInput {
    total: number;
    previousRange: CollectionRange;
    anchorIndex: number;
    restoreAnchor: CollectionViewportAnchor | null;
    resetScroll: boolean;
    extendVisibleEnd: boolean;
}

const planUpdateRange =
    (input: CollectionUpdateRangeInput): CollectionRangePlan =>
    (policy) => {
        const { total, anchorIndex, restoreAnchor } = input;
        const planned = restoreAnchor !== null && anchorIndex >= 0 ? (restoreAnchor.atStart ? createInitialRange(total, policy) : createTargetRange(anchorIndex, total, policy)) : input.resetScroll ? createInitialRange(total, policy) : reconcileRangeAfterDataChange(input.previousRange, total, anchorIndex >= 0 ? anchorIndex : null, policy);
        return input.extendVisibleEnd ? createForwardRange(planned, total, policy) : planned;
    };

const planEdgeRange =
    (edge: CollectionEdge, committedRange: CollectionRange, total: number): CollectionRangePlan =>
    (policy) =>
        edge === 'forward' ? createForwardRange(committedRange, total, policy) : createBackwardRange(committedRange, total, policy);

const planGeometryRange =
    (anchor: CollectionViewportAnchor | null, anchorIndex: number, committedRange: CollectionRange, total: number): CollectionRangePlan =>
    (policy) => {
        if (anchor === null || anchorIndex < 0) return reconcileRangeAfterDataChange(committedRange, total, null, policy);
        return anchor.atStart ? createInitialRange(total, policy) : createTargetRange(anchorIndex, total, policy);
    };

const resolveCollectionRangePolicy = (alignRows: boolean, container: HTMLElement): CollectionRangePolicy | null => {
    if (!alignRows) return DEFAULT_COLLECTION_RANGE_POLICY;
    const columnCount = measureGridColumnCount(container);
    return columnCount === null ? null : createRowAlignedRangePolicy(columnCount);
};

const planCollectionBuild = <TItem>(build: CollectionBuild<TItem>, alignRows: boolean): CollectionRange | null => {
    if (build.range !== null) return build.range;
    const policy = resolveCollectionRangePolicy(alignRows && build.ids.length > 0, build.container);
    if (policy === null) return null;
    const range = build.planRange(policy);
    build.policy = policy;
    build.range = range;
    build.cursor = range.start;
    return range;
};

const resetCollectionBuildPlan = <TItem>(build: CollectionBuild<TItem>): void => {
    build.policy = null;
    build.range = null;
    build.plannedNodes = [];
    build.itemPatches = [];
    build.enteringElements = [];
    build.existingNodes = indexExistingCollectionNodes(build.container);
};

export { planCollectionBuild, planEdgeRange, planGeometryRange, planUpdateRange, resetCollectionBuildPlan, resolveCollectionRangePolicy };
export type { CollectionRangePlan };
