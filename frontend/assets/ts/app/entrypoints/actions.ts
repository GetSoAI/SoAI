/* SoAI - Frontend application actions [frontend/assets/ts/app/entrypoints/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { AppLifecycleInstance, BackendReadyOptions, DetachedParameters } from '@app/entrypoints/types.ts';
import { ensureBackendReady, type BackendReadyResult } from '@core/backendReady.ts';
import { bootstrap, finalizePreloader } from '@app/bootstrap/bootstrap.ts';
import { ensureBootstrapCore } from '@app/bootstrap/stages/bootstrapCore.ts';
import { initializeCoreServices } from '@app/bootstrap/stages/initializeCoreServices.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { getLanguageService } from '@core/languageservice/service.ts';
import { parseDetachedQuery } from '@core/runtime/detachedQuery.ts';
import { createDeferred } from '@core/runtime/deferred.ts';
import { resolveKernelService } from '@core/runtime/runtimeContext.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { preloadCommonIcons } from '@core/ui/icons/iconservice/public.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import { getElementByIdStrict, getEventHub, getGlobalScope, getLocation, requireDocument } from '@core/environment/public.ts';
import { dom } from '@core/dom/dom.ts';
import { getScrollModule } from '@core/scroll.ts';
import { initializeServerTimeClock } from '@core/time/serverTimeClock.ts';

const resolveGlobalScope = (): typeof globalThis => {
    const scope = getGlobalScope();
    if (!isObject(scope)) {
        throw new Error('Global scope is not available for app entry points');
    }
    return scope;
};

const isAppLifecycleInstance = <T>(value: T): value is T & AppLifecycleInstance => {
    if (!isObject(value)) return false;
    return 'bootstrap' in value && 'renderInitializationError' in value && isFunction(value.bootstrap) && isFunction(value.renderInitializationError);
};

const requireAppLifecycle = (): AppLifecycleInstance => {
    const candidate = resolveKernelService('core.appLifecycle');
    if (!isAppLifecycleInstance(candidate)) throw new Error('App lifecycle unavailable');
    return candidate;
};

const whenBackendReady = (options: BackendReadyOptions = {}): Promise<BackendReadyResult> => ensureBackendReady(options);

const resolveReadySignal = (): Promise<void> => {
    const deferred = createDeferred<void>();
    deferred.resolve();
    return deferred.promise;
};

const waitForDomReady = (): Promise<void> => {
    const doc = requireDocument();
    if (doc.readyState !== 'loading') {
        return resolveReadySignal();
    }
    const deferred = createDeferred<void>();
    const handleDomContentLoaded = (): void => {
        deferred.resolve();
    };
    doc.addEventListener('DOMContentLoaded', handleDomContentLoaded, { once: true });
    return deferred.promise;
};

const waitForWindowLoad = (): Promise<void> => {
    const doc = requireDocument();
    if (doc.readyState === 'complete') {
        return resolveReadySignal();
    }
    const deferred = createDeferred<void>();
    const handleWindowLoad = (): void => {
        deferred.resolve();
    };
    getEventHub().addEventListener('load', handleWindowLoad, { once: true });
    return deferred.promise;
};

const detachedParameters = (): DetachedParameters => {
    const locationRef = getLocation();
    const result = parseDetachedQuery(locationRef.search);
    return { pageId: result.pageId, parameters: {}, windowId: windowIdentity.current() };
};

const localizeStaticHtmlElements = (): void => {
    const doc = requireDocument();
    const appleTitleMeta = dom.resolve('meta[name="apple-mobile-web-app-title"]', doc);
    if (appleTitleMeta) {
        appleTitleMeta.setAttribute('content', i18n.t('header.brandName'));
    }

    const setText = (selector: string, text: string): void => {
        const target = dom.resolve(selector, doc);
        if (target) target.textContent = text;
    };

    const setAttribute = (selector: string, attribute: string, value: string): void => {
        const target = dom.resolve(selector, doc);
        if (target) target.setAttribute(attribute, value);
    };

    const preloaderText = dom.resolve('.page-preloader-text', doc);
    if (preloaderText) preloaderText.textContent = i18n.t('app.preloader.loading');
    const preloaderStatus = dom.resolve('.page-preloader-status', doc);
    if (preloaderStatus) preloaderStatus.textContent = i18n.t('app.preloader.starting');
    const preloaderLogo = dom.resolve('.page-preloader-logo', doc);
    if (preloaderLogo) preloaderLogo.setAttribute('alt', i18n.t('app.preloader.logoAlt'));

    setText('#restart-message', i18n.t('restartOverlay.messages.pleaseWait'));
    setText('#restart-description', i18n.t('restartOverlay.descriptions.generic'));
    setAttribute('#hamburger-menu', 'aria-label', i18n.t('header.actions.toggleMenu'));
    {
        const target = dom.resolve('#hamburger-menu', doc);
        if (target instanceof HTMLElement) setTooltipText(target, i18n.t('header.actions.menuTitle'));
    }
    setAttribute('#header-search-container', 'aria-label', i18n.t('header.search.containerAria'));
    setAttribute('#header-search-input', 'placeholder', i18n.t('header.search.placeholder'));
    setAttribute('#header-search-input', 'aria-label', i18n.t('header.search.placeholder'));
    {
        const target = dom.resolve('#header-search-button', doc);
        if (target instanceof HTMLElement) setTooltipText(target, i18n.t('header.search.open'));
    }
    setAttribute('#header-search-button', 'aria-label', i18n.t('header.search.open'));
    setAttribute('#settings-button', 'aria-label', i18n.t('header.actions.openSettings'));
    {
        const target = dom.resolve('#settings-button', doc);
        if (target instanceof HTMLElement) setTooltipText(target, i18n.t('header.actions.openSettings'));
    }
    setText('#goto-settings', i18n.t('header.menu.settings'));
    setText('#goto-logs', i18n.t('header.menu.logs'));
    setText('#goto-updates', i18n.t('header.menu.updates'));
    setText('#goto-about', i18n.t('header.menu.about'));
    setText('#settings-logout', i18n.t('header.menu.logout'));
    setAttribute('#user-button', 'aria-label', i18n.t('header.actions.openUserMenu'));
    {
        const target = dom.resolve('#user-button', doc);
        if (target instanceof HTMLElement) setTooltipText(target, i18n.t('header.actions.openUserMenu'));
    }
    setText('#logout', i18n.t('header.menu.logout'));
    setAttribute('#clock-button', 'aria-label', i18n.t('header.actions.toggleClockFormat'));
    {
        const target = dom.resolve('#clock-button', doc);
        if (target instanceof HTMLElement) setTooltipText(target, i18n.t('header.actions.toggleClockFormat'));
    }
    setAttribute('.sidebar-logo-large', 'alt', i18n.t('header.brandLogoAlt'));
    setAttribute('.sidebar-logo-small', 'alt', i18n.t('header.brandIconAlt'));
};

const ensureLanguageInitialized = async (): Promise<void> => {
    const languageService = getLanguageService();
    if (!languageService.initialized) {
        await languageService.initialize();
    }
    localizeStaticHtmlElements();
};

const ensureCommonIconsPreloaded = async (): Promise<void> => {
    await preloadCommonIcons();
};

const initializeScrollModule = (): void => {
    getScrollModule().initialize();
};

const renderDetachedError = (message: string): void => {
    const container = getElementByIdStrict('main-content');
    if (!isString(message) || !message.trim()) throw new Error('Detached error message is required');
    const resolvedMessage = message.trim();
    const title = i18n.t('detached.errors.initFailed');
    const scopedDoc = container.ownerDocument;
    if (!scopedDoc || !isFunction(scopedDoc.createElement)) {
        throw new Error('Detached error rendering requires a valid document');
    }
    const wrapper = scopedDoc.createElement('div');
    wrapper.className = 'detached-initialization-error';
    const heading = scopedDoc.createElement('h2');
    heading.textContent = title;
    const body = scopedDoc.createElement('p');
    body.textContent = resolvedMessage;
    wrapper.appendChild(heading);
    wrapper.appendChild(body);
    container.replaceChildren(wrapper);
    void finalizePreloader().catch((error) => {
        errorHandler.warn('Entrypoint', 'Preloader finalization failed while rendering detached error', ensureError(error));
    });
};

const ensureEntrypointBootstrapBase = async (): Promise<void> => {
    initializeServerTimeClock();
    await ensureBootstrapCore();
    await initializeCoreServices();
    bootstrap.start();
};

export { detachedParameters, ensureCommonIconsPreloaded, ensureEntrypointBootstrapBase, ensureLanguageInitialized, isAppLifecycleInstance, initializeScrollModule, localizeStaticHtmlElements, renderDetachedError, requireAppLifecycle, resolveGlobalScope, waitForDomReady, waitForWindowLoad, whenBackendReady };
