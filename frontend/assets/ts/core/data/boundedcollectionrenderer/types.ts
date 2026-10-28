/* SoAI - Bounded collection renderer contracts [frontend/assets/ts/core/data/boundedcollectionrenderer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionRange, CollectionRangePolicy } from '@core/data/boundedcollectionrenderer/range.ts';

type CollectionEdge = 'backward' | 'forward';

type CollectionFocusOwner = 'renderer' | 'caller';

interface BoundedCollectionCommitContext {
    container: HTMLElement;
    rangeStart: number;
    rangeEnd: number;
    totalCount: number;
    mountedElements: readonly HTMLElement[];
    enteringElements: readonly HTMLElement[];
}

interface BoundedCollectionRendererOptions<TItem> {
    resolveContainer: () => HTMLElement | null;
    resolveEmptyState?: (() => HTMLElement | null) | undefined;
    renderItem: (item: TItem, context: { id: string }) => HTMLElement;
    resolveItemIdentifier: (element: HTMLElement) => string | null;
    loadingLabel: () => string;
    alignRows?: boolean | undefined;
    preserveGridScrollExtent?: boolean | undefined;
    patchMountedItems?: boolean | undefined;
    onCommit?: ((context: BoundedCollectionCommitContext) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
}

interface BoundedCollectionUpdate<TItem> {
    ids: readonly string[];
    lookup: ReadonlyMap<string, TItem>;
    dirtyIds?: readonly string[] | undefined;
    resetScroll?: boolean | undefined;
    animateLayout?: boolean | undefined;
    restoreViewportAnchor?: CollectionViewportAnchor | undefined;
    synchronizeLookupOnly?: boolean | undefined;
}

interface CollectionRevealOptions {
    focusOwner?: CollectionFocusOwner | undefined;
    signal?: AbortSignal | null | undefined;
}

interface CollectionSequenceState<TItem> {
    ids: readonly string[];
    lookup: ReadonlyMap<string, TItem>;
}

interface CollectionItemPatch {
    element: HTMLElement;
    replacement: HTMLElement;
}

interface CollectionCommitAnchor {
    element: HTMLElement;
    offset: number;
}

interface CollectionViewportAnchor {
    identifier: string;
    offset: number;
    atStart: boolean;
}

interface CollectionBuild<TItem> {
    generation: number;
    container: HTMLElement;
    ids: readonly string[];
    lookup: ReadonlyMap<string, TItem>;
    planRange: (policy: CollectionRangePolicy) => CollectionRange;
    policy: CollectionRangePolicy | null;
    range: CollectionRange | null;
    dirtyIds: ReadonlySet<string>;
    existingNodes: ReadonlyMap<string, HTMLElement>;
    plannedNodes: HTMLElement[];
    itemPatches: CollectionItemPatch[];
    enteringElements: HTMLElement[];
    cursor: number;
    loader: HTMLElement | null;
    edge: CollectionEdge | null;
    resetScroll: boolean;
    animateLayout: boolean;
    exitStarted: boolean;
    revealId: string | null;
    focusOwner: CollectionFocusOwner;
    modeAnchor: CollectionViewportAnchor | null;
    previousIds: readonly string[];
    previousLookup: ReadonlyMap<string, TItem>;
    gridScrollExtent?: { apply(container: HTMLElement, range: CollectionRange, total: number, policy: CollectionRangePolicy): void } | null;
}

export type { BoundedCollectionCommitContext, BoundedCollectionRendererOptions, BoundedCollectionUpdate, CollectionBuild, CollectionCommitAnchor, CollectionEdge, CollectionFocusOwner, CollectionItemPatch, CollectionRevealOptions, CollectionSequenceState, CollectionViewportAnchor };
