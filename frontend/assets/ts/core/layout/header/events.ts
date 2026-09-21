/* SoAI - Shared layout header events [frontend/assets/ts/core/layout/header/events.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getWindow } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { isElementNode, isFunction, isNode, isObject, isString } from '@core/typeGuards.ts';
import { isSidebarCollapseApi, type SidebarService } from '@core/layout/header/contracts.ts';
import type { CloseDropdownsOptions, CustomEventDetail, HeaderController } from '@core/layout/header/state.ts';
import type { HeaderControllers } from '@core/layout/HeaderInterface.ts';
import { CLOCK_PREFERENCES_CHANGED_EVENT } from '@core/storage/clockPreferences.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

interface HeaderLocalizationContext {
    controllers: HeaderControllers;
    controllerOrder: HeaderController[];
    getDom: (key: string) => HTMLElement | null;
}

interface HeaderSidebarCollapseContext {
    getDom: (key: string) => HTMLElement | null;
    resolveSidebar: () => SidebarService;
    isMobilePortrait: () => boolean;
    on: (target: EventTarget, event: string, handler: (event: Event) => void, options?: AddEventListenerOptions) => (() => void) | void;
}

interface HeaderClickContext {
    getDomMany: (keys: string[]) => (HTMLElement | null)[];
    closeDropdowns: (options?: CloseDropdownsOptions) => void;
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
}

interface HeaderEventsContext {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getEventHubTarget: () => EventTarget;
    applyLocalization: () => void;
    controllers: HeaderControllers;
}

const applyHeaderLocalization = (context: HeaderLocalizationContext): void => {
    for (const controller of context.controllerOrder) {
        if (isFunction(controller.localize)) {
            controller.localize();
        }
    }

    context.controllers.title.handleLocalizationChange();
    const hamburger = context.getDom('hamburger');
    if (hamburger) {
        dom.setAttribute(hamburger, 'aria-label', i18n.t('header.actions.toggleMenu'));
        setTooltipText(hamburger, i18n.t('header.actions.menuTitle'));
    }

    const documentRef = getWindow().document;
    const setText = (selector: string, value: string): void => {
        const node = dom.resolve(selector, documentRef);
        if (node instanceof HTMLElement) {
            dom.setText(node, value);
        }
    };
    const setAttr = (selector: string, attr: string, value: string): void => {
        const node = dom.resolve(selector, documentRef);
        if (node instanceof HTMLElement) {
            dom.setAttribute(node, attr, value);
        }
    };

    setText('#restart-message', i18n.t('restartOverlay.messages.pleaseWait'));
    setText('#restart-description', i18n.t('restartOverlay.descriptions.generic'));

    setAttr('#hamburger-menu', 'aria-label', i18n.t('header.actions.toggleMenu'));
    {
        const node = dom.resolve('#hamburger-menu', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.actions.menuTitle'));
        }
    }
    setAttr('#header-search-container', 'aria-label', i18n.t('header.search.containerAria'));
    setAttr('#header-search-input', 'placeholder', i18n.t('header.search.placeholder'));
    setAttr('#header-search-input', 'aria-label', i18n.t('header.search.placeholder'));
    {
        const node = dom.resolve('#header-search-button', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.search.open'));
        }
    }
    setAttr('#header-search-button', 'aria-label', i18n.t('header.search.open'));
    setText('#header-notification-title', i18n.t('header.notificationCenter.title'));
    {
        const node = dom.resolve('#clear-all-notifications', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.notificationCenter.actions.clearAll'));
        }
    }
    setAttr('#clear-all-notifications', 'aria-label', i18n.t('header.notificationCenter.actions.clearAll'));
    setAttr('#settings-button', 'aria-label', i18n.t('header.actions.openSettings'));
    {
        const node = dom.resolve('#settings-button', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.actions.openSettings'));
        }
    }
    setText('#goto-settings', i18n.t('header.menu.settings'));
    setText('#goto-logs', i18n.t('header.menu.logs'));
    setText('#goto-updates', i18n.t('header.menu.updates'));
    setText('#goto-about', i18n.t('header.menu.about'));
    setText('#settings-logout', i18n.t('header.menu.logout'));
    setAttr('#user-button', 'aria-label', i18n.t('header.actions.openUserMenu'));
    {
        const node = dom.resolve('#user-button', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.actions.openUserMenu'));
        }
    }
    setText('#logout', i18n.t('header.menu.logout'));
    setAttr('#clock-button', 'aria-label', i18n.t('header.actions.toggleClockFormat'));
    {
        const node = dom.resolve('#clock-button', documentRef);
        if (node instanceof HTMLElement) {
            setTooltipText(node, i18n.t('header.actions.toggleClockFormat'));
        }
    }
    setAttr('.sidebar-logo-large', 'alt', i18n.t('header.brandLogoAlt'));
    setAttr('.sidebar-logo-small', 'alt', i18n.t('header.brandIconAlt'));

    const currentTitle = context.controllers.title.currentTitle || context.controllers.title.brand;
    context.controllers.title.updateDocumentTitle(currentTitle);
};

const bindHeaderSidebarCollapse = (context: HeaderSidebarCollapseContext): void => {
    const header = context.getDom('header');
    const hamburger = context.getDom('hamburger');
    if (!header) {
        throw new Error('Header root is missing; cannot wire sidebar collapse behavior');
    }
    if (!hamburger) {
        throw new Error('Header hamburger is missing; cannot wire sidebar collapse behavior');
    }

    const sidebar = context.resolveSidebar();
    if (!isObject(sidebar)) {
        throw new Error('Sidebar service must be a record');
    }
    if (!isSidebarCollapseApi(sidebar)) {
        throw new Error('Sidebar must expose isExpanded() and compactSidebar()');
    }

    const update = (): void => {
        const expanded = sidebar.isExpanded();
        if (expanded && context.isMobilePortrait()) {
            sidebar.compactSidebar();
        }
    };

    context.on(getWindow(), 'resize', () => {
        update();
    });
    context.on(
        header,
        'click',
        (event: Event) => {
            const target = event.target;
            if (!isNode(target)) {
                return;
            }
            if (hamburger.contains(target)) {
                return;
            }
            if (sidebar.isExpanded()) {
                sidebar.compactSidebar();
            }
        },
        { capture: true }
    );
    update();
};

const setupHeaderGlobalClickHandler = (context: HeaderClickContext): void => {
    const keys = ['searchInput', 'searchDropdown', 'searchButton', 'notificationButton', 'notificationCenter', 'settingsButton', 'settingsDropdown', 'userButton', 'userDropdown'];
    const [searchInput, searchDropdown, searchButton, notificationButton, notificationCenter, settingsButton, settingsDropdown, userButton, userDropdown] = context.getDomMany(keys);

    const required = [searchInput, searchDropdown, searchButton, settingsButton, settingsDropdown];
    const labels = ['Header search input', 'Header search dropdown', 'Header search button', 'Header settings button', 'Header settings dropdown'];
    for (let index = 0; index < required.length; index += 1) {
        if (!isElementNode(required[index])) {
            throw new Error(`${labels[index]} must be an Element`);
        }
    }

    context.on(document, 'click', (event: Event) => {
        const target = event.target;
        if (!isNode(target)) {
            return;
        }
        if (searchInput?.contains(target) || searchDropdown?.contains(target) || searchButton?.contains(target)) {
            return;
        }
        if (notificationButton?.contains(target) || notificationCenter?.contains(target)) {
            return;
        }
        if (settingsButton?.contains(target) || settingsDropdown?.contains(target)) {
            return;
        }
        if (userButton?.contains(target) || userDropdown?.contains(target)) {
            return;
        }
        context.closeDropdowns();
    });
};

const readCustomEventDetail = (event: Event): CustomEventDetail | null => {
    if (!(typeof CustomEvent === 'function' && event instanceof CustomEvent)) {
        return null;
    }
    const detail = event.detail;
    if (!isObject(detail)) {
        return null;
    }
    return detail;
};

const bindHeaderGlobalEvents = (context: HeaderEventsContext): void => {
    const eventHub = context.getEventHubTarget();

    context.on(eventHub, 'soai:language:changed', () => {
        context.applyLocalization();
        context.controllers.clock.refresh();
    });

    context.on(eventHub, 'soai:localization:changed', () => {
        context.controllers.clock.refresh();
    });

    context.on(eventHub, CLOCK_PREFERENCES_CHANGED_EVENT, () => {
        context.controllers.clock.refresh();
    });

    context.on(eventHub, 'themeChanged', (event: Event) => {
        const detail = readCustomEventDetail(event);
        const themeValue = detail ? detail['theme'] : undefined;
        context.controllers.theme.handleThemeEvent(isString(themeValue) ? themeValue : undefined);
    });
};

export { applyHeaderLocalization, bindHeaderGlobalEvents, bindHeaderSidebarCollapse, setupHeaderGlobalClickHandler };
