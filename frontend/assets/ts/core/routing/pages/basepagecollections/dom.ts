/* SoAI - Shared routing base page collections DOM contracts [frontend/assets/ts/core/routing/pages/basepagecollections/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { runCleanup } from '@core/lifecycle/cleanup.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import type { CollectionRuntime, CollectionTargets } from '@core/routing/pages/pagetypes/public.ts';
import type { BasePageCollectionsState } from '@core/routing/pages/basepagecollections/state.ts';
import type { BasePageCollectionsCollectionViewContract } from '@core/routing/pages/basepagecollections/contracts.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';

interface ItemCardIdentifierCandidate {
    id?: string | number | undefined;
    name?: string | number | undefined;
}

const getCollectionTargets = (state: BasePageCollectionsState, getUI: (selector: string) => Element | null): CollectionTargets | null => {
    const { emptyStateId, gridId } = state.collectionConfig || {};
    const emptyElement = emptyStateId ? getUI(emptyStateId) : null;
    const gridElement = gridId ? getUI(gridId) : null;
    return emptyElement && gridElement ? { emptyElement: emptyElement, gridElement: gridElement } : null;
};

const isCollectionRuntime = <T>(value: T): value is T & CollectionRuntime => {
    if (!isObject(value)) {
        return false;
    }
    return 'getAll' in value && isFunction(value.getAll) && 'getFiltered' in value && isFunction(value.getFiltered) && 'size' in value && isFunction(value.size) && 'find' in value && isFunction(value.find) && 'upsert' in value && isFunction(value.upsert) && 'remove' in value && isFunction(value.remove) && 'apply' in value && isFunction(value.apply) && 'refresh' in value && isFunction(value.refresh);
};

const getCollectionRuntime = (state: BasePageCollectionsState): CollectionRuntime | null => {
    const resolved = state.collectionView?.getCollectionRuntime?.() ?? state.collection ?? null;
    state.collection = resolved;
    return isCollectionRuntime(resolved) ? resolved : null;
};

const getItemCardId = (item: ItemCardIdentifierCandidate | JsonValue | null | undefined): string | null => {
    if (!item || !isObject(item)) {
        return null;
    }
    const idValue = 'id' in item ? item.id : null;
    if (typeof idValue === 'string' || typeof idValue === 'number') {
        return String(idValue);
    }
    const nameValue = 'name' in item ? item.name : null;
    if (typeof nameValue === 'string' || typeof nameValue === 'number') {
        return String(nameValue);
    }
    return null;
};

const disposeCollectionView = (collectionView: BasePageCollectionsCollectionViewContract | null): void => {
    if (!collectionView || !isFunction(collectionView.dispose)) {
        return;
    }
    collectionView.dispose();
};

const cleanupCollectionState = (state: BasePageCollectionsState): void => {
    const collectionView = state.collectionView;
    runCleanup(collectionView ? () => disposeCollectionView(collectionView) : null, (runtimeError) => {
        errorHandler.warn('BasePageCollections', 'Collection view cleanup failed', runtimeError);
    });
    state.collectionView = null;
    state.collection = null;
};

export { getCollectionTargets, getCollectionRuntime, getItemCardId, disposeCollectionView, cleanupCollectionState };
