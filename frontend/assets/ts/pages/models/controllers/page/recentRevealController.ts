/* SoAI - Models page recent reveal controller [frontend/assets/ts/pages/models/controllers/page/recentRevealController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RecentItemTracker } from '@core/collectionpage/recentItemTracker.ts';
import { revealRecentCollectionItem } from '@core/collectionpage/recentItemReveal.ts';
import type { RefreshSummary } from '@core/collectionpage/publicContracts.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import type { PageCollectionsHost } from '@core/routing/pages/basepagecollections/PageCollections.ts';

interface ModelsRecentRevealHost extends PageCollectionsHost {
    getItemCardId(value: ResourceIncomingValue | null | undefined): string | null;
}

const handleModelsCollectionRefreshWithReveal = (host: ModelsRecentRevealHost, recentItems: RecentItemTracker, summary: RefreshSummary): RefreshSummary => {
    const collection = host.collections.runtime;
    if (!collection) {
        throw new Error('ModelsPage requires collection to be initialized');
    }
    const filteredModels = collection.getFiltered();
    const identifiers: string[] = [];
    for (const model of filteredModels) {
        const identifier = host.getItemCardId(model);
        if (identifier) {
            identifiers.push(identifier);
        }
    }
    revealRecentCollectionItem({
        recentItems,
        collectionView: host.collections.view,
        identifiers
    });
    return summary;
};

export { handleModelsCollectionRefreshWithReveal };
