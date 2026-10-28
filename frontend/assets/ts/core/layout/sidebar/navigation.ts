/* SoAI - Shared layout navigation [frontend/assets/ts/core/layout/sidebar/navigation.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { isPresenceAnimating } from '@core/animations/presence/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { getRouteRegistry, getSidebarComponentTargets } from '@core/routeregistry/service.ts';
import type { SidebarComponentTargets } from '@core/routeregistry/contracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { measureViewportBox } from '@core/layout/elementGeometry.ts';
import type { NavigationEventDetail } from '@core/navigationEvents.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isString } from '@core/typeGuards.ts';
import { resolveHTMLElement, SIDEBAR_ACTIVE_LINK_SELECTOR, SIDEBAR_LINK_SELECTOR } from '@core/layout/sidebar/dom.ts';

const SIDEBAR_ACTIVE_RAIL_CLASS = 'sidebar-active-rail';
const SIDEBAR_RAIL_MOTION_SLIDE = 'slide';
const SIDEBAR_RAIL_MOTION_FADE = 'fade';
const SIDEBAR_RAIL_VISIBLE = 'true';
const SIDEBAR_RAIL_HIDDEN = 'false';

const resolveSidebarActiveRail = (menu: HTMLElement): HTMLElement => {
    const existing = resolveHTMLElement(`.${SIDEBAR_ACTIVE_RAIL_CLASS}`, menu);
    if (existing) {
        return existing;
    }
    const rail = dom.create('span', { className: SIDEBAR_ACTIVE_RAIL_CLASS, 'aria-hidden': 'true' });
    dom.appendChild(menu, rail);
    return rail;
};

const updateSidebarActiveRail = (menu: HTMLElement | null, link: HTMLElement | null, previousLink: HTMLElement | null): void => {
    if (!menu) {
        return;
    }
    const rail = resolveSidebarActiveRail(menu);
    if (!link || link.offsetParent === null) {
        rail.dataset['motion'] = SIDEBAR_RAIL_MOTION_FADE;
        rail.dataset['visible'] = SIDEBAR_RAIL_HIDDEN;
        dom.setStyle(rail, '--sidebar-active-rail-opacity', '0');
        return;
    }
    const slideFromPrevious = previousLink !== null && previousLink !== link && previousLink.offsetParent !== null;
    if (slideFromPrevious) {
        rail.dataset['motion'] = SIDEBAR_RAIL_MOTION_FADE;
        rail.dataset['visible'] = SIDEBAR_RAIL_VISIBLE;
        dom.setStyles(rail, {
            '--sidebar-active-rail-y': `${previousLink.offsetTop}px`,
            '--sidebar-active-rail-height': `${previousLink.offsetHeight}px`,
            '--sidebar-active-rail-opacity': '1'
        });
        measureViewportBox(rail);
    }
    rail.dataset['motion'] = slideFromPrevious ? SIDEBAR_RAIL_MOTION_SLIDE : SIDEBAR_RAIL_MOTION_FADE;
    rail.dataset['visible'] = SIDEBAR_RAIL_VISIBLE;
    dom.setStyles(rail, {
        '--sidebar-active-rail-y': `${link.offsetTop}px`,
        '--sidebar-active-rail-height': `${link.offsetHeight}px`,
        '--sidebar-active-rail-opacity': '1'
    });
};

const sidebarRailFrames = new WeakMap<HTMLElement, number>();

const followSidebarActiveRail = (menu: HTMLElement): void => {
    const view = menu.ownerDocument.defaultView;
    if (!view) {
        return;
    }
    const pending = sidebarRailFrames.get(menu);
    if (pending !== undefined) view.cancelAnimationFrame(pending);
    const step = (): void => {
        sidebarRailFrames.delete(menu);
        const rail = resolveHTMLElement(`.${SIDEBAR_ACTIVE_RAIL_CLASS}`, menu);
        if (!menu.isConnected || rail?.dataset['visible'] !== SIDEBAR_RAIL_VISIBLE) {
            return;
        }
        updateSidebarActiveRail(menu, resolveHTMLElement(SIDEBAR_ACTIVE_LINK_SELECTOR, menu), null);
        if (Array.from(menu.children).some(isPresenceAnimating)) {
            sidebarRailFrames.set(menu, view.requestAnimationFrame(step));
        }
    };
    sidebarRailFrames.set(menu, view.requestAnimationFrame(step));
};

const setSidebarActiveLink = (menu: HTMLElement | null, link: HTMLElement | null): void => {
    const pageId = link?.getAttribute('data-page');
    if (pageId && getRouteRegistry()[pageId]?.sidebar?.activateOnNavigation === false) return;
    const previousLink = menu ? resolveHTMLElement(SIDEBAR_ACTIVE_LINK_SELECTOR, menu) : null;
    const existingRail = menu ? resolveHTMLElement(`.${SIDEBAR_ACTIVE_RAIL_CLASS}`, menu) : null;
    if (previousLink === link && existingRail?.dataset['visible'] === SIDEBAR_RAIL_VISIBLE) {
        return;
    }
    const links = menu ? dom.resolveAll(SIDEBAR_LINK_SELECTOR, menu) : [];
    for (const node of links) {
        if (node instanceof HTMLElement) {
            dom.removeAttribute(node, 'data-active');
        }
    }
    if (link) {
        dom.setAttribute(link, 'data-active', 'true');
    }
    updateSidebarActiveRail(menu, link, previousLink);
};

const setSidebarActiveByPage = (menu: HTMLElement | null, pageId: string): void => {
    if (!pageId) {
        setSidebarActiveLink(menu, null);
        return;
    }
    const link = menu ? resolveHTMLElement(`.sidebar-link[data-page="${pageId}"]`, menu) : null;
    setSidebarActiveLink(menu, link);
};

const syncSidebarWithCurrentRoute = (router: Router | null, menu: HTMLElement | null, routeComponentMap: SidebarComponentTargets): void => {
    if (!router) {
        return;
    }
    const current = router.getCurrentRoute() || router.getRouteFromHash();
    if (!current) {
        return;
    }
    const parsed = router.parseRoute ? router.parseRoute(current) : null;
    const component = parsed?.route?.component || current;
    if (component) {
        setSidebarActiveByPage(menu, routeComponentMap[component] || component);
    }
};

const isCurrentSidebarPageComponent = (router: Router, pageId: string): boolean => {
    const current = router.getCurrentRoute() || router.getRouteFromHash();
    if (!current) {
        return false;
    }
    const parsed = router.parseRoute ? router.parseRoute(current) : null;
    return parsed?.route?.component === pageId;
};

const navigateSidebarTo = (router: Router | null, pageId: string, menu: HTMLElement | null, mobile: boolean, closeMobile: () => Promise<void>): void => {
    setSidebarActiveByPage(menu, pageId);
    if (!router) {
        errorHandler.error('Sidebar', 'Router not available for navigation', { hasRouter: false });
        return;
    }
    if (isCurrentSidebarPageComponent(router, pageId)) {
        if (mobile) {
            terminateHandledPromise(closeMobile());
        }
        return;
    }
    router
        .navigate({ path: pageId, meta: { source: 'sidebar' } })
        .finally(() => {
            const selected = menu ? resolveHTMLElement(SIDEBAR_ACTIVE_LINK_SELECTOR, menu) : null;
            if (selected?.getAttribute('data-page') === pageId) syncSidebarWithCurrentRoute(router, menu, getSidebarComponentTargets());
        })
        .catch((error) => errorHandler.warn('Sidebar', 'Sidebar navigation failed', error));
    if (mobile) {
        terminateHandledPromise(closeMobile());
    }
};

const addSidebarNotificationBadge = (menu: HTMLElement | null, pageId: string, count: number): void => {
    const link = menu ? resolveHTMLElement(`.sidebar-link[data-page="${pageId}"]`, menu) : null;
    if (!link) {
        return;
    }
    const existing = resolveHTMLElement('.sidebar-badge', link);
    if (existing) {
        dom.remove(existing);
    }
    if (count > 0) {
        const badge = dom.create('span', { className: 'sidebar-badge' });
        dom.setText(badge, count > 99 ? '99+' : String(count));
        dom.appendChild(link, badge);
    }
};

const highlightSidebarItem = (menu: HTMLElement | null, pageId: string, type: string, setTimer: (functionValue: () => void, delayMs: number) => number | null): void => {
    const link = menu ? resolveHTMLElement(`.sidebar-link[data-page="${pageId}"]`, menu) : null;
    if (!link) {
        return;
    }
    const className = `highlight-${type}`;
    dom.addClass(link, className);
    setTimer(() => dom.removeClass(link, className), 3000);
};

const resolveRouteFromNavigationDetail = (detail: NavigationEventDetail | null = null): string | null => {
    const routeValue = detail?.['route'];
    return isString(routeValue) ? routeValue : null;
};

const resolveComponentFromNavigationDetail = (detail: NavigationEventDetail | null = null): string | null => {
    const componentValue = detail?.['component'];
    return isString(componentValue) ? componentValue : null;
};

export { addSidebarNotificationBadge, followSidebarActiveRail, highlightSidebarItem, navigateSidebarTo, resolveComponentFromNavigationDetail, resolveRouteFromNavigationDetail, setSidebarActiveByPage, setSidebarActiveLink, syncSidebarWithCurrentRoute };
