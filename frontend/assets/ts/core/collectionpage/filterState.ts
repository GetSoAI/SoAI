/* SoAI - Collection filter property validation and state updates [frontend/assets/ts/core/collectionpage/filterState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface CollectionFilterStateUpdates {
    setProvider(value: string): void;
    setStatus(value: string): void;
}

const updateCollectionFilterState = (pageId: string, property: string, value: string, updates: CollectionFilterStateUpdates): void => {
    if (property === 'filterProvider') {
        updates.setProvider(value);
        return;
    }
    if (property === 'filterStatus') {
        updates.setStatus(value);
        return;
    }
    throw new Error(`${pageId} collection filter property is unsupported: ${property}`);
};

export { updateCollectionFilterState };
export type { CollectionFilterStateUpdates };
