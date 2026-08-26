/* SoAI - Bounded collection range calculations and sequence validation [frontend/assets/ts/core/data/boundedcollectionrenderer/range.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

const COLLECTION_PAGE_SIZE = 48;
const COLLECTION_RETAINED_PAGE_COUNT = 4;
const COLLECTION_BUILD_FRAME_BUDGET_MS = 6;

interface CollectionRange {
    start: number;
    end: number;
}

const normalizedTotal = (totalCount: number): number => (Number.isFinite(totalCount) ? Math.max(0, Math.floor(totalCount)) : 0);
const retainedItemLimit = (): number => COLLECTION_PAGE_SIZE * COLLECTION_RETAINED_PAGE_COUNT;
const pageStart = (index: number): number => Math.floor(Math.max(0, index) / COLLECTION_PAGE_SIZE) * COLLECTION_PAGE_SIZE;

const createInitialRange = (totalCount: number): CollectionRange => {
    const total = normalizedTotal(totalCount);
    return { start: 0, end: Math.min(total, COLLECTION_PAGE_SIZE) };
};

const createCompleteRange = (totalCount: number): CollectionRange => ({ start: 0, end: normalizedTotal(totalCount) });

const createForwardRange = (current: CollectionRange, totalCount: number): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (current.end >= total) return { start: current.start, end: current.end };
    const end = Math.min(total, current.end + COLLECTION_PAGE_SIZE);
    const currentLength = Math.max(0, current.end - current.start);
    const start = currentLength < retainedItemLimit() ? current.start : Math.max(current.start, end - retainedItemLimit());
    return { start, end };
};

const createBackwardRange = (current: CollectionRange, totalCount: number): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (current.start <= 0) return { start: 0, end: Math.min(total, current.end) };
    const start = Math.max(0, current.start - COLLECTION_PAGE_SIZE);
    const currentLength = Math.max(0, current.end - current.start);
    const end = currentLength < retainedItemLimit() ? current.end : Math.min(current.end, start + retainedItemLimit());
    return { start, end: Math.min(total, end) };
};

const createTargetRange = (targetIndex: number, totalCount: number): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (total === 0) return { start: 0, end: 0 };
    const target = Math.min(total - 1, Math.max(0, Math.floor(targetIndex)));
    const start = pageStart(target);
    return { start, end: Math.min(total, start + COLLECTION_PAGE_SIZE) };
};

const reconcileRangeAfterDataChange = (current: CollectionRange, totalCount: number, survivingAnchorIndex: number | null): CollectionRange => {
    const total = normalizedTotal(totalCount);
    if (total === 0) return { start: 0, end: 0 };
    const retainedLength = Math.min(retainedItemLimit(), Math.max(COLLECTION_PAGE_SIZE, current.end - current.start));
    if (current.end > total) {
        const totalPages = Math.ceil(total / COLLECTION_PAGE_SIZE);
        const retainedPages = Math.max(1, Math.ceil(retainedLength / COLLECTION_PAGE_SIZE));
        const start = Math.max(0, (totalPages - retainedPages) * COLLECTION_PAGE_SIZE);
        return { start, end: total };
    }
    if (survivingAnchorIndex === null) {
        const start = Math.min(current.start, pageStart(total - 1));
        return { start, end: Math.min(total, start + retainedLength) };
    }
    if (survivingAnchorIndex >= current.start && survivingAnchorIndex < current.end) {
        return { start: current.start, end: Math.min(total, current.start + retainedLength) };
    }
    if (survivingAnchorIndex < current.start) {
        const start = pageStart(survivingAnchorIndex);
        return { start, end: Math.min(total, start + retainedLength) };
    }
    const target = createTargetRange(survivingAnchorIndex, total);
    const start = Math.max(0, target.end - retainedLength);
    return { start: pageStart(start), end: Math.min(total, pageStart(start) + retainedLength) };
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

export { COLLECTION_BUILD_FRAME_BUDGET_MS, COLLECTION_PAGE_SIZE, COLLECTION_RETAINED_PAGE_COUNT, createBackwardRange, createCompleteRange, createForwardRange, createInitialRange, createTargetRange, reconcileRangeAfterDataChange, validateCollectionSequence };
export type { CollectionRange };
