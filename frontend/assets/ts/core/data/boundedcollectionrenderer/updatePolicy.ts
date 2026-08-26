/* SoAI - Bounded collection lookup-only update policy [frontend/assets/ts/core/data/boundedcollectionrenderer/updatePolicy.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BoundedCollectionUpdate, CollectionBuild } from '@core/data/boundedcollectionrenderer/types.ts';

const canSynchronizeCollectionLookup = <TItem>(input: BoundedCollectionUpdate<TItem>, identifiers: readonly string[], currentIdentifiers: readonly string[], activeBuild: CollectionBuild<TItem> | null, hasCommitted: boolean, revealPending: boolean, viewModeAnchorPrepared: boolean, currentContainer: HTMLElement | null, nextContainer: HTMLElement | null): boolean => {
    if ((!hasCommitted && activeBuild === null) || viewModeAnchorPrepared || input.resetScroll === true || input.restoreViewportAnchor !== undefined) return false;
    if (activeBuild !== null && input.synchronizeLookupOnly !== true) return false;
    if (revealPending && input.synchronizeLookupOnly !== true) return false;
    if (currentContainer === null || currentContainer !== nextContainer || !currentContainer.isConnected) return false;
    if ((input.dirtyIds?.length ?? 0) > 0 || identifiers.length !== currentIdentifiers.length) return false;
    return identifiers.every((identifier, index) => currentIdentifiers[index] === identifier);
};

export { canSynchronizeCollectionLookup };
