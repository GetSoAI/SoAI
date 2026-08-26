/* SoAI - Collection initial commit and reveal lifecycle [frontend/assets/ts/core/collectionpage/revealLifecycle.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { releaseCollectionCardReveal, stageCollectionCardReveal } from '@core/collectionpage/cardReveal.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';

interface CollectionRevealDependencies {
    pageId: string;
    collections: PageCollections;
    layout: CollectionLayoutRuntime;
    isDestroyed(): boolean;
}

const prepareCollectionReveal = async (dependencies: CollectionRevealDependencies, section: HTMLElement | null, signal: AbortSignal | null): Promise<void> => {
    stageCollectionCardReveal(section, signal);
    if (signalAborted(signal) || dependencies.isDestroyed()) return;
    const view = dependencies.collections.view;
    if (!view) throw new Error(`${dependencies.pageId}: collectionView is required before collection reveal`);
    view.flushPendingRefresh();
    const grid = dependencies.layout.ensureGridElement();
    const committed = await view.awaitInitialCommit(signal);
    if (committed === false || signalAborted(signal) || dependencies.isDestroyed() || !grid.isConnected) return;
};

const releasePreparedCollection = (section: HTMLElement | null, signal: AbortSignal | null): void => {
    releaseCollectionCardReveal(section, signal);
};

export { prepareCollectionReveal, releasePreparedCollection };
export type { CollectionRevealDependencies };
