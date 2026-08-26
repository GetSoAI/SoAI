/* SoAI - Collection layout, readiness, search, filters, and event ownership [frontend/assets/ts/core/routing/pages/collections/resource/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { CollectionResourceOwners } from '@core/collectionpage/ownership.ts';
import { setupStandardFiltersAction, setupStandardSearchAction } from '@core/collectionpage/actions.ts';
import { i18n } from '@core/i18n/index.ts';
import { bindActionHandlers, bindDelegatedHandlers } from '@core/routing/pages/collections/actions.ts';
import { getMetricBadgeType, handleMetricBadgeNavigation, isMetricBadgeClick } from '@core/routing/pages/collections/resource/events.ts';
import { DEFAULT_GRID_WAIT_TIMEOUT_MS, DEFAULT_LOADING_WAIT_TIMEOUT_MS } from '@core/routing/pages/collections/resource/constants.ts';
import { getEmptyStateElement, getFilterBindings, getGridElement, getLoadingTargetElement, resolveEmptyStateId, resolveGridId } from '@core/routing/pages/collections/resource/dom.ts';
import { createCollectionLayoutState, resolveCollectionConfig, resolveCollectionLayout, resolveWaitBudget, waitForLayoutElement } from '@core/routing/pages/collections/resource/state.ts';
import { withLoading } from '@core/routing/pages/collections/resource/actions.ts';
import type { ActionHandlerConfig, DelegatedHandlerConfig, ManagerConfig, RawCollectionLayout, ResolvedCollectionLayout } from '@core/routing/pages/collections/types.ts';
import type { CollectionConfig, CollectionLayoutState, HostInterface, LayoutElements, ModelInterface, RouterInterface, WaitOptions, WithLoadingOptions } from '@core/routing/pages/collections/resource/types.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { composeCollectionLayout } from '@core/routing/pages/collections/view.ts';
import { createCollectionBuilder, type CollectionLayoutBuilder } from '@core/ui/collectionLayoutPrimitives.ts';
import { isString } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import type { PageInstance } from '@core/uiprimitives/types.ts';

interface CollectionLayoutDependencies {
    pageId: string;
    config: ManagerConfig;
    host: HostInterface;
    owners: CollectionResourceOwners;
    pageDom: PageDom;
    pageResources: PageResources;
    builderPage: PageInstance;
    resolveHostContainer(): HTMLElement;
    defineLayout(): RawCollectionLayout;
    setSearchQuery(query: string): void;
    setFilterValue(property: string, value: string): void;
}

class CollectionLayoutRuntime {
    readonly #dependencies: CollectionLayoutDependencies;
    readonly #layoutState: CollectionLayoutState = createCollectionLayoutState();
    readonly #searchPlaceholder: string;
    #layoutBuilder: CollectionLayoutBuilder | null = null;

    constructor(dependencies: CollectionLayoutDependencies) {
        this.#dependencies = dependencies;
        const configured = dependencies.config.searchPlaceholder;
        this.#searchPlaceholder = isString(configured) && configured.trim() ? configured.trim() : i18n.t('header.search.placeholder');
    }

    invalidateLayout(): void {
        this.#layoutState.value = null;
    }

    getSearchPlaceholder(): string {
        return this.#searchPlaceholder;
    }

    getLayoutBuilder(): CollectionLayoutBuilder {
        this.#layoutBuilder ??= createCollectionBuilder(this.#dependencies.builderPage);
        return this.#layoutBuilder;
    }

    getLayout(): ResolvedCollectionLayout {
        return resolveCollectionLayout(this.#dependencies.pageId, this.#layoutState, this.#dependencies.defineLayout, null);
    }

    async render(): Promise<TrustedHtml> {
        await this.#dependencies.owners.services.ensureLanguageInitialized();
        this.invalidateLayout();
        const layout = this.getLayout();
        if (!layout.header) throw new Error(`${this.#dependencies.pageId} collection layout header is required`);
        return composeCollectionLayout(this.#dependencies.pageId, (options) => this.#dependencies.owners.layout.generateHeader(options), {
            headerConfig: layout.header,
            content: layout.content
        });
    }

    getCollectionConfig(): CollectionConfig | null {
        return resolveCollectionConfig(this.#dependencies.host);
    }

    getGridId(): string | null {
        return resolveGridId(this.#dependencies.pageId, this.#dependencies.host);
    }

    getEmptyStateId(): string | null {
        return resolveEmptyStateId(this.#dependencies.pageId, this.#dependencies.host);
    }

    getGridElement(): HTMLElement | null {
        return getGridElement(this.#dependencies.pageId, this.#dependencies.host);
    }

    getEmptyStateElement(): HTMLElement | null {
        return getEmptyStateElement(this.#dependencies.pageId, this.#dependencies.host);
    }

    ensureGridElement(): HTMLElement {
        const grid = this.getGridElement();
        if (!grid) throw new Error(`${this.#dependencies.pageId} requires ${this.getGridId() || 'collection grid'} to be present before continuing`);
        return grid;
    }

    async waitForGridElement(options: WaitOptions = {}): Promise<HTMLElement> {
        const identifier = this.getGridId() || 'collection grid';
        const budget = resolveWaitBudget(this.#dependencies.host, options, DEFAULT_GRID_WAIT_TIMEOUT_MS);
        return waitForLayoutElement(this.#dependencies.pageId, this.#dependencies.host, () => this.getGridElement(), identifier, budget);
    }

    async ensureLayoutReady(options: WaitOptions = {}): Promise<LayoutElements> {
        return { grid: await this.waitForGridElement(options), emptyState: this.getEmptyStateElement() };
    }

    getLoadingTargetElement(): HTMLElement {
        return getLoadingTargetElement(this.#dependencies.pageId, this.#dependencies.host);
    }

    async waitForLoadingElement(options: WaitOptions = {}): Promise<HTMLElement> {
        const identifier = this.getGridId() || this.getEmptyStateId() || 'collection loading surface';
        const budget = resolveWaitBudget(this.#dependencies.host, options, DEFAULT_LOADING_WAIT_TIMEOUT_MS);
        return waitForLayoutElement(this.#dependencies.pageId, this.#dependencies.host, () => this.getLoadingTargetElement(), identifier, budget);
    }

    async withLoading<T extends JsonValue | null>(task: () => Promise<T>, options: WithLoadingOptions<T> = {}): Promise<T | null> {
        return withLoading(
            {
                pageId: this.#dependencies.pageId,
                waitForLoadingElement: (waitOptions = {}) => this.waitForLoadingElement(waitOptions),
                runPageTask: (taskName, operation, runOptions) => this.#dependencies.owners.streaming.runTask(taskName, operation, runOptions)
            },
            task,
            options
        );
    }

    async enableGridCheckerboard(itemSelector: string, options: WaitOptions = {}): Promise<HTMLElement> {
        const grid = await this.waitForGridElement(options);
        this.#dependencies.owners.pageElements.enableCheckerboard(grid, itemSelector);
        return grid;
    }

    setupEventListeners(): void {
        this.#dependencies.pageDom.flush();
        if (this.#hasSearchContainer()) {
            setupStandardSearchAction(
                {
                    pageId: this.#dependencies.pageId,
                    createStandardSearch: (containerId, options) => this.#dependencies.owners.layout.createSearch(containerId, options),
                    setSearchQuery: (query) => this.#dependencies.setSearchQuery(query),
                    reapplyCollection: (options) => this.#dependencies.owners.collections.reapply(options)
                },
                `${this.#dependencies.pageId}-search-container`,
                { placeholder: this.#searchPlaceholder }
            );
        }
        const filters = getFilterBindings(this.getLayout());
        if (filters && Object.keys(filters).length > 0) {
            setupStandardFiltersAction(
                {
                    pageId: this.#dependencies.pageId,
                    queryElements: (selector) => this.#dependencies.pageDom.query(selector),
                    bindEvent: (target, event, handler) => {
                        this.#dependencies.pageResources.on(target, event, handler);
                    },
                    setFilterValue: (property, value) => this.#dependencies.setFilterValue(property, value),
                    reapplyCollection: (options) => this.#dependencies.owners.collections.reapply(options)
                },
                { filters }
            );
        }
        const bindingContext = {
            resolveHostContainer: () => this.#dependencies.resolveHostContainer(),
            query: (selector: string, context?: Element | Document | null) => this.#dependencies.pageDom.query(selector, context),
            on: (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => this.#dependencies.pageResources.on(target, event, handler, options)
        };
        bindActionHandlers(bindingContext, this.getActionHandlers());
        bindDelegatedHandlers(bindingContext, this.getDelegatedHandlers());
        this.#dependencies.owners.layout.queueHeaderActions();
    }

    getActionHandlers(): ActionHandlerConfig[] {
        return this.getLayout().actions;
    }

    getDelegatedHandlers(): DelegatedHandlerConfig[] {
        return this.getLayout().delegated;
    }

    getMetricBadgeType(element: Element | null): string | null {
        return getMetricBadgeType(element);
    }

    isMetricBadgeClick(element: Element | null, targetType: string): boolean {
        return isMetricBadgeClick(element, targetType);
    }

    handleMetricBadgeNavigation(element: Element | null, model: ModelInterface, router: RouterInterface | null): boolean {
        return handleMetricBadgeNavigation(element, model, router);
    }

    #hasSearchContainer(): boolean {
        return this.getLayout().headerMetadata?.searchEnabled !== false;
    }
}

export { CollectionLayoutRuntime };
export type { CollectionLayoutDependencies };
