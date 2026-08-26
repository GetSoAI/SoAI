/* SoAI - Shared UI tabs effects [frontend/assets/ts/core/ui/controls/tabs/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { dom } from '@core/dom/dom.ts';
import { OverflowNavController } from '@core/ui/controls/OverflowNav.ts';
import { calculateTabScrollOffset } from '@core/ui/controls/tabs/service.ts';
import type { RightButtonConfig } from '@core/ui/controls/tabs/types.ts';
import { renderRightButtonsMarkup } from '@core/ui/controls/tabs/view.ts';

type ResolveElement = (selector: string) => Element | null;
type ResolveElements = (selector: string) => Element[];
type RegisterEventHandler = (target: EventTarget, event: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;

interface TabsDomReferences {
    navWrapper: HTMLElement | null;
    nav: HTMLElement | null;
    leftNavButton: HTMLElement | null;
    rightNavButton: HTMLElement | null;
    buttonsContainer: HTMLElement | null;
}

interface RightButtonsRenderOptions {
    className: string;
    activeTab: string | null;
    rightButtons: Record<string, RightButtonConfig[]>;
    buttonsContainer: HTMLElement | null;
    resolveElement: ResolveElement;
}

interface OverflowNavSetupOptions {
    enableOverflowNav: boolean;
    navScrollAmount: number;
    nav: HTMLElement | null;
    leftNavButton: HTMLElement | null;
    rightNavButton: HTMLElement | null;
    addEventListener: RegisterEventHandler;
}

const toHtmlElement = (value: Element | null): HTMLElement | null => (value instanceof HTMLElement ? value : null);

const cacheTabsDomReferences = (resolveElement: ResolveElement, className: string): TabsDomReferences => ({
    navWrapper: toHtmlElement(resolveElement(`.${className}-nav-wrapper`)),
    nav: toHtmlElement(resolveElement(`.${className}-nav`)),
    leftNavButton: toHtmlElement(resolveElement(`.${className}-nav-button--left`)),
    rightNavButton: toHtmlElement(resolveElement(`.${className}-nav-button--right`)),
    buttonsContainer: toHtmlElement(resolveElement(`#${className}-buttons`))
});

const updateActiveTabState = (resolveElements: ResolveElements, className: string, activeTab: string | null): void => {
    resolveElements(`.${className}-tab`).forEach((tab) => {
        dom.toggleClass(tab, 'is-active', dom.getData(tab, 'tab') === activeTab);
    });
};

const updateTabSelectionState = (tab: HTMLElement, panel: HTMLElement, isActive: boolean): void => {
    dom.setAttribute(tab, 'aria-selected', isActive ? 'true' : 'false');
    dom.setAttribute(panel, 'aria-hidden', isActive ? 'false' : 'true');
    panel.hidden = !isActive;
};

const updateTabAvailabilityState = (tab: HTMLElement, isAvailable: boolean): void => {
    dom.setAttribute(tab, 'aria-hidden', isAvailable ? 'false' : 'true');
    tab.tabIndex = isAvailable ? 0 : -1;
    tab.hidden = !isAvailable;
};

const renderRightButtons = (options: RightButtonsRenderOptions): HTMLElement | null => {
    const resolvedContainer = options.buttonsContainer ?? toHtmlElement(options.resolveElement(`#${options.className}-buttons`));
    if (!resolvedContainer) {
        return null;
    }
    dom.setHTML(resolvedContainer, renderRightButtonsMarkup(options.activeTab, options.rightButtons), {
        escape: false
    });
    return resolvedContainer;
};

const setupOverflowNav = (options: OverflowNavSetupOptions): OverflowNavController | null => {
    if (!options.enableOverflowNav || !options.nav || !options.leftNavButton || !options.rightNavButton) {
        return null;
    }
    const overflowNav = new OverflowNavController(options.nav, options.leftNavButton, options.rightNavButton, {
        scrollAmount: options.navScrollAmount
    });
    overflowNav.initialize(options.addEventListener);
    return overflowNav;
};

const scrollTabIntoView = (nav: HTMLElement | null, tabId: string, resolveElement: ResolveElement): void => {
    if (!nav) {
        return;
    }
    const tabElement = resolveElement(`[data-tab="${tabId}"]`);
    if (!tabElement) {
        return;
    }
    const scrollOffset = calculateTabScrollOffset(measureLayoutBox(nav), measureLayoutBox(tabElement));
    if (scrollOffset !== 0) {
        nav.scrollBy({ left: scrollOffset, behavior: 'smooth' });
    }
};

export { cacheTabsDomReferences, renderRightButtons, scrollTabIntoView, setupOverflowNav, updateActiveTabState, updateTabAvailabilityState, updateTabSelectionState };
export type { TabsDomReferences };
