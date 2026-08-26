/* SoAI - Shared data collection view effects [frontend/assets/ts/core/data/collectionview/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { BoundedCollectionRenderer } from '@core/data/boundedcollectionrenderer/public.ts';
import { isFunction, isNullOrUndefined, isObject, isString } from '@core/typeGuards.ts';
import type { CollectionRuntime, CollectionRuntimeHost, CollectionItem, CollectionRendererOptions, TrackByFunction } from '@core/data/collectionview/types.ts';

const resolveCollectionTrackBy = (trackBy: TrackByFunction | undefined): TrackByFunction => {
    if (trackBy) return trackBy;
    return (item: CollectionItem): string | null => {
        if (!isObject(item)) return null;
        const identifier = item['id'];
        return isNullOrUndefined(identifier) ? null : String(identifier);
    };
};

const createCollectionRenderer = ({ resource, renderItem, loadingLabel, resolveContainer, resolveItemIdentifier, resolveEmptyState, onCommit }: CollectionRendererOptions): BoundedCollectionRenderer<CollectionItem> => {
    if (!isFunction(renderItem)) throw new Error(`CollectionView ${resource} requires renderItem`);
    if (!isFunction(loadingLabel)) throw new Error(`CollectionView ${resource} requires loadingLabel`);
    if (!isFunction(resolveContainer)) throw new Error(`CollectionView ${resource} requires resolveContainer`);
    if (!isFunction(resolveItemIdentifier)) throw new Error(`CollectionView ${resource} requires resolveItemIdentifier`);
    return new BoundedCollectionRenderer<CollectionItem>({
        resolveContainer,
        resolveEmptyState,
        resolveItemIdentifier,
        loadingLabel: () => {
            const label = loadingLabel();
            if (!isString(label) || !label.trim()) throw new Error(`CollectionView ${resource} loadingLabel must return text`);
            return label;
        },
        renderItem: (item, context): HTMLElement => {
            if (!isObject(item)) throw new Error(`CollectionView renderItem received invalid item for ${resource}`);
            return renderItem(item, context.id);
        },
        onCommit: onCommit ?? undefined
    });
};

const resolveRefreshReason = (reasonValue: string | undefined): string => (isString(reasonValue) && reasonValue.trim() ? reasonValue.trim() : 'refresh');

const createCollectionRuntime = (host: CollectionRuntimeHost): CollectionRuntime => ({
    getAll: (): CollectionItem[] => host.allItems.slice(),
    getFiltered: (): CollectionItem[] => host.filteredItems.slice(),
    size: (): number => host.allItems.length,
    find: (id: string): CollectionItem | null => host.itemLookup.get(isString(id) ? id : String(id)) ?? null,
    update: (id, updater): CollectionItem | null => {
        const identifier = isString(id) ? id : String(id);
        const current = host.itemLookup.get(identifier);
        if (!current) return null;
        const next = typeof updater === 'function' ? updater({ ...current }) : { ...current, ...updater };
        if (next === null) return current;
        host.upsertLocal(next);
        return next;
    },
    upsert: (item): CollectionItem | null => host.upsertLocal(item),
    remove: (id): boolean => host.removeLocal(id),
    apply: (criteria = {}): CollectionItem[] => host.applyCriteria(criteria),
    refresh: (): CollectionItem[] => host.refresh({ reason: 'manual' }),
    prepareForViewModeChange: (): void => host.prepareForViewModeChange(),
    rebuildForViewMode: (): void => host.rebuildForViewMode()
});

export { createCollectionRuntime, createCollectionRenderer, resolveCollectionTrackBy, resolveRefreshReason };
