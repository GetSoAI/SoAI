/* SoAI - Bounded collection renderer contracts [frontend/assets/ts/core/data/boundedcollectionrenderer/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionRange } from '@core/data/boundedcollectionrenderer/range.ts';

type CollectionEdge = 'backward' | 'forward';

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
    renderAllItems?: boolean | undefined;
    onCommit?: ((context: BoundedCollectionCommitContext) => void) | undefined;
    onError?: ((error: Error) => void) | undefined;
}

interface BoundedCollectionUpdate<TItem> {
    ids: readonly string[];
    lookup: ReadonlyMap<string, TItem>;
    dirtyIds?: readonly string[] | undefined;
    resetScroll?: boolean | undefined;
    restoreViewportAnchor?: CollectionViewportAnchor | undefined;
    synchronizeLookupOnly?: boolean | undefined;
}

interface CollectionSequenceState<TItem> {
    ids: readonly string[];
    lookup: ReadonlyMap<string, TItem>;
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
    range: CollectionRange;
    dirtyIds: ReadonlySet<string>;
    existingNodes: ReadonlyMap<string, HTMLElement>;
    plannedNodes: HTMLElement[];
    enteringElements: HTMLElement[];
    cursor: number;
    loader: HTMLElement | null;
    edge: CollectionEdge | null;
    resetScroll: boolean;
    revealId: string | null;
    modeAnchor: CollectionViewportAnchor | null;
    previousIds: readonly string[];
    previousLookup: ReadonlyMap<string, TItem>;
}

export type { BoundedCollectionCommitContext, BoundedCollectionRendererOptions, BoundedCollectionUpdate, CollectionBuild, CollectionCommitAnchor, CollectionEdge, CollectionSequenceState, CollectionViewportAnchor };
