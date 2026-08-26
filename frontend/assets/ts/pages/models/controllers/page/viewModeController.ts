/* SoAI - Models page view mode controller [frontend/assets/ts/pages/models/controllers/page/viewModeController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { renderCollectionGroupEntry } from '@core/collectionpage/collectionGroupEntry.ts';
import type { CollectionGroupingState } from '@core/collectionpage/collectionGroupingState.ts';
import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { ResourceIncomingValue } from '@core/data/ClientDataHub.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ModelData, ModelRecord } from '@core/types/modelTypes.ts';
import { createCollectionDisplayModeOverrides, initializeCollectionDisplayModeControllerWithList, renderCollectionDisplayModeElement, resolveInitialCollectionDisplayMode, toggleCollectionDisplayMode, type CollectionDisplayMode, type CollectionDisplayModeHost } from '@core/uiprimitives/viewmode/public.ts';
import { isModelData, normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';
import { syncModelsListSortIndicators, type ModelsListSortHost } from '@pages/models/controllers/page/listSortingController.ts';
import type { ModelsUiRefs } from '@pages/models/types.ts';
import type { PageCollectionsHost } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

const MODELS_VIEW_MODE_STORAGE_KEY = 'soai.models.viewMode';
const MODELS_CARD_IDENTITY_ATTRIBUTE = 'data-model';

interface ModelsViewModeHost extends CollectionDisplayModeHost, ModelsListSortHost, PageCollectionsHost, PageLayoutOwnerHost, PageDomOwnerHost {
    cardRenderer: {
        render: (model: ModelData | null) => Element | null;
        renderListRow: (model: ModelData | null) => HTMLElement | null;
    };
    grouping: CollectionGroupingState<ModelRecord>;
    getItemCardId: (item: ResourceIncomingValue | null | undefined) => string | null;
}

const resolveInitialModelsViewMode = (): CollectionDisplayMode => resolveInitialCollectionDisplayMode(MODELS_VIEW_MODE_STORAGE_KEY);

const initializeModelsViewMode = (host: ModelsViewModeHost, ui: ModelsUiRefs): void => {
    initializeCollectionDisplayModeControllerWithList(host, ui, {
        storageKey: MODELS_VIEW_MODE_STORAGE_KEY,
        context: 'Models',
        prepareCollectionViewModeChange: () => {
            const collection = host.collections.runtime;
            if (!collection) throw new Error('Models collection is unavailable for view mode preparation');
            collection.prepareForViewModeChange();
        },
        reapplyCollection: () => {
            const collection = host.collections.runtime;
            if (!collection) throw new Error('Models collection is unavailable for view mode rebuild');
            collection.rebuildForViewMode();
        },
        syncSortIndicators: (table) => syncModelsListSortIndicators(host, table)
    });
};

const toggleModelsViewMode = (host: ModelsViewModeHost): void => {
    toggleCollectionDisplayMode(host, 'Models');
};

const createModelsCollectionViewOverrides = (host: ModelsViewModeHost): Partial<CollectionConfigurationOptions> => ({
    ...createCollectionDisplayModeOverrides(host, {
        gridSelector: '#models-grid',
        listSelector: '#models-list-body',
        itemDataKey: 'model'
    }),
    loadingLabel: () => i18n.t('models.loading.moreModels')
});

const renderModelsItemForViewMode = (host: ModelsViewModeHost, model: ResourceIncomingValue | null | undefined): HTMLElement => {
    const normalized = normalizeModelRecordStrict(model, 'ModelsPage.viewModeRender');
    if (!isModelData(normalized)) {
        throw new Error('Models list view requires model data');
    }
    const element = renderCollectionDisplayModeElement({
        viewMode: host.viewMode,
        item: normalized,
        context: 'Models',
        renderCard: (item) => host.cardRenderer.render(item),
        renderListRow: (item) => host.cardRenderer.renderListRow(item)
    });
    if (!(element instanceof HTMLElement)) throw new Error('Models rendered element must be an HTMLElement');
    if (host.viewMode === 'list') return element;
    const modelId = host.getItemCardId(normalized);
    return renderCollectionGroupEntry({ card: element, heading: modelId ? host.grouping.headingFor(modelId) : null, identityAttribute: MODELS_CARD_IDENTITY_ATTRIBUTE });
};

export { createModelsCollectionViewOverrides, initializeModelsViewMode, resolveInitialModelsViewMode, renderModelsItemForViewMode, toggleModelsViewMode };
export type { ModelsViewModeHost };
