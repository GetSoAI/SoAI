/* SoAI - Models page composition contracts [frontend/assets/ts/pages/models/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { RemoteModelSearchResult } from '@core/api/contracts/pluginSearchContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { CollectionItem, CollectionOperation } from '@core/collectionpage/types.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import type { PageControlsStorageInput } from '@core/pagecontrols/storageController.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { RouterInterface, WithLoadingOptions } from '@core/routing/pages/collections/resource/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { StreamActionHandle } from '@core/routing/pages/pagetypes/public.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import type { SetButtonLoadingOptions } from '@core/state/UIStateManager.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { StreamActionHandlers } from '@core/types/streamTypes.ts';
import type { ModelsPageSession } from '@pages/models/controllers/page/ModelsPageSession.ts';
import type { ModelsPluginCatalogController } from '@pages/models/controllers/page/ModelsPluginCatalogController.ts';
import type { SpeedTest } from '@pages/models/controllers/variantprobemanager/types.ts';

interface ModelsPageInitialActionContext {
    action: string;
    plugin?: string;
    vm?: string;
}

interface ModelsPageModelActions {
    delete(identifier: string, options?: { handlers?: StreamActionHandlers }): Promise<StreamActionHandle>;
    updateAlias(universalId: string, payload: { displayName: string; description: string | null }): Promise<SuccessfulMutationResponse>;
    removeAlias(universalId: string): Promise<SuccessfulMutationResponse>;
    searchRemoteModels(plugin: string, query: string, options?: { limit?: number; signal?: AbortSignal }): Promise<RemoteModelSearchResult[]>;
    probeModelVariants(plugin: string, modelId: string): Promise<ModelVariantResponse[]>;
    startDownload(request: { plugin?: string; modelId?: string; universalId?: string; quantization?: string; displayName?: string; modelName?: string }, options?: { handlers?: StreamActionHandlers }): Promise<StreamActionHandle>;
}

interface ModelsInfrastructure extends PageLayoutOwnerHost, PageStreamingOwnerHost, PageServicesOwnerHost, PageUiOwnerHost, PageLifecycleOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    pageId: string;
    sanitizer: SanitizerApi;
    auth: { isAdmin(): boolean };
    dom: {
        getData(element: Element, key: string): string | null;
        setData(element: Element, key: string, value: string): void;
        hasClass(element: Element, className: string): boolean;
        createFragment(html?: TrustedHtml): DocumentFragment;
        getDocument(): Document;
    };
    stateManager: {
        status: StatusManager;
        setButtonLoading(target: string | Element | null | undefined, loading: boolean, options?: SetButtonLoadingOptions): HTMLElement | null;
    };
    api: ApiClient;
    router: Router;
    storage: PageControlsStorageInput;
}

interface ModelsCollectionBindings {
    collections: PageCollections;
    collectionLifecycle: {
        withLoading<Value extends JsonValue | null>(task: () => Promise<Value>, options: WithLoadingOptions<Value>): Promise<Value>;
    };
    cancelDownload(key: string): void;
    removeItemById(id: string, options?: { emit?: boolean }): boolean | CollectionOperation[];
    initializeCollectionView(): void;
    setItemsFromList(items: readonly (ResourceIncomingValue | null | undefined)[]): CollectionItem[] | null;
    setItemsWithoutEmit(items: readonly (ResourceIncomingValue | null | undefined)[]): CollectionOperation[];
    upsertItemWithoutEmit(item: CollectionItem): CollectionOperation[];
    getContainer(): HTMLElement | null;
    isDestroyed(): boolean;
    renderItems(): void;
    getMetricBadgeType(element: Element): string | null;
    handleMetricBadgeNavigation(element: Element, item: ModelRecord, router: RouterInterface): boolean;
}

interface ModelsFilterBindings {
    getFilterProvider(): string;
    setFilterProvider(value: string): void;
    getFilterStatus(): string;
    setFilterStatus(value: string): void;
    getSortBy(): string;
    setSortBy(value: string): void;
    getSortOrder(): 'asc' | 'desc' | null;
    setSortOrder(value: 'asc' | 'desc' | null): void;
    getSearchQuery(): string;
    setSearchQuery(value: string): void;
}

interface ModelsRuntimeDependencies {
    session: ModelsPageSession;
    catalog: ModelsPluginCatalogController;
    infrastructure: ModelsInfrastructure;
    collection: ModelsCollectionBindings;
    filters: ModelsFilterBindings;
    modelActions: ModelsPageModelActions;
    speedTest: SpeedTest;
    log(level: 'debug' | 'info' | 'warn' | 'error', message: string, error?: Error): void;
}

type ModelsControllerRuntimeDependencies = Pick<ModelsRuntimeDependencies, 'session' | 'infrastructure' | 'collection' | 'filters' | 'modelActions' | 'log'>;
type ModelsLifecycleRuntimeDependencies = Pick<ModelsRuntimeDependencies, 'session' | 'catalog' | 'infrastructure' | 'collection' | 'filters'>;
type ModelsManagerRuntimeDependencies = Pick<ModelsRuntimeDependencies, 'session' | 'catalog' | 'infrastructure' | 'collection' | 'modelActions' | 'speedTest' | 'log'>;
type ModelsModalRuntimeDependencies = Pick<ModelsRuntimeDependencies, 'session' | 'catalog' | 'infrastructure' | 'collection' | 'modelActions' | 'log'>;
type ModelsViewRuntimeDependencies = Pick<ModelsRuntimeDependencies, 'session' | 'infrastructure' | 'collection' | 'filters'>;

export type { ModelsCollectionBindings, ModelsControllerRuntimeDependencies, ModelsFilterBindings, ModelsInfrastructure, ModelsLifecycleRuntimeDependencies, ModelsManagerRuntimeDependencies, ModelsModalRuntimeDependencies, ModelsPageInitialActionContext, ModelsPageModelActions, ModelsRuntimeDependencies, ModelsViewRuntimeDependencies, ResourceItem };
