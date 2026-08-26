/* SoAI - Prompts page domain runtime ownership [frontend/assets/ts/pages/prompts/controllers/page/PromptsPageRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ResourceIncomingValue, ResourceItem, ResourceSnapshot } from '@core/data/ClientDataHub.ts';
import { CollectionPageState } from '@core/collectionpage/CollectionPageState.ts';
import { armCollectionCardRevealTargetsForCommit } from '@core/collectionpage/cardReveal.ts';
import { composeCollectionRuntime, type CollectionCompositionBehavior } from '@core/collectionpage/composeCollectionRuntime.ts';
import { defaultCollectionDataBehavior, type CollectionDataRuntime } from '@core/collectionpage/CollectionDataRuntime.ts';
import { getDefaultCollectionItemCardId } from '@core/collectionpage/defaultBehavior.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { CollectionLayoutRuntime } from '@core/routing/pages/collections/resource/service.ts';
import type { CollectionPageLifecycle } from '@core/routing/pages/collections/pagelifecyclemanager/public.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { downloadFile } from '@core/primitives/download.ts';
import { requireSyntaxHighlighter } from '@core/syntaxhighlighter/public.ts';
import { ColorToolkit, isPromptRecord } from '@features/prompts/public.ts';
import { COLLECTION_OPTIONS, DEFAULT_SORT, PAGE_ID, PROMPT_CARD_SELECTOR } from '@pages/prompts/contracts/PromptsPageSupport.ts';
import { PromptEnhancerController } from '@pages/prompts/controllers/promptenhancer/service/PromptEnhancerController.ts';
import { createPromptsCardController, createPromptsCardHost, createPromptsColorToolkitHost, createPromptsPromptEnhancerHost } from '@pages/prompts/controllers/page/adapters.ts';
import type { PromptsRuntimeComponents, PromptsRuntimeContext, PromptsRuntimeControls, PromptsRuntimeOperations, PromptsRuntimeOwners } from '@pages/prompts/controllers/page/contracts.ts';
import { applyPromptsSortSelection, getPromptsListSortValue, hydratePromptsPageControls, sortPromptsListFromHeader } from '@pages/prompts/controllers/page/listSortingController.ts';
import { createPromptsSelectionManager } from '@pages/prompts/controllers/page/mappers.ts';
import { PromptsPageSession } from '@pages/prompts/controllers/page/PromptsPageSession.ts';
import { PromptsCollectionController } from '@pages/prompts/controllers/page/PromptsCollectionController.ts';
import { copyPromptContent } from '@pages/prompts/controllers/page/service.ts';
import { buildPromptDownloadEntry, buildSelectionDownloadFilename, ensureDataAdapter, ensureDataAdapterReady, normalizeCollectionPrompt, normalizeCollectionPromptId, toPromptResourceItem, upsertPromptRecord } from '@pages/prompts/controllers/page/state.ts';
import { applyPromptCustomFilters, getFilteredPromptIds, getPromptItemCardId, getPromptItemSearchFields, onCollectionRefresh, preparePromptPresentation, refreshPromptCards, renderItems, renderPromptItem, updateStats } from '@pages/prompts/controllers/page/view.ts';
import { createPromptsCollectionViewOverrides, togglePromptsViewMode } from '@pages/prompts/controllers/page/viewModeController.ts';
import { PromptCardRenderer } from '@pages/prompts/rendering/CardRenderer.ts';
import { PromptListRowRenderer } from '@pages/prompts/rendering/promptListRowWidget.ts';
import { hasPromptCardEditChanges, hasPromptModalEditChanges } from '@pages/prompts/controllers/page/saveDirtyStateManager.ts';
import { buildPromptsLayoutConfig } from '@pages/prompts/view.ts';
import { isPlainObject } from '@core/typeGuards.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { RefreshContext } from '@core/data/collectionview/service.ts';
import type { CollectionConfigurationOptions } from '@core/routing/pages/pagetypes/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { PROMPTS } from '@core/realtime/streammanager/resources/ids.ts';
import { consumeRepeatableDropdownSelection } from '@core/ui/dropdown/selectControl.ts';

interface PromptsPageRuntimeOptions {
    owners: Omit<PromptsRuntimeOwners, 'collections' | 'collectionLifecycle' | 'collectionLayout' | 'layout' | 'streaming'> & {
        pageHost: PageHost;
        layout: PageLayout;
        streaming: PageStreaming;
    };
}

class PromptsPageRuntime implements PromptsRuntimeContext {
    readonly state: PromptsPageSession;
    readonly owners: PromptsRuntimeOwners;
    readonly controls: PromptsRuntimeControls;
    readonly operations: PromptsRuntimeOperations;
    readonly components: PromptsRuntimeComponents;
    readonly collectionState: CollectionPageState;
    readonly collections: PageCollections;
    readonly collectionData: CollectionDataRuntime;
    readonly collectionLayout: CollectionLayoutRuntime;
    readonly collectionLifecycle: CollectionPageLifecycle;
    readonly #collectionBehavior: CollectionCompositionBehavior;
    #controlsHydrated = false;

    constructor({ owners }: PromptsPageRuntimeOptions) {
        this.state = new PromptsPageSession();
        this.collectionState = new CollectionPageState({ pageId: PAGE_ID, collectionKey: PROMPTS, collectionOptions: { ...COLLECTION_OPTIONS, normalize: normalizeCollectionPrompt }, defaultSort: DEFAULT_SORT });
        this.#collectionBehavior = this.#createCollectionBehavior();
        const collection = composeCollectionRuntime({
            pageId: PAGE_ID,
            config: {
                collectionKey: PROMPTS,
                collectionOptions: { ...COLLECTION_OPTIONS, normalize: normalizeCollectionPrompt },
                defaultSort: DEFAULT_SORT,
                searchPlaceholder: i18n.t('prompts.searchPlaceholder'),
                checkerboardSelector: PROMPT_CARD_SELECTOR
            },
            state: this.collectionState,
            owners: {
                pageDom: owners.pageDom,
                pageResources: owners.pageResources,
                streaming: owners.streaming,
                layout: owners.layout,
                services: owners.services,
                pageElements: owners.pageElements,
                feedback: owners.feedback,
                storage: owners.storage,
                pageHost: owners.pageHost,
                pageLifecycle: owners.pageLifecycle,
                createFragment: (markup) => owners.dom.createFragment(markup)
            },
            behavior: this.#collectionBehavior
        });
        this.collections = collection.collections;
        this.collectionData = collection.data;
        this.collectionLayout = collection.layout;
        this.collectionLifecycle = collection.lifecycle;
        this.owners = { ...owners, collections: this.collections, collectionLifecycle: this.collectionLifecycle, collectionLayout: this.collectionLayout };
        this.controls = new PromptsCollectionController(this.collectionState, owners.pageLifecycle, this.#collectionBehavior);
        this.operations = {
            requireUi: () => {
                if (!this.state.ui) throw new Error('Prompts UI is not initialized');
                return this.state.ui;
            },
            requirePromptRecord: (value) => {
                const jsonValue = value === null || value === undefined ? null : toJsonCompatibleValue(value);
                if (!isPromptRecord(jsonValue)) throw new TypeError('Prompt record is invalid');
                return jsonValue;
            },
            findPromptById: (id) => {
                const record = this.owners.collections.runtime?.find?.(String(id));
                if (record === null || record === undefined) return null;
                const value = toJsonCompatibleValue(record);
                return isPromptRecord(value) ? value : null;
            },
            upsertPromptRecord: (record) => upsertPromptRecord(this, record),
            upsertItem: (item) => this.collectionData.upsertItem(toPromptResourceItem(item)),
            ensureDataAdapter: () => ensureDataAdapter(this),
            ensureDataAdapterReady: () => ensureDataAdapterReady(this),
            getFilteredPromptIds: () => getFilteredPromptIds(this),
            renderItems: () => renderItems(this),
            updateStats: () => updateStats(this),
            updateFilters: () => {},
            reapplyCollection: (options) => this.collections.reapply(options),
            downloadTextFile: (content, filename, mimeType = 'text/plain') => downloadFile(content, filename, mimeType),
            copyPromptContent: (content) => copyPromptContent(this, content),
            removeItemById: (id) => this.collectionData.removeItemById(id),
            refreshPromptCards: (ids) => refreshPromptCards(this, ids),
            buildPromptDownloadEntry: (prompt) => buildPromptDownloadEntry(prompt),
            buildSelectionDownloadFilename: () => buildSelectionDownloadFilename(this),
            hasUnsavedChanges: () => hasPromptCardEditChanges(this) || hasPromptModalEditChanges(this),
            getItemCardId: (item: ResourceItem) => getPromptItemCardId(item),
            toggleViewMode: () => togglePromptsViewMode(this),
            sortList: (actionElement) => sortPromptsListFromHeader(this, actionElement)
        };
        const colorToolkit = new ColorToolkit(createPromptsColorToolkitHost(this.owners));
        const selectionController = createPromptsSelectionManager(this, (element: Element | undefined, visible: boolean): void => {
            if (!element) return;
            owners.pageDom.toggleClass(element, 'u-hidden', !visible);
            owners.pageDom.updateAttribute(element, 'aria-hidden', visible ? 'false' : 'true');
        });
        const promptEnhancer = new PromptEnhancerController({
            host: createPromptsPromptEnhancerHost(this),
            syntaxHighlighter: requireSyntaxHighlighter(),
            resources: owners.pageResources.tracker
        });
        const cardHost = createPromptsCardHost(this, colorToolkit);
        this.components = {
            colorToolkit,
            selectionController,
            promptEnhancer,
            cardRenderer: new PromptCardRenderer({ host: cardHost }),
            listRowRenderer: new PromptListRowRenderer({ host: cardHost })
        };
        ensureDataAdapter(this);
        this.state.cardController = createPromptsCardController(this, (item: ResourceIncomingValue) => normalizeCollectionPromptId(item));
    }

    getCollectionViewOverrides(): Partial<CollectionConfigurationOptions> {
        return createPromptsCollectionViewOverrides(this);
    }

    #createCollectionBehavior(): CollectionCompositionBehavior {
        return {
            defineLayout: () => {
                this.#hydrateControls();
                const config = buildPromptsLayoutConfig({
                    getIconSync: (iconName, options) => this.owners.services.getIconSync(iconName, options),
                    sortBy: this.controls.getSortBy() ?? 'none',
                    sortOrder: this.controls.getSortOrder() ?? 'asc',
                    onSortChange: (event) => this.#handleSortChange(event)
                });
                const built = this.collectionLayout.getLayoutBuilder().build(config);
                if (!isPlainObject(built)) throw new Error('Prompts layout builder returned invalid output');
                return built;
            },
            onSnapshot: (snapshot: ResourceSnapshot) => toJsonCompatibleValue(snapshot),
            preparePresentation: (context) =>
                preparePromptPresentation(
                    this,
                    context.filtered.map((item) => this.operations.requirePromptRecord(item))
                ),
            onRefresh: (summary: RefreshContext) => {
                onCollectionRefresh(this, summary);
            },
            onCommit: (context) => {
                armCollectionCardRevealTargetsForCommit(context.enteringElements);
                this.owners.pageElements.enableCheckerboard(context.container, PROMPT_CARD_SELECTOR, context.rangeStart);
                this.owners.layout.queueResponsive();
            },
            renderItemCard: (item) => renderPromptItem(this, item),
            getItemSearchFields: (item) => getPromptItemSearchFields(item),
            applyCustomFilters: () => applyPromptCustomFilters(),
            getSortValue: (item, field) => getPromptsListSortValue(item, field, this.components.colorToolkit),
            isValidItem: defaultCollectionDataBehavior.isValidItem,
            normalizeItem: (prompt) => normalizeCollectionPrompt(prompt),
            getItemCardId: (item) => getDefaultCollectionItemCardId(item),
            renderItems: () => this.operations.renderItems(),
            updateStats: () => this.operations.updateStats(),
            updateFilters: () => this.operations.updateFilters()
        };
    }

    #hydrateControls(): void {
        if (this.#controlsHydrated) return;
        hydratePromptsPageControls(this);
        this.#controlsHydrated = true;
    }

    #handleSortChange(event: Event): void {
        const target = event.target;
        if (!(target instanceof HTMLSelectElement)) throw new TypeError('Prompts sort change requires an HTMLSelectElement');
        applyPromptsSortSelection(this, consumeRepeatableDropdownSelection(target));
    }
}

export { PromptsPageRuntime };
export type { PromptsPageRuntimeOptions };
