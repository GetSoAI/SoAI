/* SoAI - Prompts page ownership and domain contracts [frontend/assets/ts/pages/prompts/controllers/page/contracts.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ApiClient } from '@core/api/service.ts';
import type { ResourceIncomingValue, ResourceItem } from '@core/data/ClientDataHub.ts';
import type { PageCollectionsContract } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedbackOwnerHost } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResourcesOwnerHost } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServicesOwnerHost } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUiOwnerHost } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayoutOwnerHost } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreamingOwnerHost } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageLifecycleOwnerHost } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { dom } from '@core/dom/dom.ts';
import type { ColorToolkit, PromptRecord } from '@features/prompts/public.ts';
import type { PromptEnhancerController } from '@pages/prompts/controllers/promptenhancer/service/PromptEnhancerController.ts';
import type { SelectionManager } from '@pages/prompts/controllers/SelectionManager.ts';
import type { PromptsPageSession } from '@pages/prompts/controllers/page/PromptsPageSession.ts';
import type { PromptCardRenderer } from '@pages/prompts/rendering/CardRenderer.ts';
import type { PromptListRowRenderer } from '@pages/prompts/rendering/promptListRowWidget.ts';
import type { PromptDataAdapter } from '@pages/prompts/services/service.ts';
import type { PromptsUiRefs } from '@pages/prompts/types.ts';

interface PromptsRuntimeOwners extends PageLayoutOwnerHost, PageStreamingOwnerHost, PageServicesOwnerHost, PageUiOwnerHost, PageLifecycleOwnerHost, PageDomOwnerHost, PageResourcesOwnerHost, PageFeedbackOwnerHost {
    dom: typeof dom;
    api: ApiClient;
    storage: StorageService;
    collections: PageCollectionsContract;
    collectionLifecycle: CollectionPageLifecycle;
    collectionLayout: CollectionLayoutRuntime;
}

interface PromptsRuntimeComponents {
    colorToolkit: ColorToolkit;
    selectionController: SelectionManager;
    promptEnhancer: PromptEnhancerController;
    cardRenderer: PromptCardRenderer;
    listRowRenderer: PromptListRowRenderer;
}

interface PromptsRuntimeControls {
    getSortBy(): string | null;
    setSortBy(value: string): void;
    getSortOrder(): 'asc' | 'desc' | null;
    setSortOrder(value: 'asc' | 'desc' | null): void;
    getSearchQuery(): string | null;
    setSearchQuery(value: string): void;
    isDestroyed(): boolean;
    getCollectionFilter(): (item: ResourceItem) => boolean;
}

interface PromptsRuntimeOperations {
    requireUi(): PromptsUiRefs;
    requirePromptRecord(value: ResourceIncomingValue | null | undefined): PromptRecord;
    findPromptById(id: string | number): PromptRecord | null;
    upsertPromptRecord(record: PromptRecord | null): PromptRecord | null;
    upsertItem(item: PromptRecord): void;
    ensureDataAdapter(): PromptDataAdapter;
    ensureDataAdapterReady(): Promise<PromptDataAdapter>;
    getFilteredPromptIds(): readonly string[];
    renderItems(): void;
    updateStats(): void;
    updateFilters(): void;
    reapplyCollection(options?: { shouldRender?: boolean; updateStats?: boolean; updateFilters?: boolean; resetScroll?: boolean }): void;
    downloadTextFile(content: string, filename: string, mimeType?: string): void;
    copyPromptContent(content: string | null | undefined): Promise<void>;
    removeItemById(id: string): void;
    refreshPromptCards(ids?: readonly (string | number)[] | null): void;
    buildPromptDownloadEntry(prompt: PromptRecord): string;
    buildSelectionDownloadFilename(): string;
    hasUnsavedChanges(): boolean;
    getItemCardId(item: ResourceItem | PromptRecord): string;
    toggleViewMode(): void;
    sortList(actionElement: HTMLElement): void;
}

interface PromptsRuntimeCore {
    state: PromptsPageSession;
    owners: PromptsRuntimeOwners;
    controls: PromptsRuntimeControls;
    operations: PromptsRuntimeOperations;
}

interface PromptsRuntimeContext extends PromptsRuntimeCore {
    components: PromptsRuntimeComponents;
}

type PromptsPageEventsHost = PromptsRuntimeContext;

export type { PromptsPageEventsHost, PromptsRuntimeComponents, PromptsRuntimeContext, PromptsRuntimeControls, PromptsRuntimeCore, PromptsRuntimeOperations, PromptsRuntimeOwners };
