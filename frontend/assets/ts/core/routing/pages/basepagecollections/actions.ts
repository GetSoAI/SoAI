/* SoAI - Shared routing base page collections actions [frontend/assets/ts/core/routing/pages/basepagecollections/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { err } from '@core/routing/pages/basepagecore/actions.ts';
import type { BasePageCollectionsState } from '@core/routing/pages/basepagecollections/state.ts';
import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';

const setCollectionConfiguration = (state: BasePageCollectionsState, pageId: string, config: CollectionConfigurationOptions): void => {
    state.collectionConfig = {
        ...state.collectionConfig,
        ...config,
        gridId: config.gridId || `${pageId}-grid`,
        emptyStateId: config.emptyStateId || `${pageId}-empty`
    };
};

const hasCollectionConfiguration = (state: BasePageCollectionsState): boolean => {
    return Boolean(state.collectionConfig?.collectionKey?.trim());
};

const getCollectionConfiguration = (state: BasePageCollectionsState): CollectionConfigurationOptions | null => {
    return state.collectionConfig ? { ...state.collectionConfig } : null;
};

const getCollectionKey = (state: BasePageCollectionsState): string => {
    const collectionKey = state.collectionConfig?.collectionKey?.trim();
    if (!collectionKey) {
        throw err('Collection key missing');
    }
    return collectionKey;
};

export { hasCollectionConfiguration, getCollectionConfiguration, getCollectionKey, setCollectionConfiguration };
