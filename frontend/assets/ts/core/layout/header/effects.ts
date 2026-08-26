/* SoAI - Shared layout header effects [frontend/assets/ts/core/layout/header/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { bindHeaderActionEventBridge, disposeHeaderActionEventBridge } from '@core/layout/header/actions.ts';
import { isAuthService, isNotificationCenterHideHost } from '@core/layout/header/contracts.ts';
import { optionalChildHTMLElement } from '@core/layout/header/dom.ts';
import type { CloseDropdownsOptions } from '@core/layout/header/state.ts';
import { createHeaderIconTargets } from '@core/layout/header/view.ts';
import type { HeaderEscapableValue, HeaderServiceResolver, HeaderServiceValue, IconsService } from '@core/layout/HeaderInterface.ts';
import { NOTIFICATIONS_CENTER_SERVICE_ID } from '@core/notifications/protocols.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
import { filterTrimmedStringArrayValue } from '@core/types/payloadArrayReaders.ts';
import { isArray, isFunction, isObject, isString, isThenable } from '@core/typeGuards.ts';
import { requireDialogsService } from '@core/ui/modals/dialogs/service.ts';

interface HeaderActionBridgeContext {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getEventHubTarget: () => EventTarget;
}

interface HeaderLogoutContext {
    resolveService: HeaderServiceResolver;
}

interface HeaderNotificationCenterContext {
    resolveOptionalService: (serviceId: string) => HeaderServiceValue;
}

interface HeaderIconLoadContext {
    getDom: (key: string) => HTMLElement | null;
    icons: IconsService;
}

const shortLogId = 'Header';

const bindHeaderActionBridge = (context: HeaderActionBridgeContext): (() => void)[] => {
    return bindHeaderActionEventBridge({
        on: (target, eventName, handler) => context.on(target, eventName, handler),
        getEventHubTarget: () => context.getEventHubTarget()
    });
};

const cleanupHeaderActionBridge = (disposers: (() => void)[]): void => {
    disposeHeaderActionEventBridge(disposers);
};

const handleHeaderLogout = async (context: HeaderLogoutContext): Promise<void> => {
    const auth = context.resolveService('core.auth', isAuthService, 'Auth');
    if (!auth.isAuthenticated) {
        return;
    }
    const confirmed = await requireDialogsService().showConfirmation({
        title: i18n.t('header.menu.logout'),
        message: i18n.t('header.confirmations.logoutMessage'),
        confirmText: i18n.t('header.menu.logout'),
        variant: 'warning'
    });
    if (!confirmed || !isFunction(auth.logout)) {
        return;
    }
    try {
        await auth.logout();
    } catch (error) {
        const runtimeError = ensureError(error);
        errorHandler.warn(shortLogId, 'Logout failed', runtimeError);
    }
};

const hideHeaderNotificationCenter = (context: HeaderNotificationCenterContext): void => {
    const notificationCenter = context.resolveOptionalService(NOTIFICATIONS_CENTER_SERVICE_ID);
    if (!isObject(notificationCenter)) {
        return;
    }
    if (!('isInitialized' in notificationCenter) || notificationCenter.isInitialized !== true) {
        return;
    }
    if (!isNotificationCenterHideHost(notificationCenter)) {
        errorHandler.error(shortLogId, 'NotificationCenter.hide must be a function');
        return;
    }
    const result = notificationCenter.hide();
    if (isThenable(result)) {
        void Promise.resolve(result).catch((error) => {
            const runtimeError = ensureError(error);
            errorHandler.warn(shortLogId, 'NotificationCenter.hide failed', runtimeError);
        });
    }
};

const escapeHeaderValue = (value: HeaderEscapableValue): string => {
    if (!isString(value)) {
        return String(value ?? '');
    }
    return value.replace(/[&<>"]|'/g, (token) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[token] ?? token);
};

const logHeaderMessage = (level: string, message: string, data?: TelemetryValue): void => {
    switch (level) {
        case 'debug':
            errorHandler.debug(shortLogId, message, data);
            break;
        case 'info':
            errorHandler.info(shortLogId, message, data);
            break;
        case 'warn':
            errorHandler.warn(shortLogId, message, data);
            break;
        case 'error':
            errorHandler.error(shortLogId, message, data);
            break;
        default:
            errorHandler.info(shortLogId, message, data);
    }
};

const loadHeaderIcons = async (context: HeaderIconLoadContext): Promise<void> => {
    const hamburger = context.getDom('hamburger');
    if (hamburger) {
        const hamburgerIcon = optionalChildHTMLElement(hamburger, '.hamburger-icon');
        if (hamburgerIcon) {
            const markup = context.icons.get('menu', { size: 22 });
            if (!markup) {
                throw new Error('Header hamburger menu icon is unavailable');
            }
            dom.setHTML(hamburgerIcon, markup, { escape: false });
        }
        const closeIcon = optionalChildHTMLElement(hamburger, '.close-icon');
        if (closeIcon) {
            const markup = context.icons.get('close', { size: 22 });
            if (!markup) {
                throw new Error('Header hamburger close icon is unavailable');
            }
            dom.setHTML(closeIcon, markup, { escape: false });
        }
    }

    const targets = createHeaderIconTargets({
        searchContainer: context.getDom('searchContainer'),
        searchButton: context.getDom('searchButton'),
        notificationButton: context.getDom('notificationButton'),
        settingsButton: context.getDom('settingsButton'),
        userButton: context.getDom('userButton')
    });
    await context.icons.apply(targets);
};

const bindHeaderHamburgerMenu = (
    currentDisposer: (() => void) | null,
    context: {
        getDom: (key: string) => HTMLElement | null;
        on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
        handleClick: (event: Event) => Promise<void>;
    }
): (() => void) | null => {
    if (isFunction(currentDisposer)) {
        currentDisposer();
    }
    const hamburger = context.getDom('hamburger');
    if (!hamburger) {
        return null;
    }
    const disposer = context.on(hamburger, 'click', (event: Event) => {
        terminateHandledPromise(context.handleClick(event));
    });
    return isFunction(disposer) ? disposer : null;
};

const replaceHeaderNodeMarkup = (node: Element, markup: TrustedHtml): void => {
    const normalized = (markup.html ?? '').trim();
    if (!normalized) {
        dom.setText(node, '');
        return;
    }
    if (!(node instanceof HTMLElement) && !(typeof SVGElement === 'function' && node instanceof SVGElement)) {
        throw new Error('Header replaceNodeMarkup requires an HTMLElement or SVGElement');
    }
    const parent = node.parentElement;
    if (!parent) {
        dom.setHTML(node, markup, { escape: false });
        return;
    }
    const fragment = dom.createFragment(markup);
    if (fragment.childNodes.length > 0) {
        parent.insertBefore(fragment, node);
    }
    node.remove();
};

const normalizeCloseDropdownExclusions = (options: CloseDropdownsOptions): Set<string> => {
    const except = options['except'];
    return new Set(filterTrimmedStringArrayValue(isArray(except) ? except : [except]));
};

export { bindHeaderActionBridge, bindHeaderHamburgerMenu, cleanupHeaderActionBridge, escapeHeaderValue, handleHeaderLogout, hideHeaderNotificationCenter, loadHeaderIcons, logHeaderMessage, normalizeCloseDropdownExclusions, replaceHeaderNodeMarkup };
