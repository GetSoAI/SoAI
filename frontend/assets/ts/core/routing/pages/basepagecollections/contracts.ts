/* SoAI - Shared routing base page collections contracts [frontend/assets/ts/core/routing/pages/basepagecollections/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import type { CollectionRuntime } from '@core/routing/pages/pagetypes/public.ts';
import type { CollectionPresentationContext, RefreshContext } from '@core/data/collectionview/types.ts';
import type { BoundedCollectionCommitContext } from '@core/data/boundedcollectionrenderer/public.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';

interface BasePageCollectionsStorageContract {
    get: (key: string, defaultValue?: JsonValue | null) => JsonValue | null;
    set: (key: string, value: JsonValue | null) => void;
}

interface BasePageCollectionsCollectionViewContract {
    dispose?: () => void;
    getCollectionRuntime: () => CollectionRuntime;
    replaceLocal?: (items: ResourceItem[]) => void;
    revealItem?: (id: string) => Promise<boolean>;
    rebuildForViewMode?: () => void;
    flushPendingRefresh: () => void;
    awaitInitialCommit: (signal: AbortSignal | null) => Promise<boolean>;
    markDirty?: (ids?: string[]) => void;
    refresh?: (options?: Record<string, ResourceIncomingValue>) => void;
}

interface BasePageCollectionsFilterSortContract {
    searchQuery?: string | null;
    filterProvider?: string | null;
    filterStatus?: string | null;
    sortBy?: string | null;
    sortOrder?: 'asc' | 'desc' | null;
}

interface PageCollectionsDependencies {
    pageId: string;
    pageDom: PageDom;
    streaming: PageStreaming;
    pageLifecycle: { readonly isDestroyed: boolean };
}

interface PageCollectionBehavior extends BasePageCollectionsFilterSortContract {
    onCollectionSnapshot?: ((snapshot: ResourceSnapshot) => ResourceIncomingValue) | undefined;
    prepareCollectionPresentation?: ((context: CollectionPresentationContext) => readonly string[]) | undefined;
    onCollectionRefresh?: ((snapshot: RefreshContext) => void) | undefined;
    onCollectionCommit?: ((context: BoundedCollectionCommitContext) => void) | undefined;
    renderItem?: ((item: ResourceItem, context?: ResourceIncomingValue) => HTMLElement) | undefined;
    renderItemCard?: ((item: ResourceItem, context?: ResourceIncomingValue) => HTMLElement) | undefined;
    getItemSearchFields?: ((item: ResourceItem) => (string | undefined)[]) | undefined;
    applyCustomFilters?: ((item: ResourceItem, context: { filterProvider: string; filterStatus: string }) => boolean) | undefined;
    getSortValue?: ((item: ResourceItem, field: string) => string | number | null) | undefined;
    renderItems?: (() => void) | undefined;
    updateStats?: (() => void) | undefined;
    updateFilters?: (() => void) | undefined;
}

export type { BasePageCollectionsCollectionViewContract, BasePageCollectionsStorageContract, PageCollectionBehavior, PageCollectionsDependencies };
