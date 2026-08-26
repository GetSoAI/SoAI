/* SoAI - Shared layout title manager service [frontend/assets/ts/core/layout/header/titlemanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { PAGE_HEADER_STATE_CHANGED_EVENT } from '@core/animations/constants.ts';
import { getDocument, getWindow } from '@core/environment/public.ts';
import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { onNavigationComplete, onNavigationError, onNavigationStart } from '@core/navigationEvents.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { bindPageHeaderElements, isHeaderlessComponent, resolveSidebarNavigationDirection, scheduleHeaderBinding, shouldForcePageTitle, teardownPageHeaderObservers } from '@core/layout/header/titlemanager/actions.ts';
import { detailIsObject, isSoaiOsCapabilitiesInterface, resolveComponent } from '@core/layout/header/titlemanager/guards.ts';
import type { NavigationDetail, SetCurrentPageTitleOptions, SetHeaderCollapsedOptions, TitleManagerOptions } from '@core/layout/header/titlemanager/types.ts';
import { formatTabBrandName, normalizeTitle, resolveNavigationTitle, setPageTitleDisplay } from '@core/layout/header/titlemanager/view.ts';

const PAGE_TITLE_NAVIGATION_ENTER_ANIMATION = 'page-title-navigation-enter';

export class TitleManager {
    header: TitleManagerOptions['header'];
    dynamicComponents: Set<string>;
    brand: string;
    currentTitle: string;
    currentComponent: string | null;
    pendingComponent: string | null;
    mainContentElement: HTMLElement | null;
    pageHeaderPanelElement: HTMLElement | null;
    pageHeaderTitleElement: HTMLElement | null;
    titleObserver: MutationObserver | null;
    mainObserver: MutationObserver | null;
    headerCollapsed: boolean;
    titleNavigating: boolean;
    headerBindingQueue: AnimationFrameRenderQueue<() => void> | null;
    navigationStartUnsubscribe: (() => void) | null;
    navigationUnsubscribe: (() => void) | null;
    navigationErrorUnsubscribe: (() => void) | null;

    constructor({ header, dynamicComponents }: TitleManagerOptions) {
        this.header = header;
        this.dynamicComponents = dynamicComponents ?? new Set();
        this.brand = '';
        this.currentTitle = '';
        this.currentComponent = null;
        this.pendingComponent = null;
        this.mainContentElement = null;
        this.pageHeaderPanelElement = null;
        this.pageHeaderTitleElement = null;
        this.titleObserver = null;
        this.mainObserver = null;
        this.headerCollapsed = false;
        this.titleNavigating = false;
        this.headerBindingQueue = null;
        this.navigationStartUnsubscribe = null;
        this.navigationUnsubscribe = null;
        this.navigationErrorUnsubscribe = null;
    }

    async initialize(): Promise<void> {
        this.brand = this.resolveBrandName();
        this.currentTitle = this.brand;
        setPageTitleDisplay(this.header, this.brand, this.brand);
        this.mainContentElement = this.header.optionalHTMLElement('#main-content');
        if (this.mainContentElement) {
            this.mainObserver = new MutationObserver((records) => {
                if (records.some((record) => record.type === 'childList')) {
                    scheduleHeaderBinding(this, () => this.bindPageHeaderElements());
                }
            });
            this.mainObserver.observe(this.mainContentElement, { childList: true });
        }
        this.navigationStartUnsubscribe = onNavigationStart((detail = null) => this.handleNavigationStart(detailIsObject(detail) ? detail : null));
        if (!this.navigationUnsubscribe) {
            this.navigationUnsubscribe = onNavigationComplete((detail = null) => this.handleNavigationEvent(detailIsObject(detail) ? detail : null));
        }
        if (!this.navigationErrorUnsubscribe) {
            this.navigationErrorUnsubscribe = onNavigationError(() => this.handleNavigationError());
        }
        this.header.on(getWindow(), PAGE_HEADER_STATE_CHANGED_EVENT, (event: Event) => this.handlePageHeaderStateChanged(event));
        const titleNode = this.header.getDom('pageTitle');
        if (titleNode) {
            this.header.on(titleNode, 'animationend', (event: Event) => this.handleTitleAnimationEnd(event));
        }
        this.refreshDisplayedTitle();
        this.updateDocumentTitle(this.brand);
        scheduleHeaderBinding(this, () => this.bindPageHeaderElements());
    }

    destroy(): void {
        this.cancelPendingHeaderBinding();
        this.headerBindingQueue?.dispose();
        this.headerBindingQueue = null;
        teardownPageHeaderObservers(this);
        if (this.mainObserver) {
            this.mainObserver.disconnect();
        }
        this.mainObserver = null;
        if (isFunction(this.navigationStartUnsubscribe)) {
            this.navigationStartUnsubscribe();
        }
        this.navigationStartUnsubscribe = null;
        if (isFunction(this.navigationUnsubscribe)) {
            this.navigationUnsubscribe();
        }
        this.navigationUnsubscribe = null;
        if (isFunction(this.navigationErrorUnsubscribe)) {
            this.navigationErrorUnsubscribe();
        }
        this.navigationErrorUnsubscribe = null;
        this.mainContentElement = null;
        this.currentComponent = null;
        this.pendingComponent = null;
        const titleNode = this.header.getDom('pageTitle');
        titleNode?.classList.remove('is-navigating', 'is-navigation-entering');
    }

    handleLocalizationChange(): void {
        const previousBrand = this.brand;
        this.brand = this.resolveBrandName();
        if (normalizeTitle(this.currentTitle) === normalizeTitle(previousBrand)) {
            this.currentTitle = this.brand;
        }
        this.refreshDisplayedTitle();
        this.writeDocumentTitle(this.currentTitle);
    }

    refreshDisplayedTitle(): void {
        if (this.titleNavigating) {
            return;
        }
        const value = this.resolveCurrentDisplayedTitle();
        setPageTitleDisplay(this.header, value, this.brand);
    }

    handleNavigationStart(detailInput: NavigationDetail | null): void {
        const detail = detailIsObject(detailInput) ? detailInput : {};
        const component = resolveComponent(detail);
        if (!component) {
            return;
        }
        this.cancelPendingHeaderBinding();
        const shouldAnimateTitle = this.shouldAnimateTitleNavigation(detail, component);
        teardownPageHeaderObservers(this);
        const titleNode = this.header.getDom('pageTitle');
        if (titleNode) {
            this.header.updateAttribute(titleNode, 'data-page-title-navigation', resolveSidebarNavigationDirection(this.currentComponent, component));
        }
        this.pendingComponent = component;
        this.setTitleNavigating(shouldAnimateTitle);
        this.setHeaderCollapsed(this.isHeaderless(this.pendingComponent), { force: true });
    }

    handleNavigationEvent(detailInput: NavigationDetail | null): void {
        const detail = detailIsObject(detailInput) ? detailInput : {};
        const component = resolveComponent(detail);
        if (!component) {
            return;
        }
        const headerless = this.isHeaderless(component);
        const titleValue = resolveNavigationTitle(detail, component, this.brand, headerless);
        this.currentTitle = titleValue;
        this.currentComponent = component;
        this.pendingComponent = null;
        this.setHeaderCollapsed(headerless, { force: true });
        setPageTitleDisplay(this.header, this.resolveCurrentDisplayedTitle(), this.brand);
        this.writeDocumentTitle(titleValue);
        this.setTitleNavigating(false);
        this.header.onSearchNavigation(component);
        this.bindPageHeaderElements();
    }

    bindPageHeaderElements(): void {
        bindPageHeaderElements(this, {
            header: this.header,
            setHeaderCollapsed: (value, options) => this.setHeaderCollapsed(value, options),
            refreshDisplayedTitle: () => this.refreshDisplayedTitle(),
            setCurrentPageTitle: (value) => this.setCurrentPageTitle(value)
        });
    }

    cancelPendingHeaderBinding(): void {
        this.headerBindingQueue?.cancel();
    }

    handleNavigationError(): void {
        this.pendingComponent = null;
        this.setHeaderCollapsed(this.isHeaderless(this.currentComponent), { force: true });
        this.setTitleNavigating(false);
        this.refreshDisplayedTitle();
    }

    handlePageHeaderStateChanged(event: Event): void {
        if (!(event instanceof CustomEvent)) {
            return;
        }
        const detail = event.detail;
        if (!isObject(detail)) {
            return;
        }
        this.setHeaderCollapsed(detail['collapsed'] === true);
    }

    handleTitleAnimationEnd(event: Event): void {
        const titleNode = this.header.getDom('pageTitle');
        if (!titleNode || !(event instanceof AnimationEvent) || event.target !== titleNode || event.animationName !== PAGE_TITLE_NAVIGATION_ENTER_ANIMATION) {
            return;
        }
        titleNode.classList.remove('is-navigation-entering');
    }

    resolveBrandName(): string {
        try {
            const soaiOsCapabilities = this.header.resolveService('core.soaiOsCapabilities', isSoaiOsCapabilitiesInterface, 'SoAI OS capabilities');
            if (soaiOsCapabilities.isSoaiOsEnabled()) {
                return normalizeTitle(i18n.t('header.brandNameOs')) || i18n.t('header.brandNameOs');
            }
            const normalized = normalizeTitle(i18n.t('header.brandName'));
            return normalized || i18n.t('header.brandName');
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.debug('TitleManager', 'Brand name translation unavailable', runtimeError);
            throw ensureError(error);
        }
    }

    isHeaderless(component: string | null): boolean {
        return isHeaderlessComponent(this.dynamicComponents, component);
    }

    shouldForcePageTitle(): boolean {
        return shouldForcePageTitle(this.dynamicComponents, this.pendingComponent, this.currentComponent, this.headerCollapsed, this.header.isMobilePortrait());
    }

    shouldAnimateTitleNavigation(detail: NavigationDetail, component: string): boolean {
        return normalizeTitle(this.resolveCurrentDisplayedTitle()) !== normalizeTitle(this.resolvePendingDisplayedTitle(detail, component));
    }

    resolveCurrentDisplayedTitle(): string {
        return this.shouldForcePageTitle() ? this.currentTitle : this.brand;
    }

    resolvePendingDisplayedTitle(detail: NavigationDetail, component: string): string {
        const headerless = this.isHeaderless(component);
        if (headerless || this.header.isMobilePortrait()) {
            return resolveNavigationTitle(detail, component, this.brand, headerless);
        }
        return this.brand;
    }

    setHeaderCollapsed(value: boolean, options: SetHeaderCollapsedOptions = {}): void {
        const { force = false } = options;
        if (!force && this.headerCollapsed === value) {
            return;
        }
        this.headerCollapsed = value;
        this.refreshDisplayedTitle();
    }

    setCurrentPageTitle(value: string, options: SetCurrentPageTitleOptions = {}): void {
        const { force = false } = options;
        const normalized = normalizeTitle(value);
        if (!normalized || (!force && normalized === this.currentTitle)) {
            return;
        }
        this.currentTitle = normalized;
        this.writeDocumentTitle(normalized);
        this.refreshDisplayedTitle();
    }

    setTitleNavigating(value: boolean): void {
        const titleNode = this.header.getDom('pageTitle');
        if (value) {
            this.titleNavigating = true;
            titleNode?.classList.remove('is-navigation-entering');
            titleNode?.classList.add('is-navigating');
            return;
        }
        const shouldAnimateEntrance = this.titleNavigating;
        this.titleNavigating = false;
        titleNode?.classList.remove('is-navigating');
        titleNode?.classList.toggle('is-navigation-entering', shouldAnimateEntrance);
    }

    updateDocumentTitle(value: string): void {
        const normalized = normalizeTitle(value) || this.brand;
        this.writeDocumentTitle(normalized);
        this.currentTitle = normalized;
        this.refreshDisplayedTitle();
    }

    writeDocumentTitle(value: string): void {
        const normalizedBrand = formatTabBrandName(this.brand);
        const normalized = normalizeTitle(value);
        const documentRef = getDocument();
        documentRef.title = normalized && normalized !== this.brand ? `${normalizedBrand} - ${normalized}` : normalizedBrand;
    }
}
