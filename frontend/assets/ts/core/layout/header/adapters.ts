/* SoAI - Shared frontend layout header adapters [frontend/assets/ts/core/layout/header/adapters.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { DomPropertyValue } from '@core/dom/propertyValues.ts';
import { AccountManager, type AccountManagerHost } from '@core/layout/header/AccountManager.ts';
import { ActionZoneManager, type ActionZoneManagerHost } from '@core/layout/header/actionzonemanager/service.ts';
import { ClockManager, type ClockManagerHost } from '@core/layout/header/ClockManager.ts';
import { LicensingShortcutController } from '@core/layout/header/LicensingShortcutController.ts';
import { ResponsiveManager } from '@core/layout/header/ResponsiveManager.ts';
import { RestartReminderManager, type RestartReminderHost } from '@core/layout/header/RestartReminderManager.ts';
import { HeaderSearchManager } from '@core/layout/header/searchmanager/service.ts';
import type { SearchManagerHost } from '@core/layout/header/searchmanager/types.ts';
import { SettingsMenuManager, type SettingsMenuManagerHost } from '@core/layout/header/settingsmenumanager/public.ts';
import type { ClockFormat, HeaderControllerBundle } from '@core/layout/header/state.ts';
import { ThemeManager, type ThemeManagerHost } from '@core/layout/header/ThemeManager.ts';
import { TitleManager } from '@core/layout/header/titlemanager/service.ts';
import type { TitleManagerHost } from '@core/layout/header/titlemanager/types.ts';
import { UserMenuManager, type UserMenuManagerHost } from '@core/layout/header/UserMenuManager.ts';
import type { HeaderEscapableValue, HeaderServiceResolver, IconsService } from '@core/layout/HeaderInterface.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';

interface HeaderDomOperations {
    getDom: (key: string) => HTMLElement | null;
    getDomMany: (keys: string[]) => (HTMLElement | null)[];
    removeClassName: (element: Element, className: string | string[]) => void;
    updateProperty: (element: HTMLElement, property: string, value: DomPropertyValue) => void;
    addClassName: (element: Element, className: string | string[]) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    updateHTML: (element: HTMLElement, html: TrustedHtml | string, options: { escape: boolean }) => void;
    updateText: (element: Element, text: string) => void;
    optionalUI: (selector: string, context?: Element) => Element | null;
    optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null;
}

interface HeaderLifecycleOperations {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    setTimer: (callback: () => void, delay: number, options?: { repeat?: boolean | undefined }) => number | null;
    clearTimer: (id: number | null) => void;
    getLayoutFrameManager: () => { queue: (callback: () => void) => void; cancel: () => void } | null;
}

interface HeaderServiceAccess {
    resolveService: HeaderServiceResolver;
    getStorage: () => {
        getClockFormat: () => ClockFormat;
        getHeaderClockEnabled: () => boolean;
        getClockSecondsEnabled: () => boolean;
        getTheme: () => string | null;
        setTheme: (theme: string) => void;
        addRecentSearch: (query: string) => void;
    };
    handleLogout: () => Promise<void>;
}

interface HeaderPresentationState {
    hiddenClass: string;
    icons: IconsService;
    dynamicComponents: Set<string>;
    closeDropdowns: (options?: { except?: string | string[] | undefined }) => void;
    getClockFormat: () => ClockFormat;
    updateLogosForTheme: () => void;
    isMobilePortrait: () => boolean;
    escape: (value: HeaderEscapableValue) => string;
    logger: (level: string, message: string, data?: TelemetryValue) => void;
}

interface HeaderControllerFactoryContext {
    dom: HeaderDomOperations;
    lifecycle: HeaderLifecycleOperations;
    services: HeaderServiceAccess;
    presentation: HeaderPresentationState;
}

const createHeaderControllerBundle = ({ dom, lifecycle, services, presentation }: HeaderControllerFactoryContext): HeaderControllerBundle => {
    const actionHost: ActionZoneManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        getDom: (key) => dom.getDom(key),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value),
        updateText: (element, text) => dom.updateText(element, text),
        removeClassName: (element, className) => dom.removeClassName(element, className),
        addClassName: (element, className) => dom.addClassName(element, className),
        logger: (level, message, data) => presentation.logger(level, message, data),
        icons: presentation.icons
    };

    const searchHost: SearchManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        getDom: (key) => dom.getDom(key),
        closeDropdowns: (options) => presentation.closeDropdowns(options),
        setTimer: (callback, delay, options) => lifecycle.setTimer(callback, delay, options),
        clearTimer: (id) => lifecycle.clearTimer(id),
        removeClassName: (element, className) => dom.removeClassName(element, className),
        updateProperty: (element, property, value) => dom.updateProperty(element, property, value),
        addClassName: (element, className) => dom.addClassName(element, className),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value),
        updateHTML: (element, html, options) => dom.updateHTML(element, html, options),
        resolveService: services.resolveService,
        escape: (value) => presentation.escape(value),
        logger: (level, message, data) => presentation.logger(level, message, data),
        getStorage: () => services.getStorage(),
        icons: presentation.icons
    };

    const settingsHost: SettingsMenuManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        getDomMany: (keys) => dom.getDomMany(keys),
        closeDropdowns: (options) => presentation.closeDropdowns(options),
        logger: (level, message, data) => presentation.logger(level, message, data),
        updateText: (element, text) => dom.updateText(element, text),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value),
        handleLogout: async () => await services.handleLogout(),
        resolveService: services.resolveService
    };

    const userHost: UserMenuManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        getDomMany: (keys) => dom.getDomMany(keys),
        closeDropdowns: (options) => presentation.closeDropdowns(options),
        addClassName: (element, className) => dom.addClassName(element, className),
        removeClassName: (element, className) => dom.removeClassName(element, className),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value),
        updateText: (element, text) => dom.updateText(element, text),
        optionalHTMLElement: (selector, root) => dom.optionalHTMLElement(selector, root),
        handleLogout: async () => await services.handleLogout(),
        resolveService: services.resolveService
    };

    const themeHost: ThemeManagerHost = {
        getStorage: () => services.getStorage(),
        updateLogosForTheme: () => presentation.updateLogosForTheme()
    };

    const clockHost: ClockManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        getDomMany: (keys) => dom.getDomMany(keys),
        getClockFormat: () => presentation.getClockFormat(),
        getHeaderClockEnabled: () => services.getStorage().getHeaderClockEnabled(),
        getClockSecondsEnabled: () => services.getStorage().getClockSecondsEnabled(),
        clearTimer: (id) => lifecycle.clearTimer(id),
        setTimer: (callback, delay, options) => lifecycle.setTimer(callback, delay, options),
        updateText: (element, text) => dom.updateText(element, text),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value)
    };

    const restartHost: RestartReminderHost = {
        resolveService: services.resolveService
    };

    const accountHost: AccountManagerHost = {
        resolveService: services.resolveService,
        getDom: (key) => dom.getDom(key),
        optionalHTMLElement: (selector, root) => dom.optionalHTMLElement(selector, root),
        addClassName: (element, className) => dom.addClassName(element, className),
        removeClassName: (element, className) => dom.removeClassName(element, className),
        updateText: (element, text) => dom.updateText(element, text)
    };

    const actions = new ActionZoneManager({
        header: actionHost,
        hiddenClass: presentation.hiddenClass
    });
    const search = new HeaderSearchManager({ header: searchHost });
    const menu = new SettingsMenuManager({ header: settingsHost });
    const user = new UserMenuManager({ header: userHost });
    const theme = new ThemeManager({ header: themeHost });
    const clock = new ClockManager({ header: clockHost });
    const restart = new RestartReminderManager({ header: restartHost });
    const licensing = new LicensingShortcutController();
    const account = new AccountManager({ header: accountHost });
    const titleHost: TitleManagerHost = {
        on: (target, event, handler) => lifecycle.on(target, event, handler),
        resolveService: services.resolveService,
        getDom: (key) => dom.getDom(key),
        optionalHTMLElement: (selector, root) => dom.optionalHTMLElement(selector, root),
        updateText: (element, text) => dom.updateText(element, text),
        updateAttribute: (element, attr, value) => dom.updateAttribute(element, attr, value),
        isMobilePortrait: () => presentation.isMobilePortrait(),
        onSearchNavigation: (component) => search.onNavigation(component)
    };

    const title = new TitleManager({
        header: titleHost,
        dynamicComponents: presentation.dynamicComponents
    });
    const responsive = new ResponsiveManager({
        header: {
            getDom: (key) => dom.getDom(key),
            on: (target, event, handler) => lifecycle.on(target, event, handler),
            getLayoutFrameManager: () => lifecycle.getLayoutFrameManager(),
            refreshDisplayedTitle: () => title.refreshDisplayedTitle()
        }
    });

    const controllers = { actions, search, menu, user, theme, clock, restart, licensing, account, responsive, title };
    const order = [actions, licensing, search, menu, user, theme, clock, restart, account, responsive, title];
    return { controllers, order };
};

export { createHeaderControllerBundle };
