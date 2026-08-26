/* SoAI - Shared data collection view contracts [frontend/assets/ts/core/data/collectionview/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BoundedCollectionCommitContext } from '@core/data/boundedcollectionrenderer/public.ts';
import type { ClientDataHub, ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';

type CollectionItem = ResourceItem;
type TrackByFunction = (item: CollectionItem) => string | null;
type PresentationFingerprintFunction = (item: CollectionItem) => string;
type FilterFunction = (item: CollectionItem) => boolean;
type SortFunction = (firstValue: CollectionItem, secondValue: CollectionItem) => number;
type RenderItemFunction = (item: CollectionItem, id: string) => HTMLElement;
type ResolveContainerFunction = () => HTMLElement | null;
type ResolveEmptyStateFunction = () => HTMLElement | null;
type ResolveItemIdentifierFunction = (element: HTMLElement) => string | null;
type LoadingLabelFunction = () => string;
type CollectionViewHost = WeakKey;

interface RefreshContext {
    filtered: readonly CollectionItem[];
    orderedIds: readonly string[];
    itemLookup: ReadonlyMap<string, CollectionItem>;
    dirtyIds: readonly string[];
    filteredCount: number;
    totalCount: number;
    reason: string;
}

interface CollectionPresentationContext {
    filtered: readonly CollectionItem[];
    orderedIds: readonly string[];
    itemLookup: ReadonlyMap<string, CollectionItem>;
    reason: string;
}

type PreparePresentationFunction = (context: CollectionPresentationContext) => readonly string[];

interface CollectionCriteria {
    filter?: FilterFunction | null | undefined;
    sort?: SortFunction | null | undefined;
    resetScroll?: boolean | undefined;
}

interface CollectionViewOptions {
    resource: string;
    host: CollectionViewHost;
    trackBy?: TrackByFunction | undefined;
    presentationFingerprint?: PresentationFingerprintFunction | undefined;
    hub?: ClientDataHub | undefined;
    renderItem: RenderItemFunction;
    loadingLabel: LoadingLabelFunction;
    resolveContainer: ResolveContainerFunction;
    resolveItemIdentifier: ResolveItemIdentifierFunction;
    resolveEmptyState?: ResolveEmptyStateFunction | undefined;
    onSnapshot?: ((snapshot: ResourceSnapshot) => void) | null | undefined;
    preparePresentation?: PreparePresentationFunction | null | undefined;
    onRefresh?: ((context: RefreshContext) => void) | null | undefined;
    onCommit?: ((context: BoundedCollectionCommitContext) => void) | null | undefined;
}

interface CollectionRuntime {
    getAll: () => CollectionItem[];
    getFiltered: () => CollectionItem[];
    size: () => number;
    find: (id: string) => CollectionItem | null;
    update: (id: string, updater: Partial<CollectionItem> | ((item: CollectionItem) => CollectionItem | null)) => CollectionItem | null;
    upsert: (item: CollectionItem) => CollectionItem | null;
    remove: (id: string) => boolean;
    apply: (options?: CollectionCriteria) => CollectionItem[];
    refresh: () => CollectionItem[];
    rebuildForViewMode: () => void;
    prepareForViewModeChange: () => void;
}

interface CollectionRuntimeHost {
    allItems: CollectionItem[];
    filteredItems: CollectionItem[];
    itemLookup: Map<string, CollectionItem>;
    applyCriteria: (criteria?: CollectionCriteria) => CollectionItem[];
    refresh: (context?: { reason?: string; resetScroll?: boolean }) => CollectionItem[];
    upsertLocal: (item: CollectionItem) => CollectionItem | null;
    removeLocal: (id: string) => boolean;
    prepareForViewModeChange: () => void;
    rebuildForViewMode: () => void;
}

interface CollectionRendererOptions {
    resource: string;
    renderItem: RenderItemFunction;
    loadingLabel: LoadingLabelFunction;
    resolveContainer: ResolveContainerFunction;
    resolveItemIdentifier: ResolveItemIdentifierFunction;
    resolveEmptyState?: ResolveEmptyStateFunction | undefined;
    onCommit?: ((context: BoundedCollectionCommitContext) => void) | null | undefined;
}

export type { CollectionCriteria, CollectionPresentationContext, CollectionRuntime, CollectionRuntimeHost, CollectionItem, CollectionRendererOptions, CollectionViewHost, CollectionViewOptions, FilterFunction, LoadingLabelFunction, PreparePresentationFunction, PresentationFingerprintFunction, RefreshContext, RenderItemFunction, ResolveContainerFunction, ResolveEmptyStateFunction, ResolveItemIdentifierFunction, SortFunction, TrackByFunction };
