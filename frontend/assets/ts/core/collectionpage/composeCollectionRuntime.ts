/* SoAI - Collection page data, layout, stream, and lifecycle composition [frontend/assets/ts/core/collectionpage/composeCollectionRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CollectionDataRuntime, type CollectionDataBehavior } from '@core/collectionpage/CollectionDataRuntime.ts';
import type { ResourceIncomingValue, ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import type { CollectionPresentationContext, RefreshContext } from '@core/data/collectionview/types.ts';
import type { BoundedCollectionCommitContext } from '@core/data/boundedcollectionrenderer/public.ts';
import { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';
import type { CollectionOptionsInternal } from '@core/routing/pages/pagetypes/public.ts';
import type { RawCollectionLayout } from '@core/routing/pages/collections/resource/types.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { CollectionPageState } from '@core/collectionpage/CollectionPageState.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';

interface CollectionCompositionConfig {
    collectionKey: string;
    collectionOptions: CollectionOptionsInternal;
    defaultSort: string;
    searchPlaceholder: string | null;
    checkerboardSelector: string;
}

interface CollectionCompositionOwners {
    pageDom: PageDom;
    pageResources: PageResources;
    streaming: PageStreaming;
    layout: PageLayout;
    services: PageServices;
    pageElements: PageUi;
    feedback: PageFeedback;
    storage: StorageService;
    pageHost: PageHost;
    pageLifecycle: PageLifecycle;
    createFragment(markup: TrustedHtml): DocumentFragment;
}

interface CollectionCompositionBehavior extends CollectionDataBehavior {
    defineLayout(): RawCollectionLayout;
    onSnapshot(snapshot: ResourceSnapshot): ResourceIncomingValue;
    preparePresentation?(context: CollectionPresentationContext): readonly string[];
    onRefresh(summary: RefreshContext): void;
    onCommit(context: BoundedCollectionCommitContext): void;
    renderItemCard(item: ResourceItem): HTMLElement;
    getItemSearchFields(item: ResourceItem): (string | undefined)[];
    applyCustomFilters(item: ResourceItem, filters: { filterProvider: string; filterStatus: string }): boolean;
    getSortValue(item: ResourceItem, field: string): string | number | null;
    updateStats(): void;
    updateFilters(): void;
    onFilterChange?(property: string, value: string): void;
}

interface CollectionCompositionDependencies {
    pageId: string;
    config: CollectionCompositionConfig;
    owners: CollectionCompositionOwners;
    behavior: CollectionCompositionBehavior;
    state: CollectionPageState;
}

interface CollectionRuntimeComposition {
    collections: PageCollections;
    data: CollectionDataRuntime;
    layout: CollectionLayoutRuntime;
    lifecycle: CollectionPageLifecycle;
}

const composeCollectionRuntime = (dependencies: CollectionCompositionDependencies): CollectionRuntimeComposition => {
    const { behavior, config, owners, pageId, state } = dependencies;
    const collections = new PageCollections(
        { pageId, pageDom: owners.pageDom, streaming: owners.streaming, pageLifecycle: owners.pageLifecycle },
        {
            get searchQuery() {
                return state.searchQuery;
            },
            get filterProvider() {
                return state.filterProvider;
            },
            get filterStatus() {
                return state.filterStatus;
            },
            get sortBy() {
                return state.sortBy;
            },
            get sortOrder() {
                return state.sortOrder;
            },
            onCollectionSnapshot: behavior.onSnapshot,
            prepareCollectionPresentation: behavior.preparePresentation,
            onCollectionRefresh: behavior.onRefresh,
            onCollectionCommit: behavior.onCommit,
            renderItemCard: behavior.renderItemCard,
            getItemSearchFields: behavior.getItemSearchFields,
            applyCustomFilters: behavior.applyCustomFilters,
            getSortValue: behavior.getSortValue,
            renderItems: behavior.renderItems,
            updateStats: behavior.updateStats,
            updateFilters: behavior.updateFilters
        }
    );
    const data = new CollectionDataRuntime({ pageId, storage: owners.storage, collections, streaming: owners.streaming, pageDom: owners.pageDom, feedback: owners.feedback, behavior });
    const pageHost = {
        get container() {
            return owners.pageHost.container;
        },
        get isDestroyed() {
            return owners.pageLifecycle.isDestroyed;
        },
        optionalHTMLElement: (selector: string, context?: Element) => owners.pageDom.optionalHTMLElement(selector, context),
        getRuntimeAbortSignal: () => owners.pageLifecycle.signal(),
        collections
    };
    const layout = new CollectionLayoutRuntime({
        pageId,
        config: { collectionKey: config.collectionKey, collectionOptions: config.collectionOptions, defaultSort: config.defaultSort, ...(config.searchPlaceholder ? { searchPlaceholder: config.searchPlaceholder } : {}) },
        host: pageHost,
        owners: { collections, streaming: owners.streaming, layout: owners.layout, services: owners.services, pageElements: owners.pageElements },
        pageDom: owners.pageDom,
        pageResources: owners.pageResources,
        builderPage: { pageId, dom: { createFragment: owners.createFragment } },
        resolveHostContainer: () => owners.pageHost.resolveContainer(),
        defineLayout: behavior.defineLayout,
        setSearchQuery: (query) => {
            state.searchQuery = query;
        },
        setFilterValue: (property, value) => {
            state.setFilterValue(property, value);
            behavior.onFilterChange?.(property, value);
        }
    });
    const lifecycle = new CollectionPageLifecycle({ pageId, layout, collections, pageLifecycle: owners.pageLifecycle }, { checkerboardSelector: config.checkerboardSelector });
    return { collections, data, layout, lifecycle };
};

export { composeCollectionRuntime };
export type { CollectionCompositionBehavior, CollectionCompositionConfig, CollectionCompositionDependencies, CollectionCompositionOwners, CollectionRuntimeComposition };
