/* SoAI - Shared collection page recent item reveal [frontend/assets/ts/core/collectionpage/recentItemReveal.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';

interface RecentItemRevealTracker {
    resolveRevealIdentifiers(orderedIdentifiers: readonly string[]): string[];
    consumeRevealIdentifiers(orderedIdentifiers: readonly string[]): string[];
}

interface RecentItemRevealView {
    revealItem(identifier: string): Promise<boolean>;
}

const revealRecentCollectionItem = (options: { recentItems: RecentItemRevealTracker; collectionView: RecentItemRevealView | null | undefined; identifiers: readonly string[] }): void => {
    const revealIdentifiers = options.recentItems.resolveRevealIdentifiers(options.identifiers);
    if (revealIdentifiers.length <= 0) {
        return;
    }
    const targetIdentifier = revealIdentifiers[Math.floor((revealIdentifiers.length - 1) / 2)] ?? null;
    if (!targetIdentifier) {
        return;
    }
    const reveal = options.collectionView?.revealItem(targetIdentifier);
    if (reveal === undefined) return;
    terminateHandledPromise(
        reveal.then((revealed) => {
            if (revealed) options.recentItems.consumeRevealIdentifiers(revealIdentifiers);
        })
    );
};

export { revealRecentCollectionItem };
