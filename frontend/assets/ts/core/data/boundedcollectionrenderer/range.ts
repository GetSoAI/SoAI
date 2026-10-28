/* SoAI - Bounded collection range calculations and sequence validation [frontend/assets/ts/core/data/boundedcollectionrenderer/range.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const COLLECTION_PAGE_SIZE = 72;
const COLLECTION_RETAINED_PAGE_COUNT = 4;
const COLLECTION_BUILD_FRAME_BUDGET_MS = 6;

interface CollectionRange {
    start: number;
    end: number;
}

interface CollectionRangePolicy {
    pageSize: number;
    retainedPageCount: number;
    rowSize: number;
}

const DEFAULT_COLLECTION_RANGE_POLICY: CollectionRangePolicy = Object.freeze({ pageSize: COLLECTION_PAGE_SIZE, retainedPageCount: COLLECTION_RETAINED_PAGE_COUNT, rowSize: 1 });

const createRowAlignedRangePolicy = (columnCount: number): CollectionRangePolicy => {
    const rowSize = Number.isFinite(columnCount) ? Math.max(1, Math.floor(columnCount)) : 1;
    return { pageSize: Math.ceil(COLLECTION_PAGE_SIZE / rowSize) * rowSize, retainedPageCount: COLLECTION_RETAINED_PAGE_COUNT, rowSize };
};

const normalizedTotal = (totalCount: number): number => (Number.isFinite(totalCount) ? Math.max(0, Math.floor(totalCount)) : 0);
const retainedItemLimit = (policy: CollectionRangePolicy): number => policy.pageSize * policy.retainedPageCount;
const pageStart = (index: number, policy: CollectionRangePolicy): number => Math.floor(Math.max(0, index) / policy.pageSize) * policy.pageSize;
const rowStart = (index: number, policy: CollectionRangePolicy): number => Math.floor(Math.max(0, index) / policy.rowSize) * policy.rowSize;
const isRetainedRangeFull = (range: CollectionRange, policy: CollectionRangePolicy): boolean => Math.ceil((range.end - range.start) / policy.rowSize) * policy.rowSize >= retainedItemLimit(policy);

const createInitialRange = (totalCount: number, policy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY): CollectionRange => {
    const total = normalizedTotal(totalCount);
    return { start: 0, end: Math.min(total, policy.pageSize) };
};

const createForwardRange = (current: CollectionRange, totalCount: number, policy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (current.end >= total) return { start: current.start, end: current.end };
    const end = Math.min(total, current.end + policy.pageSize);
    const start = Math.max(current.start, Math.ceil((end - retainedItemLimit(policy)) / policy.rowSize) * policy.rowSize);
    return { start: rowStart(start, policy), end };
};

const createBackwardRange = (current: CollectionRange, totalCount: number, policy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (current.start <= 0) return { start: 0, end: Math.min(total, current.end) };
    const requestedStart = rowStart(Math.max(0, current.start - policy.pageSize), policy);
    const start = isRetainedRangeFull(current, policy) ? requestedStart : Math.max(requestedStart, Math.ceil((current.end - retainedItemLimit(policy)) / policy.rowSize) * policy.rowSize);
    const end = Math.min(current.end, start + retainedItemLimit(policy));
    return { start, end: Math.min(total, end) };
};

const createTargetRange = (targetIndex: number, totalCount: number, policy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (total === 0) return { start: 0, end: 0 };
    const target = Math.min(total - 1, Math.max(0, Math.floor(targetIndex)));
    const start = pageStart(target, policy);
    return { start, end: Math.min(total, start + policy.pageSize) };
};

const reconcileRangeAfterDataChange = (current: CollectionRange, totalCount: number, survivingAnchorIndex: number | null, policy: CollectionRangePolicy = DEFAULT_COLLECTION_RANGE_POLICY): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (total === 0) return { start: 0, end: 0 };
    const retainedLength = Math.min(retainedItemLimit(policy), Math.max(policy.pageSize, Math.ceil((current.end - current.start) / policy.rowSize) * policy.rowSize));
    if (current.end > total) {
        const totalPages = Math.ceil(total / policy.pageSize);
        const retainedPages = Math.max(1, Math.ceil(retainedLength / policy.pageSize));
        const start = Math.max(0, (totalPages - retainedPages) * policy.pageSize);
        return { start, end: total };
    }
    if (survivingAnchorIndex === null) {
        const start = rowStart(Math.min(current.start, pageStart(total - 1, policy)), policy);
        return { start, end: Math.min(total, start + retainedLength) };
    }
    if (survivingAnchorIndex >= current.start && survivingAnchorIndex < current.end) {
        const start = Math.max(rowStart(current.start, policy), rowStart(survivingAnchorIndex, policy) + policy.rowSize - retainedLength);
        return { start, end: Math.min(total, start + retainedLength) };
    }
    if (survivingAnchorIndex < current.start) {
        const start = pageStart(survivingAnchorIndex, policy);
        return { start, end: Math.min(total, start + retainedLength) };
    }
    const target = createTargetRange(survivingAnchorIndex, total, policy);
    const start = pageStart(Math.max(0, target.end - retainedLength), policy);
    return { start, end: Math.min(total, start + retainedLength) };
};

const validateCollectionSequence = <TItem>(ids: readonly string[], lookup: ReadonlyMap<string, TItem>): string[] => {
    const validated: string[] = [];
    const seen = new Set<string>();
    for (const identifier of ids) {
        if (typeof identifier !== 'string' || identifier.length === 0) throw new Error('Collection identifiers must be non-empty strings');
        if (seen.has(identifier)) throw new Error(`Collection identifier is duplicate: ${identifier}`);
        if (!lookup.has(identifier)) throw new Error(`Collection lookup is missing identifier: ${identifier}`);
        seen.add(identifier);
        validated.push(identifier);
    }
    return validated;
};

export { COLLECTION_BUILD_FRAME_BUDGET_MS, COLLECTION_PAGE_SIZE, COLLECTION_RETAINED_PAGE_COUNT, DEFAULT_COLLECTION_RANGE_POLICY, createBackwardRange, createForwardRange, createInitialRange, createRowAlignedRangePolicy, createTargetRange, isRetainedRangeFull, reconcileRangeAfterDataChange, validateCollectionSequence };
export type { CollectionRange, CollectionRangePolicy };
