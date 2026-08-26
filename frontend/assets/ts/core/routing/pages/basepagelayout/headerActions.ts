/* SoAI - Shared routing header actions [frontend/assets/ts/core/routing/pages/basepagelayout/headerActions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, type DOMTarget } from '@core/dom/dom.ts';
import { queueHeaderActionsLayoutUpdate, shouldUpdateHeaderActionLayout } from '@core/routing/pages/basepagelayout/dom.ts';
import type { HeaderActionMenuCallbacks } from '@core/routing/pages/basepagelayout/effects.ts';
import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';
import { isDocumentNode, isElementNode } from '@core/typeGuards.ts';

interface ResolveLayoutHeaderActionContextDependencies {
    resolveDomContextForHeaderActions?: (context?: Element | Document | null) => Element | null;
    getDomContext: () => Element | null;
    container: HTMLElement | null;
}

interface HeaderActionMenuCallbacksDependencies {
    getActionsMenuBreakpoint?: () => number;
    getActionsMenuSidebarState?: () => boolean;
    onActionsMenuCollapsedChange?: (collapsed: boolean) => void;
    collapseActionsMenuToFit?: boolean;
}

const resolveLayoutHeaderActionContext = (context: Element | Document | null | undefined, dependencies: ResolveLayoutHeaderActionContextDependencies): Element | null => {
    const overrideContext = dependencies.resolveDomContextForHeaderActions?.(context);
    if (overrideContext) {
        return overrideContext;
    }
    if (isDocumentNode(context)) {
        return context.documentElement;
    }
    if (isElementNode(context)) {
        return context;
    }
    const resolvedContext = dependencies.getDomContext() || dependencies.container;
    return isElementNode(resolvedContext) ? resolvedContext : null;
};

const resolveLayoutHeaderActionsRoot = (resolveContext: (context?: Element | Document | null) => Element | null): HTMLElement | null => {
    const context = resolveContext();
    const rootContext = context || dom.getDocumentElement();
    const headerActions = dom.resolve('.page-actions__menu', rootContext);
    return headerActions instanceof HTMLElement ? headerActions : null;
};

const createLayoutHeaderActionMenuCallbacks = (dependencies: HeaderActionMenuCallbacksDependencies): HeaderActionMenuCallbacks => {
    const callbacks: HeaderActionMenuCallbacks = {};
    if (dependencies.collapseActionsMenuToFit === true) {
        callbacks.collapseToFit = true;
    }
    const getActionsMenuBreakpoint = dependencies.getActionsMenuBreakpoint;
    if (typeof getActionsMenuBreakpoint === 'function') {
        callbacks.getBreakpoint = (): number => getActionsMenuBreakpoint();
    }
    const getActionsMenuSidebarState = dependencies.getActionsMenuSidebarState;
    if (typeof getActionsMenuSidebarState === 'function') {
        callbacks.getSidebarState = (): boolean => getActionsMenuSidebarState();
    }
    const onActionsMenuCollapsedChange = dependencies.onActionsMenuCollapsedChange;
    if (typeof onActionsMenuCollapsedChange === 'function') {
        callbacks.onCollapsedChange = (collapsed: boolean): void => onActionsMenuCollapsedChange(collapsed);
    }
    return callbacks;
};

const queueLayoutHeaderActionsLayoutUpdateForMutation = (state: BasePageLayoutState, target: DOMTarget, classes: string | string[], context: Element | Document | null | undefined, resolveContext: (context?: Element | Document | null) => Element | null, resolveRoot: () => HTMLElement | null): void => {
    if (shouldUpdateHeaderActionLayout(resolveContext, target, classes, context)) {
        queueHeaderActionsLayoutUpdate(state, resolveContext, resolveRoot);
    }
};

const queueLayoutHeaderActionsLayoutUpdate = (state: BasePageLayoutState, resolveContext: (context?: Element | Document | null) => Element | null, resolveRoot: () => HTMLElement | null): void => {
    queueHeaderActionsLayoutUpdate(state, resolveContext, resolveRoot);
};

export { createLayoutHeaderActionMenuCallbacks, queueLayoutHeaderActionsLayoutUpdate, queueLayoutHeaderActionsLayoutUpdateForMutation, resolveLayoutHeaderActionContext, resolveLayoutHeaderActionsRoot };
export type { HeaderActionMenuCallbacksDependencies, ResolveLayoutHeaderActionContextDependencies };
