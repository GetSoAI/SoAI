/* SoAI - Shared layout interactions [frontend/assets/ts/core/layout/sidebar/interactions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { isString } from '@core/typeGuards.ts';
import { LOGO_LARGE_CLASS, LOGO_SMALL_CLASS } from '@core/layout/sidebar/dom.ts';
import type { SidebarDisposerCandidate } from '@core/layout/sidebar/disposers.ts';

interface SidebarInteractionsHost {
    addSessionDisposer: (functionValue: SidebarDisposerCandidate) => void;
    on: (target: EventTarget, eventName: string, handler: (event: Event) => void) => SidebarDisposerCandidate;
    compactSidebar: () => void;
    getDomRef: (key: string) => HTMLElement | null;
    getMenuElement: () => HTMLElement | null;
    isExpanded: () => boolean;
    navigateTo: (pageId: string) => void;
}

const resolveEventElement = (event: Event): Element | null => {
    const target = event.target;
    if (target instanceof Element) {
        return target;
    }
    if (target instanceof Node) {
        return target.parentElement;
    }
    return null;
};

const bindSidebarNavigation = (host: SidebarInteractionsHost): void => {
    const menu = host.getMenuElement();
    if (!menu) return;
    host.addSessionDisposer(
        host.on(menu, 'click', (event: Event) => {
            const target = resolveEventElement(event);
            if (!target) {
                return;
            }
            const candidate = target.closest('.sidebar-link');
            if (!candidate) {
                return;
            }
            if (!(candidate instanceof HTMLElement)) {
                errorHandler.warn('Sidebar', 'Sidebar link must be an HTMLElement');
                return;
            }
            if (dom.hasClass(candidate, 'main-state-indicator')) {
                return;
            }
            event.preventDefault();
            const pageId = candidate.dataset['page'];
            if (!isString(pageId) || !pageId) {
                errorHandler.warn('Sidebar', 'Sidebar link missing data-page');
                return;
            }
            host.compactSidebar();
            host.navigateTo(pageId);
        })
    );
};

const bindSidebarToggleHandlers = (host: SidebarInteractionsHost): void => {
    const backdrop = host.getDomRef('backdrop');
    const mainContent = host.getDomRef('mainContent');
    if (!backdrop || !mainContent) {
        throw new Error('Sidebar backdrop and page content are required');
    }
    host.addSessionDisposer(
        host.on(backdrop, 'click', (event: Event) => {
            event.preventDefault();
            event.stopPropagation();
            if (host.isExpanded()) {
                host.compactSidebar();
            }
        })
    );
    host.addSessionDisposer(
        host.on(mainContent, 'click', () => {
            if (host.isExpanded()) {
                host.compactSidebar();
            }
        })
    );
};

const bindSidebarLogoNavigation = (host: SidebarInteractionsHost): void => {
    const wrapper = host.getDomRef('logoWrapper');
    if (!wrapper) return;
    host.addSessionDisposer(
        host.on(wrapper, 'click', (event: Event) => {
            const target = resolveEventElement(event);
            if (!target || !wrapper.contains(target)) {
                return;
            }
            const isLogoTarget = target === wrapper || target.closest(`.${LOGO_LARGE_CLASS}`) instanceof Element || target.closest(`.${LOGO_SMALL_CLASS}`) instanceof Element;
            if (!isLogoTarget) {
                return;
            }
            event.preventDefault();
            host.navigateTo('dashboard');
            host.compactSidebar();
        })
    );
    dom.setStyle(wrapper, 'cursor', 'pointer');
};

export { bindSidebarLogoNavigation, bindSidebarNavigation, bindSidebarToggleHandlers };
export type { SidebarInteractionsHost };
