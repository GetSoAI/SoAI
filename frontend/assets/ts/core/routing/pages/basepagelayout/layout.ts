/* SoAI - Shared routing layout [frontend/assets/ts/core/routing/pages/basepagelayout/layout.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { INTERFACE_SCALE_CHANGED_EVENT } from '@core/layout/interfaceScale.ts';
import { applyHeaderStatsLayout } from '@core/headerStatsLayout.ts';
import { getCancelAnimationFrame, getComputedStyleStrict, getRequestAnimationFrame, getWindow } from '@core/environment/public.ts';
import { getPageHeaderAnimator } from '@core/animations/service.ts';
import { dom } from '@core/dom/dom.ts';
import { isDocumentNode, isElementNode } from '@core/typeGuards.ts';
import { applyAdaptiveNumbers } from '@core/ui/adaptiveNumber.ts';
import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';
import { requireCheckerboardService } from '@core/routing/pages/pageDom.ts';
import type { BasePageLayoutHost } from '@core/routing/pages/basepagelayout/contracts.ts';

interface ResponsiveLayoutCallbacks {
    refreshHeaderActionsLayout(): void;
    updateCheckerboard(): void;
    onResponsiveLayout(): void;
}

const queueHeaderStatsFrame = (state: BasePageLayoutState, rerender: () => void): void => {
    if (state.pendingHeaderStatsFrame) return;
    state.pendingHeaderStatsFrame = getRequestAnimationFrame()(() => {
        state.pendingHeaderStatsFrame = null;
        rerender();
    });
};

const updateResponsiveLayout = (page: BasePageLayoutHost, state: BasePageLayoutState, callbacks: ResponsiveLayoutCallbacks): void => {
    const contentArea = page.getUI('.page-scrollable') || page.getUI('[data-section]');
    if (!contentArea) {
        callbacks.onResponsiveLayout();
        return;
    }
    const header = page.getUI('.header');
    if (state.layoutResizeObserver && isElementNode(header)) {
        state.layoutResizeObserver.observe(header);
    }
    const headerHeight = header ? measureLayoutBox(header).height : parseFloat(getComputedStyleStrict(dom.getDocumentElement()).getPropertyValue('--layout-top-offset')) || 0;
    page.updateStyles(contentArea, {
        '--header-height': `${headerHeight}px`
    });
    callbacks.refreshHeaderActionsLayout();
    callbacks.updateCheckerboard();
    applyAdaptiveNumbers(contentArea);
    callbacks.onResponsiveLayout();
};

const setupResponsiveLayout = (page: BasePageLayoutHost, state: BasePageLayoutState, callbacks: ResponsiveLayoutCallbacks): void => {
    if (state.responsiveSetup) {
        return;
    }
    state.responsiveSetup = true;
    const requestAnimationFrame = getRequestAnimationFrame();
    const schedule = (): void => {
        if (!state.pendingLayoutFrame) {
            state.pendingLayoutFrame = requestAnimationFrame(() => {
                state.pendingLayoutFrame = null;
                updateResponsiveLayout(page, state, callbacks);
            });
        }
    };
    const win = getWindow();
    ['resize', 'orientationchange'].forEach((eventName) => page.on(win, eventName, schedule));
    page.on(win, INTERFACE_SCALE_CHANGED_EVENT, schedule);
    if (win.visualViewport) {
        page.on(win.visualViewport, 'resize', schedule);
    }
    const contentArea = page.getUI('.page-scrollable') || page.getUI('[data-section]') || getWindow().document.body;
    if (contentArea) {
        state.layoutResizeObserver = new ResizeObserver(schedule);
        state.layoutResizeObserver.observe(contentArea);
    }
    schedule();
};

const setupHeaderStatsLayout = (page: BasePageLayoutHost, state: BasePageLayoutState): void => {
    if (state.headerStatsLayouts) {
        return;
    }
    const containers = page.queryUI('.ui-page-header-stats');
    if (!containers || !containers.length) {
        return;
    }
    const apply = (): void => {
        state.headerStatsLayouts?.forEach((layout) => {
            applyHeaderStatsLayout(layout.container);
            applyAdaptiveNumbers(layout.container);
        });
    };
    const schedule = (): void => queueHeaderStatsFrame(state, apply);
    const layouts = containers.map((container) => {
        if (!isElementNode(container) || !(container instanceof HTMLElement)) {
            throw new Error('Header stats containers must be HTMLElements');
        }
        const resizeObserver = new ResizeObserver(schedule);
        const mutationObserver = new MutationObserver(schedule);
        resizeObserver.observe(container);
        mutationObserver.observe(container, { childList: true });
        page.trackDisposable(resizeObserver, () => resizeObserver.disconnect());
        page.trackDisposable(mutationObserver, () => mutationObserver.disconnect());
        return { container };
    });
    state.headerStatsLayouts = layouts;
    const width = getWindow();
    page.on(width, 'resize', schedule);
    apply();
    schedule();
    layouts.forEach(({ container }) => {
        requireCheckerboardService().applyCheckerboard(container, '.ui-page-header-stats__card');
    });
};

const applyHeaderStatsLayoutNow = (_page: BasePageLayoutHost, _state: BasePageLayoutState, scope?: ParentNode | null): void => {
    const root = isElementNode(scope) || isDocumentNode(scope) ? scope : dom.getDocument();
    const containers = (dom.resolveAll('.ui-page-header-stats', root) || []).filter((element): element is HTMLElement => element instanceof HTMLElement);
    if (!containers.length) {
        return;
    }
    containers.forEach((container) => {
        applyHeaderStatsLayout(container);
        applyAdaptiveNumbers(container);
    });
};

const cleanupLayoutState = (page: BasePageLayoutHost, state: BasePageLayoutState): void => {
    const cancelFrame = getCancelAnimationFrame();
    if (state.pendingLayoutFrame !== null) {
        cancelFrame(state.pendingLayoutFrame);
    }
    if (state.pendingHeaderActionsFrame !== null) {
        cancelFrame(state.pendingHeaderActionsFrame);
    }
    if (state.pendingHeaderStatsFrame !== null) {
        cancelFrame(state.pendingHeaderStatsFrame);
    }
    state.layoutResizeObserver?.disconnect();
    state.prefixedSelectObserver?.disconnect();
    state.pendingLayoutFrame = null;
    state.pendingHeaderActionsFrame = null;
    state.pendingHeaderStatsFrame = null;
    state.layoutResizeObserver = null;
    state.prefixedSelectObserver = null;
    state.headerStatsLayouts = null;
    state.responsiveSetup = false;
    const section = page.getUI('.page-scrollable');
    if (section instanceof HTMLElement) {
        getPageHeaderAnimator().detach(section);
    }
};

const queueResponsiveLayoutUpdate = (page: BasePageLayoutHost, state: BasePageLayoutState, callbacks: ResponsiveLayoutCallbacks): void => {
    if (!state.pendingLayoutFrame) {
        state.pendingLayoutFrame = getRequestAnimationFrame()(() => {
            state.pendingLayoutFrame = null;
            updateResponsiveLayout(page, state, callbacks);
        });
    }
};

export { applyHeaderStatsLayoutNow, cleanupLayoutState, queueResponsiveLayoutUpdate, setupHeaderStatsLayout, setupResponsiveLayout, updateResponsiveLayout };
export type { ResponsiveLayoutCallbacks };
