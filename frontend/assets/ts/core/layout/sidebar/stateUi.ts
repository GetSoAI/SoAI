/* SoAI - Shared layout state UI [frontend/assets/ts/core/layout/sidebar/stateUi.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { getLayoutRuntimeManager } from '@core/runtime/LayoutManager.ts';
import { ARIA_HIDDEN_ATTR, SIDEBAR_COLLAPSED_CLASS, SIDEBAR_WIDTH, STYLE_DISPLAY } from '@core/layout/sidebar/dom.ts';
import type { SidebarState } from '@core/layout/sidebar/state.ts';
import type { SidebarVersionController } from '@core/layout/sidebar/version.ts';

const handleSidebarResize = (state: SidebarState): void => {
    const dimensions = measureLayoutViewport();
    const isMobile = dimensions.width <= 1024 || dimensions.height <= 768;
    if (state.mobile !== isMobile) {
        if (isMobile) {
            state.lastDesktopCollapsed = state.collapsed;
        } else {
            state.collapsed = state.lastDesktopCollapsed ?? state.collapsed;
        }
        state.open = false;
    }
    state.mobile = isMobile;
};

const updateSidebarStateUI = (state: SidebarState, domRefs: Map<string, HTMLElement | null>, versionController: SidebarVersionController, onMainStateIndicatorUpdate: () => void): void => {
    const collapsed = state.mobile ? !state.open : state.collapsed;
    const sidebar = domRefs.get('sidebar');
    if (sidebar) {
        dom.toggleClass(sidebar, SIDEBAR_COLLAPSED_CLASS, collapsed);
        dom.toggleClass(sidebar, 'is-open', state.mobile && state.open);
        dom.setAttribute(sidebar, ARIA_HIDDEN_ATTR, String(state.mobile && !state.open));
    }

    const backdrop = domRefs.get('backdrop');
    if (backdrop) {
        const visible = !collapsed;
        dom.toggleClass(backdrop, 'is-visible', visible);
        dom.setAttribute(backdrop, ARIA_HIDDEN_ATTR, String(!visible));
    }

    const body = getLayoutRuntimeManager().getBody();
    body.classList.toggle('sidebar-collapsed', collapsed);
    body.classList.toggle('sidebar-expanded', !collapsed);

    const hamburger = domRefs.get('hamburger');
    if (hamburger) {
        dom.setStyle(hamburger, STYLE_DISPLAY, 'inline-flex');
        dom.toggleClass(hamburger, 'is-active', !collapsed);
        dom.setAttribute(hamburger, 'aria-expanded', String(!collapsed));
    }

    const menu = domRefs.get('menu');
    if (menu) {
        const hide = state.mobile && !state.open;
        dom.setStyle(menu, STYLE_DISPLAY, hide ? 'none' : '');
        dom.setAttribute(menu, ARIA_HIDDEN_ATTR, String(hide));
    }

    versionController.refreshVisibility();
    onMainStateIndicatorUpdate();
};

const resetSidebarBodyState = (): void => {
    const body = getLayoutRuntimeManager().getBody();
    body.classList.toggle('sidebar-collapsed', true);
    body.classList.toggle('sidebar-expanded', false);
};

const isSidebarExpanded = (state: SidebarState): boolean => {
    return state.mobile ? state.open : !state.collapsed;
};

const compactSidebarState = (state: SidebarState): boolean => {
    if (state.mobile) {
        if (state.open) {
            state.open = false;
            return true;
        }
        return false;
    }
    if (!state.collapsed) {
        state.collapsed = true;
        state.lastDesktopCollapsed = true;
        return true;
    }
    return false;
};

const toggleSidebarState = (state: SidebarState): void => {
    if (state.mobile) {
        state.open = !state.open;
        return;
    }
    state.collapsed = !state.collapsed;
    state.lastDesktopCollapsed = state.collapsed;
};

const closeSidebarMobile = (state: SidebarState): boolean => {
    if (state.mobile && state.open) {
        state.open = false;
        return true;
    }
    return false;
};

const openSidebarMobile = (state: SidebarState): boolean => {
    if (state.mobile && !state.open) {
        state.open = true;
        return true;
    }
    return false;
};

const isSidebarBlocking = (state: SidebarState): boolean => {
    return state.mobile && state.open;
};

const getSidebarWidth = (state: SidebarState): number => {
    if (state.mobile) {
        return state.open ? SIDEBAR_WIDTH.mobile : 0;
    }
    return state.collapsed ? SIDEBAR_WIDTH.collapsed : SIDEBAR_WIDTH.expanded;
};

export { closeSidebarMobile, compactSidebarState, getSidebarWidth, handleSidebarResize, isSidebarBlocking, isSidebarExpanded, openSidebarMobile, resetSidebarBodyState, toggleSidebarState, updateSidebarStateUI };
