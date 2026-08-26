/* SoAI - Plugins page composition contracts [frontend/assets/ts/pages/plugins/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { HardwareSnapshotOptions } from '@core/api/types/hardware.ts';
import type { AcceptedPowerActionResponse } from '@core/api/contracts/powerContracts.ts';
import type { ConfigUpdateResponse } from '@core/api/contracts/configContracts.ts';
import type { BackendVariantsResponse, PluginBackendUpdatesResponse, PluginCompatibilityOverrideResponse } from '@core/api/contracts/pluginManagementContracts.ts';
import type { ManualInstallPathResponse } from '@core/api/contracts/manualInstallPathContracts.ts';
import type { SuccessfulMutationResponse } from '@core/api/contracts/successfulMutationContract.ts';
import type { ApiResponsePayload } from '@core/api/types/payload.ts';
import type { ApiRequestBody } from '@core/api/types/request.ts';
import type { ResourceIncomingValue, ResourceItem, ResourceOperation } from '@core/data/ClientDataHub.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { StatusManager } from '@core/state/statusmanager/service.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import { hasFunctionProperties, isObject } from '@core/typeGuards.ts';
import type { SystemInfoResponse } from '@core/api/contracts/systemContracts.ts';
import type { HardwareSnapshotResponse } from '@core/api/contracts/hardwareContracts.ts';
import type { CatalogSubscriptionManager } from '@features/catalog/public.ts';
import type { ConfigurationManager, PluginsManagerHostCallbacks } from '@features/plugins/public.ts';
import type { PluginsPageControllerSet, PluginsPageModalManagers } from '@pages/plugins/controllers/contracts.ts';
import type { PluginsLifecycleController } from '@pages/plugins/controllers/lifecycleController.ts';
import type { PluginsOperationsController } from '@pages/plugins/controllers/operationsController.ts';
import type { PluginsProgressController } from '@pages/plugins/controllers/progressController.ts';
import type { PluginsPageSession } from '@pages/plugins/controllers/page/PluginsPageSession.ts';
import type { PluginCardRenderer } from '@pages/plugins/rendering/cardrenderer/service.ts';
import type { PluginsPageDependencies } from '@pages/plugins/types.ts';
import type { CardPageController } from '@core/routing/pages/collections/cardgridpage/public.ts';

interface PluginsApi {
    post(path: string, body?: ApiRequestBody): Promise<ApiResponsePayload>;
    uploadFile(url: string, file: File): Promise<ApiResponsePayload>;
    configs: { get(name: string): Promise<JsonObject>; update(name: string, data: JsonValue): Promise<ConfigUpdateResponse> };
    hardware: { snapshot(options?: HardwareSnapshotOptions): Promise<HardwareSnapshotResponse> };
    plugins: {
        checkUpdates(): Promise<PluginBackendUpdatesResponse>;
        getBackendVariants(pluginName: string): Promise<BackendVariantsResponse>;
        manualInstall(): Promise<ManualInstallPathResponse>;
        overrideIncompatibility(pluginName: string, override: boolean): Promise<PluginCompatibilityOverrideResponse>;
        saveBackendVariantSelection(pluginName: string, variantId: string): Promise<BackendVariantsResponse>;
    };
    system: {
        info(): Promise<SystemInfoResponse>;
        resetCircuitBreaker(pluginName: string): Promise<SuccessfulMutationResponse>;
        power?: { restartApplication?: () => Promise<AcceptedPowerActionResponse> };
    };
}

interface PluginsInfrastructure extends PageDomOwnerHost, PageFeedbackOwnerHost, PageResourcesOwnerHost, PageServicesOwnerHost, PageUiOwnerHost, PageLayoutOwnerHost, PageStreamingOwnerHost {
    api: PluginsApi;
    auth: { isAdmin(): boolean };
    router: Router;
    dom: {
        createFragment(markup: TrustedHtml): DocumentFragment;
        getData(element: Element, key: string): string | null;
        setData(element: Element, key: string, value: string): void;
    };
    stateManager: { status: StatusManager };
    sanitizer: { text(value: JsonValue | null | undefined, options?: { allowEmpty?: boolean }): string };
}

interface PluginsCollectionBindings {
    collections: PageCollections;
    collectionLifecycle: Pick<CollectionPageLifecycle, 'withLoading'>;
    cancelDownload(key: string): void;
    removeItemById(identifier: string): void;
    setItemsFromList(items: ReadonlyArray<ResourceIncomingValue | null | undefined>): ResourceItem[] | null;
    setItemsWithoutEmit(items: ReadonlyArray<ResourceIncomingValue | null | undefined>): ResourceOperation[];
    upsertItemWithoutEmit(item: ResourceItem): ResourceOperation[];
    isDestroyed(): boolean;
}

interface PluginsFilterBindings {
    getFilterProvider(): string;
    setFilterProvider(value: string): void;
    getFilterStatus(): string;
    setFilterStatus(value: string): void;
    getSortBy(): string | null;
    setSortBy(value: string | null): void;
    getSortOrder(): 'asc' | 'desc' | null;
    setSortOrder(value: 'asc' | 'desc' | null): void;
    setSearchQuery(value: string): void;
}

interface CreatePluginsPageRuntimeDependencies {
    session: PluginsPageSession;
    pageDependencies: PluginsPageDependencies;
    infrastructure: PluginsInfrastructure;
    collection: PluginsCollectionBindings;
    filters: PluginsFilterBindings;
    runBoundary<T>(scope: string, task: () => Promise<T> | T): Promise<T>;
}

interface PluginsPagePrimaryRuntime {
    coreControllers: Pick<PluginsPageControllerSet, 'compatibilityController' | 'dataController' | 'collectionController' | 'statsController' | 'taskActionController'>;
    modalManagers: PluginsPageModalManagers;
    progressController: PluginsProgressController;
    catalogSubscriptions: CatalogSubscriptionManager;
    cardRenderer: PluginCardRenderer;
    cardController: CardPageController;
    managerHostCallbacks: PluginsManagerHostCallbacks;
}

interface PluginsControllerResolvers {
    getOperationsController(): PluginsOperationsController | null;
    getLifecycleController(): PluginsLifecycleController | null;
}

const isConfigurationManager = <Candidate>(candidate: Candidate): candidate is Candidate & ConfigurationManager => {
    if (!isObject(candidate)) return false;
    return hasFunctionProperties(candidate, ['initialize', 'onChange', 'getValue', 'updateValue', 'commitChanges']);
};

export { isConfigurationManager };
export type { CreatePluginsPageRuntimeDependencies, PluginsCollectionBindings, PluginsControllerResolvers, PluginsFilterBindings, PluginsInfrastructure, PluginsPagePrimaryRuntime };
