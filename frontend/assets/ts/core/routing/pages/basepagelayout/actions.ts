/* SoAI - Shared routing base page layout actions [frontend/assets/ts/core/routing/pages/basepagelayout/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { registerUnsavedChangesGuard } from '@core/navigationGuards.ts';
import { showUnsavedChangesConfirmation } from '@core/modals/unsavedChangesConfirmation.ts';
import { err } from '@core/routing/pages/basepagecore/actions.ts';
import { REMOTE_SEARCH_DEBOUNCE_MS } from '@core/search/searchDebounce.ts';
import type { BasePageLayoutState } from '@core/routing/pages/basepagelayout/state.ts';
import { getWindow } from '@core/environment/public.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { isFunction, isNullOrUndefined, isString } from '@core/typeGuards.ts';
import { TabsComponent } from '@core/ui/controls/Tabs.ts';
import type { TabsOptions } from '@core/ui/controls/tabs/types.ts';
import type { AttachViewportResizeOptions, CreateStandardSearchOptions, GridPosition, StandardSearchResult, UnsavedChangesGuardOptions } from '@core/routing/pages/pagetypes/public.ts';
import type { BasePageLayoutHost } from '@core/routing/pages/basepagelayout/contracts.ts';
import type { NavigationContext } from '@core/routing/router/types.ts';

const NOOP = (): void => {};

const initializeTabs = (page: BasePageLayoutHost, state: BasePageLayoutState, container: string | Element, options: TabsOptions = {}, onTabChange: (target: string, previousTarget: string | null) => void = () => undefined): TabsComponent | null => {
    const element = isString(container) ? page.getUI(container) : container;
    if (!(element instanceof HTMLElement)) {
        return null;
    }
    state.tabs?.destroy?.();
    state.tabs = new TabsComponent(element, {
        onTabChange,
        ...options
    });
    state.tabs.initialize();
    return state.tabs;
};

const getTabsComponent = (state: BasePageLayoutState): TabsComponent | null => state.tabs;

const getFromPageId = (context: NavigationContext): string | null => context.from?.route.component ?? null;

const registerUnsavedChangesProtection = (page: BasePageLayoutHost, _state: BasePageLayoutState, { hasUnsavedChanges, confirmMessage, guardId }: UnsavedChangesGuardOptions): (() => void) => {
    if (!isFunction(hasUnsavedChanges) || !isString(confirmMessage)) {
        throw new TypeError('Guard config invalid');
    }
    return registerUnsavedChangesGuard({
        id: guardId || `${page.pageId}-dirty-guard`,
        hasUnsavedChanges,
        getMessage: () => confirmMessage,
        shouldPromptOnNavigation: (context: NavigationContext) => getFromPageId(context) === page.pageId && hasUnsavedChanges(),
        confirmNavigation: async (context: NavigationContext) =>
            getFromPageId(context) !== page.pageId || !hasUnsavedChanges()
                ? true
                : await showUnsavedChangesConfirmation({
                      message: confirmMessage
                  }),
        addEventListener: (target: EventTarget, eventName: string, listener: EventListener, options?: AddEventListenerOptions) => page.on(target, eventName, listener, options)
    });
};

const updateGridPosition = (page: BasePageLayoutHost, _unusedValue: BasePageLayoutState, element: Element, position: GridPosition): void => {
    if (!element || !position) {
        throw new TypeError('Args invalid');
    }
    page.updateStyles(element, {
        gridColumn: `${position.x + 1} / span ${position.width}`,
        gridRow: `${position.y + 1} / span ${position.height}`
    });
};

const createStandardSearch = (page: BasePageLayoutHost, _state: BasePageLayoutState, selector: string | Element, options: CreateStandardSearchOptions): StandardSearchResult => {
    const { placeholder, onSearch = NOOP, onClear = NOOP, debounceTime = REMOTE_SEARCH_DEBOUNCE_MS, showIconOnMobile = false } = options;
    const container = isString(selector) ? page.getUI(selector) : selector;
    if (!container || dom.getData(container, 'searchInitialized')) {
        throw err('Search container invalid or initialized');
    }
    const containerId = container.id?.trim();
    if (!containerId) throw err('Search container requires a stable id');
    const inputId = `${containerId}-input`;
    if (!isString(placeholder) || !placeholder.trim()) {
        throw err('Search placeholder is required');
    }
    const searchIconClass = showIconOnMobile ? 'searchbar-icon' : 'searchbar-icon u-hide-mobile-portrait';
    page.updateHTML(
        container,
        uiHtml`<div class="searchbar-container searchbar-container--control wide u-stretch"><input type="text" class="searchbar-input" placeholder="${uiAttr(placeholder.trim())}" id="${uiAttr(inputId)}"><span class="${uiAttr(searchIconClass)}">${page.services.getIconSync('search', {
            size: 16,
            strokeWidth: 1.5
        })}</span></div>`,
        { escape: false }
    );
    page.setDataAttribute(container, 'searchInitialized', 'true');
    page.flushDOMUpdates();
    const resolvedInput = dom.resolve('input.searchbar-input', container);
    if (!(resolvedInput instanceof HTMLInputElement)) {
        throw err('Search input missing');
    }
    const input = resolvedInput;
    const notify = debounceTime > 0 ? page.services.createDebouncedHandler((value: string) => onSearch(value), debounceTime) : (value: string): void => onSearch(value);
    page.on(input, 'input', (event: Event) => {
        if (!(event.target instanceof HTMLInputElement)) {
            return;
        }
        const value = event.target.value;
        notify(value);
        if (!value) {
            onClear();
        }
    });
    return { input, setValue: (value: string) => page.updateProperty(input, 'value', value) };
};

const attachViewportResize = (page: BasePageLayoutHost, _state: BasePageLayoutState, handler: () => void, { debounceMs, options }: AttachViewportResizeOptions = {}): (() => void) => {
    const callback = isNullOrUndefined(debounceMs) ? handler : page.services.createDebouncedHandler(handler, debounceMs);
    const win = getWindow();
    const disposers: Array<() => void> = [page.on(win, 'resize', callback, options)];
    if (win.visualViewport) {
        disposers.push(page.on(win.visualViewport, 'resize', callback, options));
    }
    return () => {
        disposers.forEach((dispose) => dispose());
    };
};

export { attachViewportResize, createStandardSearch, getTabsComponent, initializeTabs, registerUnsavedChangesProtection, updateGridPosition };
