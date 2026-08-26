/* SoAI - Shared layout DOM refs [frontend/assets/ts/core/layout/sidebar/domRefs.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ARIA_HIDDEN_ATTR, resolveHTMLElement, SIDEBAR_DOM_SELECTORS, SIDEBAR_MENU_SELECTOR, VERSION_LARGE_ID, VERSION_SMALL_ID } from '@core/layout/sidebar/dom.ts';

const ensureSidebarVersionElements = (domRefs: Map<string, HTMLElement | null>): void => {
    const container = domRefs.get('versionContainer') || domRefs.get('logoWrapper') || domRefs.get('sidebar');
    if (!container) {
        return;
    }

    const pairs: [string, string][] = [
        ['versionLarge', VERSION_LARGE_ID],
        ['versionSmall', VERSION_SMALL_ID]
    ];
    pairs.forEach(([key, id]) => {
        let node = resolveHTMLElement(`#${id}`);
        if (node) {
            if (!container.contains(node)) {
                dom.appendChild(container, node);
            }
        } else {
            const created = dom.create('span', { id, className: id, [ARIA_HIDDEN_ATTR]: 'true' });
            if (!(created instanceof HTMLElement)) {
                throw new TypeError('Version element must be an HTMLElement');
            }
            node = created;
            dom.appendChild(container, created);
        }
        domRefs.set(key, node);
    });
};

const cacheSidebarDomRefs = (domRefs: Map<string, HTMLElement | null>): void => {
    domRefs.clear();
    for (const [key, selector] of Object.entries(SIDEBAR_DOM_SELECTORS)) {
        domRefs.set(key, resolveHTMLElement(selector));
    }
    if (!domRefs.get('menu')) {
        const sidebar = domRefs.get('sidebar');
        if (sidebar) {
            domRefs.set('menu', resolveHTMLElement(SIDEBAR_MENU_SELECTOR, sidebar));
        }
    }
    ensureSidebarVersionElements(domRefs);
};

const getSidebarDomRef = (domRefs: Map<string, HTMLElement | null>, key: string): HTMLElement | null => {
    return domRefs.get(key) || null;
};

const getSidebarMenuElement = (domRefs: Map<string, HTMLElement | null>): HTMLElement | null => {
    return getSidebarDomRef(domRefs, 'menu');
};

const getSidebarPageLink = (domRefs: Map<string, HTMLElement | null>, pageId: string): HTMLElement | null => {
    const menu = getSidebarMenuElement(domRefs);
    return menu ? resolveHTMLElement(`.sidebar-link[data-page="${pageId}"]`, menu) : null;
};

const getSidebarPluginsLink = (domRefs: Map<string, HTMLElement | null>): HTMLElement | null => {
    return getSidebarPageLink(domRefs, 'plugins');
};

const getSidebarChatLink = (domRefs: Map<string, HTMLElement | null>): HTMLElement | null => {
    return getSidebarPageLink(domRefs, 'chat');
};

const getSidebarAutomationLink = (domRefs: Map<string, HTMLElement | null>): HTMLElement | null => {
    return getSidebarPageLink(domRefs, 'automation');
};

const clearSidebarMenu = (domRefs: Map<string, HTMLElement | null>): void => {
    const menu = getSidebarMenuElement(domRefs);
    if (menu) {
        dom.replaceContent(menu, '');
    }
};

export { cacheSidebarDomRefs, clearSidebarMenu, getSidebarAutomationLink, getSidebarChatLink, getSidebarDomRef, getSidebarMenuElement, getSidebarPageLink, getSidebarPluginsLink };
