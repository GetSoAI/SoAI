/* SoAI - Routed page responsive layout, header actions, tabs, and search ownership [frontend/assets/ts/core/routing/pages/basepagelayout/PageLayout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DOMTarget } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { attachViewportResize, createStandardSearch, getTabsComponent, initializeTabs, registerUnsavedChangesProtection, updateGridPosition } from '@core/routing/pages/basepagelayout/actions.ts';
import { cleanupBasePageLayoutTransientState } from '@core/routing/pages/basepagelayout/cleanup.ts';
import type { BasePageLayoutHost } from '@core/routing/pages/basepagelayout/contracts.ts';
import { attachExternalLinkConfirmation, bindHeaderActionMenu, bindPrefixedHeaderSelects, updatePageActionsMenuState, type HeaderActionMenuHost } from '@core/routing/pages/basepagelayout/effects.ts';
import { refreshHeaderActionsLayout } from '@core/routing/pages/basepagelayout/dom.ts';
import { createLayoutHeaderActionMenuCallbacks, queueLayoutHeaderActionsLayoutUpdate, queueLayoutHeaderActionsLayoutUpdateForMutation, resolveLayoutHeaderActionContext, resolveLayoutHeaderActionsRoot } from '@core/routing/pages/basepagelayout/headerActions.ts';
import { updateHeaderStatCard } from '@core/routing/pages/basepagelayout/headerStats.ts';
import { applyHeaderStatsLayoutNow, cleanupLayoutState, queueResponsiveLayoutUpdate, setupHeaderStatsLayout, setupResponsiveLayout, updateResponsiveLayout, type ResponsiveLayoutCallbacks } from '@core/routing/pages/basepagelayout/layout.ts';
import { createBasePageLayoutState, type BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';
import { attachHeaderAnimator, onHide } from '@core/routing/pages/basepagelayout/transitions.ts';
import { buildHeaderStatsMarkup, buildStandardHeaderMarkup } from '@core/routing/pages/basepagelayout/view.ts';
import type { AttachViewportResizeOptions, CreateStandardSearchOptions, GenerateStandardHeaderOptions, GridPosition, HeaderStatDefinition, StandardSearchResult, UnsavedChangesGuardOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { isString } from '@core/typeGuards.ts';
import type { TabsComponent } from '@core/ui/controls/Tabs.ts';
import type { TabsOptions } from '@core/ui/controls/tabs/types.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { PageContext } from '@core/pagecontext/public.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';

type PageLayoutHost = BasePageLayoutHost &
    HeaderActionMenuHost & {
        updateText(target: Element, text: string): void;
    };

interface PageLayoutDependencies {
    pageId: string;
    pageContext: PageContext;
    pageDom: PageDom;
    resources: PageResources;
    services: PageServices;
    pageHost: PageHost;
}

interface PageLayoutControls {
    resolveDomContextForHeaderActions?: ((context?: Element | Document | null) => Element | null) | undefined;
    getActionsMenuBreakpoint?: (() => number) | undefined;
    getActionsMenuSidebarState?: (() => boolean) | undefined;
    onActionsMenuCollapsedChange?: ((collapsed: boolean) => void) | undefined;
    collapseActionsMenuToFit?: boolean | undefined;
    onTabChange?: ((target: string, previousTarget?: string | null) => void) | undefined;
    onResponsiveLayout?: (() => void) | undefined;
    updateCheckerboard?: (() => void) | undefined;
}

interface PageLayoutContract {
    initializeTabs(container: string | Element, options?: TabsOptions): TabsComponent | null;
    getTabs(): TabsComponent | null;
    setupResponsive(): void;
    setupHeaderStats(): void;
    attachHeaderAnimator(): void;
    attachHeaderCtaConfirmation(): void;
    initializePageActions(): void;
    applyHeaderStats(scope?: ParentNode | null): void;
    updateResponsive(): void;
    generateHeader(options?: GenerateStandardHeaderOptions): TrustedHtml;
    generateStats(statDefinitions?: HeaderStatDefinition[]): TrustedHtml;
    updateHeaderStat(id: string, label: string, value: number | string): void;
    updatePageActions(): void;
    queueHeaderActions(): void;
    registerUnsavedChanges(options: UnsavedChangesGuardOptions): () => void;
    applyGridPosition(element: Element, position: GridPosition): void;
    queueResponsive(): void;
    createSearch(container: string | Element, options: CreateStandardSearchOptions): StandardSearchResult;
    attachViewportResize(handler: () => void, options?: AttachViewportResizeOptions): () => void;
    hide(): Promise<void>;
    cleanup(): Promise<void>;
    destroy(): void;
}

interface PageLayoutOwnerHost {
    layout: PageLayoutContract;
}

class PageLayout implements PageLayoutContract {
    readonly #host: PageLayoutHost;
    readonly #pageHost: PageHost;
    readonly #pageDom: PageDom;
    readonly #controls: PageLayoutControls;
    readonly #state: BasePageLayoutState;
    #classMutationDisposer: (() => void) | null;

    constructor(dependencies: PageLayoutDependencies, controls: PageLayoutControls) {
        const host: PageLayoutHost = {
            get container(): HTMLElement | null {
                return dependencies.pageHost.container;
            },
            pageId: dependencies.pageId,
            pageContext: dependencies.pageContext,
            services: dependencies.services,
            resolveHostContainer: () => dependencies.pageHost.resolveContainer(),
            getUI: (selector, context) => dependencies.pageDom.get(selector, context),
            queryUI: (selector, context) => dependencies.pageDom.query(selector, context),
            on: (target, event, listener, options) => dependencies.resources.on(target, event, listener, options),
            trackDisposable: (resource, onDispose) => dependencies.resources.track(resource, onDispose),
            updateText: (target, text) => dependencies.pageDom.updateText(target, text),
            updateStyles: (target, styles, context) => dependencies.pageDom.updateStyles(target, styles, context),
            updateStyle: (target, property, value, context) => dependencies.pageDom.updateStyle(target, property, value, context),
            updateHTML: (target, html, options) => dependencies.pageDom.updateHtml(target, html, options),
            updateProperty: (target, property, value, context) => dependencies.pageDom.updateProperty(target, property, value, context),
            addClassName: (target, classes, context) => dependencies.pageDom.addClass(target, classes, context),
            removeClassName: (target, classes, context) => dependencies.pageDom.removeClass(target, classes, context),
            setDataAttribute: (target, name, value, context) => dependencies.pageDom.setDataAttribute(target, name, value, context),
            flushDOMUpdates: () => dependencies.pageDom.flush(),
            showNotification: (message, type, duration) => dependencies.pageContext.notifications.show(message, type, duration)
        };
        this.#host = host;
        this.#pageHost = dependencies.pageHost;
        this.#pageDom = dependencies.pageDom;
        this.#controls = controls;
        this.#state = createBasePageLayoutState();
        this.#classMutationDisposer = dependencies.pageDom.onClassMutation((target, classes, context) => this.#onClassMutation(target, classes, context));
    }

    configure(controls: PageLayoutControls): void {
        Object.assign(this.#controls, controls);
    }

    #resolveHeaderActionContext(context?: Element | Document | null): Element | null {
        return resolveLayoutHeaderActionContext(context, {
            ...(this.#controls.resolveDomContextForHeaderActions ? { resolveDomContextForHeaderActions: this.#controls.resolveDomContextForHeaderActions } : {}),
            getDomContext: () => this.#pageDom.getContext(),
            container: this.#host.container instanceof HTMLElement ? this.#host.container : null
        });
    }

    #resolveHeaderActionsRoot(): HTMLElement | null {
        return resolveLayoutHeaderActionsRoot((context) => this.#resolveHeaderActionContext(context));
    }

    #responsiveCallbacks(): ResponsiveLayoutCallbacks {
        return {
            refreshHeaderActionsLayout: () => {
                updatePageActionsMenuState(this.#state);
                this.refreshHeaderActions();
            },
            updateCheckerboard: () => this.#controls.updateCheckerboard?.(),
            onResponsiveLayout: () => this.#controls.onResponsiveLayout?.()
        };
    }

    #onClassMutation(target: DOMTarget, classes: string | string[], context?: Element | Document | null): void {
        queueLayoutHeaderActionsLayoutUpdateForMutation(
            this.#state,
            target,
            classes,
            context,
            (candidate) => this.#resolveHeaderActionContext(candidate),
            () => this.#resolveHeaderActionsRoot()
        );
    }

    queueHeaderActions(): void {
        queueLayoutHeaderActionsLayoutUpdate(
            this.#state,
            (context) => this.#resolveHeaderActionContext(context),
            () => this.#resolveHeaderActionsRoot()
        );
    }

    refreshHeaderActions(): void {
        refreshHeaderActionsLayout(() => this.#resolveHeaderActionsRoot());
    }

    initializeTabs(container: string | Element, options: TabsOptions = {}): TabsComponent | null {
        return initializeTabs(this.#host, this.#state, container, options, (target, previousTarget) => this.#controls.onTabChange?.(target, previousTarget));
    }

    getTabs(): TabsComponent | null {
        return getTabsComponent(this.#state);
    }

    setupResponsive(): void {
        setupResponsiveLayout(this.#host, this.#state, this.#responsiveCallbacks());
    }

    setupHeaderStats(): void {
        setupHeaderStatsLayout(this.#host, this.#state);
    }

    applyHeaderStats(scope?: ParentNode | null): void {
        applyHeaderStatsLayoutNow(this.#host, this.#state, scope);
    }

    updateResponsive(): void {
        updateResponsiveLayout(this.#host, this.#state, this.#responsiveCallbacks());
    }

    generateHeader(options: GenerateStandardHeaderOptions = {}): TrustedHtml {
        return buildStandardHeaderMarkup({ pageId: this.#host.pageId, isDetached: () => this.#host.services.isDetached(), getIconSync: (icon, iconOptions) => this.#host.services.getIconSync(icon, iconOptions) }, options);
    }

    generateStats(statDefinitions: HeaderStatDefinition[] = []): TrustedHtml {
        return buildHeaderStatsMarkup({ pageId: this.#host.pageId, isDetached: () => this.#host.services.isDetached(), getIconSync: (icon, iconOptions) => this.#host.services.getIconSync(icon, iconOptions) }, statDefinitions);
    }

    updateHeaderStat(id: string, label: string, value: number | string): void {
        const valueElement = this.#host.getUI(id);
        if (!valueElement) return;
        if (typeof value === 'number') {
            updateHeaderStatCard({ pageDom: this.#pageDom }, valueElement, label, i18n.formatNumber(value));
            return;
        }
        updateHeaderStatCard({ pageDom: this.#pageDom }, valueElement, label, value);
        if (valueElement instanceof HTMLElement) setTooltipText(valueElement, value);
    }

    attachHeaderAnimator(): void {
        attachHeaderAnimator(this.#host);
    }

    attachHeaderCtaConfirmation(): void {
        attachExternalLinkConfirmation(this.#host, this.#state);
    }

    initializePageActions(): void {
        bindPrefixedHeaderSelects(this.#host, this.#state);
        bindHeaderActionMenu(
            this.#host,
            this.#state,
            createLayoutHeaderActionMenuCallbacks({
                ...(this.#controls.getActionsMenuBreakpoint ? { getActionsMenuBreakpoint: this.#controls.getActionsMenuBreakpoint } : {}),
                ...(this.#controls.getActionsMenuSidebarState ? { getActionsMenuSidebarState: this.#controls.getActionsMenuSidebarState } : {}),
                ...(this.#controls.onActionsMenuCollapsedChange ? { onActionsMenuCollapsedChange: this.#controls.onActionsMenuCollapsedChange } : {}),
                ...(this.#controls.collapseActionsMenuToFit === true ? { collapseActionsMenuToFit: true } : {})
            })
        );
    }

    updatePageActions(): void {
        this.initializePageActions();
        updatePageActionsMenuState(this.#state);
    }

    registerUnsavedChanges(options: UnsavedChangesGuardOptions): () => void {
        const normalized: UnsavedChangesGuardOptions = { hasUnsavedChanges: options.hasUnsavedChanges, confirmMessage: options.confirmMessage };
        if (isString(options.guardId)) normalized.guardId = options.guardId;
        return registerUnsavedChangesProtection(this.#host, this.#state, normalized);
    }

    applyGridPosition(element: Element, position: GridPosition): void {
        updateGridPosition(this.#host, this.#state, element, position);
    }

    queueResponsive(): void {
        queueResponsiveLayoutUpdate(this.#host, this.#state, this.#responsiveCallbacks());
    }

    createSearch(container: string | Element, options: CreateStandardSearchOptions): StandardSearchResult {
        return createStandardSearch(this.#host, this.#state, container, options);
    }

    attachViewportResize(handler: () => void, options: AttachViewportResizeOptions = {}): () => void {
        return attachViewportResize(this.#host, this.#state, handler, options);
    }

    async hide(): Promise<void> {
        await onHide(this.#host, this.#pageHost.getSection());
    }

    async cleanup(): Promise<void> {
        await cleanupLayoutState(this.#host, this.#state);
        cleanupBasePageLayoutTransientState(this.#state);
    }

    destroy(): void {
        cleanupBasePageLayoutTransientState(this.#state);
        this.#classMutationDisposer?.();
        this.#classMutationDisposer = null;
    }
}

export { PageLayout };
export type { PageLayoutContract, PageLayoutControls, PageLayoutDependencies, PageLayoutHost, PageLayoutOwnerHost };
