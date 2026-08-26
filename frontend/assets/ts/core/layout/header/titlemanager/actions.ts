/* SoAI - Shared layout title manager actions [frontend/assets/ts/core/layout/header/titlemanager/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { getRouteRegistry, getSidebarComponentTargets } from '@core/routeregistry/service.ts';
import { refreshPageHeaderTitleTightStateForElement } from '@core/routing/pages/basepagelayout/dom.ts';
import { applyPageHeaderTitleDisplay, readPageHeaderTitleText } from '@core/routing/pages/basepagelayout/pageHeaderTitle.ts';
import type { SetHeaderCollapsedOptions, TitleManagerHost, TitleNavigationDirection } from '@core/layout/header/titlemanager/types.ts';
import { normalizeTitle } from '@core/layout/header/titlemanager/view.ts';

interface TitleManagerBindingState {
    dynamicComponents: Set<string>;
    currentTitle: string;
    currentComponent: string | null;
    pendingComponent: string | null;
    mainContentElement: HTMLElement | null;
    pageHeaderPanelElement: HTMLElement | null;
    pageHeaderTitleElement: HTMLElement | null;
    titleObserver: MutationObserver | null;
    headerCollapsed: boolean;
    headerBindingQueue: AnimationFrameRenderQueue<() => void> | null;
}

interface PageHeaderBinderDependencies {
    header: TitleManagerHost;
    setHeaderCollapsed: (value: boolean, options?: SetHeaderCollapsedOptions) => void;
    refreshDisplayedTitle: () => void;
    setCurrentPageTitle: (value: string) => void;
}

const isHeaderlessComponent = (dynamicComponents: Set<string>, component: string | null): boolean => {
    return component !== null && dynamicComponents.has(component);
};

const shouldForcePageTitle = (dynamicComponents: Set<string>, pendingComponent: string | null, currentComponent: string | null, headerCollapsed: boolean, isMobilePortrait: boolean): boolean => {
    return isHeaderlessComponent(dynamicComponents, pendingComponent || currentComponent) || headerCollapsed || isMobilePortrait;
};

const resolveSidebarNavigationDirection = (currentComponent: string | null, pendingComponent: string): TitleNavigationDirection => {
    if (!currentComponent || currentComponent === pendingComponent) {
        return 'none';
    }
    const componentTargets = getSidebarComponentTargets();
    const currentTarget = componentTargets[currentComponent] ?? null;
    const pendingTarget = componentTargets[pendingComponent] ?? null;
    if (!currentTarget || !pendingTarget || currentTarget === pendingTarget) {
        return 'none';
    }
    const routeRegistry = getRouteRegistry();
    const currentOrder = routeRegistry[currentTarget]?.sidebar?.order;
    const pendingOrder = routeRegistry[pendingTarget]?.sidebar?.order;
    if (currentOrder === undefined || pendingOrder === undefined || currentOrder === pendingOrder) {
        return 'none';
    }
    return pendingOrder > currentOrder ? 'down' : 'up';
};

const teardownPageHeaderObservers = (state: TitleManagerBindingState): void => {
    if (state.titleObserver) {
        state.titleObserver.disconnect();
    }
    state.titleObserver = null;
    state.pageHeaderPanelElement = null;
    state.pageHeaderTitleElement = null;
};

const resolveActiveSection = (state: TitleManagerBindingState, header: TitleManagerHost): HTMLElement | null => {
    const host = state.mainContentElement || header.optionalHTMLElement('#main-content');
    if (!host) {
        return null;
    }
    state.mainContentElement = host;
    return header.optionalHTMLElement(':scope > [data-section]', host);
};

const bindPageHeaderElements = (state: TitleManagerBindingState, dependencies: PageHeaderBinderDependencies): void => {
    const effectiveComponent = state.pendingComponent || state.currentComponent;
    const activeSection = resolveActiveSection(state, dependencies.header);
    if (!activeSection) {
        teardownPageHeaderObservers(state);
        dependencies.refreshDisplayedTitle();
        return;
    }
    if (isHeaderlessComponent(state.dynamicComponents, effectiveComponent)) {
        teardownPageHeaderObservers(state);
        dependencies.setHeaderCollapsed(false, { force: true });
        dependencies.refreshDisplayedTitle();
        return;
    }
    const panel = dependencies.header.optionalHTMLElement('.page-header-panel', activeSection);
    const titleElement = dependencies.header.optionalHTMLElement('.page-header-title', activeSection);
    if (state.pageHeaderPanelElement !== panel) {
        state.pageHeaderPanelElement = panel;
        dependencies.setHeaderCollapsed(panel?.classList.contains('page-header-panel--folded') === true, { force: true });
    }
    if (state.pageHeaderTitleElement !== titleElement) {
        if (state.titleObserver) {
            state.titleObserver.disconnect();
        }
        state.titleObserver = null;
        state.pageHeaderTitleElement = titleElement;
        if (titleElement) {
            const update = (): void => {
                const text = normalizeTitle(readPageHeaderTitleText(titleElement));
                applyPageHeaderTitleDisplay(titleElement, text);
                refreshPageHeaderTitleTightStateForElement(titleElement);
                if (!text || text === state.currentTitle) {
                    return;
                }
                dependencies.setCurrentPageTitle(text);
            };
            update();
            state.titleObserver = new MutationObserver(update);
            state.titleObserver.observe(titleElement, { characterData: true, subtree: true, childList: true });
        }
    }
    if (!panel && !titleElement) {
        dependencies.setHeaderCollapsed(false, { force: true });
    }
    dependencies.refreshDisplayedTitle();
};

const scheduleHeaderBinding = (state: TitleManagerBindingState, bindCallback: () => void): void => {
    if (state.headerBindingQueue === null) {
        state.headerBindingQueue = new AnimationFrameRenderQueue<() => void>({
            label: 'TitleManager',
            render: (callback): void => callback(),
            merge: (previous, next): (() => void) => previous ?? next
        });
    }
    state.headerBindingQueue.schedule(bindCallback);
};

export { bindPageHeaderElements, isHeaderlessComponent, resolveSidebarNavigationDirection, scheduleHeaderBinding, shouldForcePageTitle, teardownPageHeaderObservers };

export type { TitleManagerBindingState };
