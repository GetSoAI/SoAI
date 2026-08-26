/* SoAI - Shared routing base page collections state [frontend/assets/ts/core/routing/pages/basepagecollections/state.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionConfigurationOptions, CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import type { CollectionView } from '@core/data/collectionview/service.ts';

interface BasePageCollectionsState {
    collectionConfig: CollectionConfigurationOptions | null;
    collection: CollectionRuntime | null;
    collectionView: CollectionView | null;
}

const createBasePageCollectionsState = (): BasePageCollectionsState => ({
    collectionConfig: null,
    collection: null,
    collectionView: null
});

export type { BasePageCollectionsState };
export { createBasePageCollectionsState };
