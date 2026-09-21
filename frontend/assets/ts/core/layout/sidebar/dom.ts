/* SoAI - Shared layout sidebar DOM contracts [frontend/assets/ts/core/layout/sidebar/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';

type SidebarDomKey = 'sidebar' | 'backdrop' | 'hamburger' | 'mainContent' | 'versionSmall' | 'versionLarge' | 'versionContainer' | 'logoLarge' | 'logoSmall' | 'logoWrapper' | 'menu';

const SIDEBAR_ROOT_SELECTOR = '.sidebar';
const SIDEBAR_BACKDROP_SELECTOR = '.sidebar-backdrop';
const SIDEBAR_LINK_SELECTOR = '.sidebar-link';
const SIDEBAR_PAGE_LABEL_SELECTOR = '.sidebar-link[data-page] .sidebar-label';
const SIDEBAR_MENU_SELECTOR = '.sidebar-menu';
const SIDEBAR_EXPANDED_WIDTH_PROPERTY = '--sidebar-width-expanded';
const SIDEBAR_BASE_WIDTH_PROPERTY = '--sidebar-width';

const SIDEBAR_COLLAPSED_CLASS = 'is-collapsed';

const ARIA_HIDDEN_ATTR = 'aria-hidden';

const STYLE_DISPLAY = 'display';
const STYLE_OPACITY = 'opacity';

const VERSION_LARGE_ID = 'sidebar-version-large';
const VERSION_SMALL_ID = 'sidebar-version-small';
const LOGO_LARGE_CLASS = 'sidebar-logo-large';
const LOGO_SMALL_CLASS = 'sidebar-logo-small';

const SIDEBAR_DOM_SELECTORS: Record<SidebarDomKey, string> = Object.freeze({
    sidebar: SIDEBAR_ROOT_SELECTOR,
    backdrop: SIDEBAR_BACKDROP_SELECTOR,
    hamburger: '#hamburger-menu',
    mainContent: '#main-content',
    versionSmall: '#' + VERSION_SMALL_ID,
    versionLarge: '#' + VERSION_LARGE_ID,
    versionContainer: '.sidebar-version-container',
    logoLarge: '.' + LOGO_LARGE_CLASS,
    logoSmall: '.' + LOGO_SMALL_CLASS,
    logoWrapper: '.sidebar-logo-wrapper',
    menu: SIDEBAR_ROOT_SELECTOR + ' ' + SIDEBAR_MENU_SELECTOR
});

const resolveHTMLElement = (selector: string, context: Element | Document | null = null): HTMLElement | null => {
    const resolved = dom.resolve(selector, context ?? dom.getDocument());
    if (resolved === null) return null;
    if (resolved instanceof HTMLElement) return resolved;
    if (resolved instanceof Element) {
        throw new Error(`Sidebar expected HTMLElement but found ${resolved.tagName} for selector: ${selector}`);
    }
    throw new Error(`Sidebar expected an Element for selector: ${selector}`);
};

export { ARIA_HIDDEN_ATTR, LOGO_LARGE_CLASS, LOGO_SMALL_CLASS, SIDEBAR_BACKDROP_SELECTOR, SIDEBAR_BASE_WIDTH_PROPERTY, SIDEBAR_COLLAPSED_CLASS, SIDEBAR_DOM_SELECTORS, SIDEBAR_EXPANDED_WIDTH_PROPERTY, SIDEBAR_LINK_SELECTOR, SIDEBAR_MENU_SELECTOR, SIDEBAR_PAGE_LABEL_SELECTOR, SIDEBAR_ROOT_SELECTOR, STYLE_DISPLAY, STYLE_OPACITY, VERSION_LARGE_ID, VERSION_SMALL_ID, resolveHTMLElement };

export type { SidebarDomKey };
