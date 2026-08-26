/* SoAI - Routed page service access, navigation, localization, icons, and clipboard ownership [frontend/assets/ts/core/routing/pages/basepagecore/PageServices.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ConfigurationManager } from '@core/configurationManager.ts';
import { dom, domCache } from '@core/dom/dom.ts';
import { getComputedStyleStrict, getLocation } from '@core/environment/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { ClipboardApi, PageContext } from '@core/pagecontext/public.ts';
import { requireModalPresenter, type ModalPresenterApi } from '@core/modals/modalPresenter.ts';
import { AUTH_ROUTE_LOGIN } from '@core/routing/router/authRouteTarget.ts';
import { err, request } from '@core/routing/pages/basepagecore/actions.ts';
import { applyPageIconMap } from '@core/routing/pages/basepagecore/iconMap.ts';
import { hidePageLoadingHandle, showPageLoadingHandle, withPageLoadingHandle, type PageLoadingHandle } from '@core/routing/pages/basepagecore/notifications.ts';
import { getPageCurrentRoute, loadPageStorageValue, navigatePageRoute, removePageStorageValue, resolvePageAuthenticated, savePageStorageValue } from '@core/routing/pages/basepagecore/storageRouting.ts';
import type { IconDefinition, LanguageService } from '@core/routing/pages/pagetypes/public.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import { getWindowService } from '@core/runtimeenv/public.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { monotonicMs } from '@core/time/clock.ts';
import { createDebouncedHandler, createThrottledHandler } from '@core/timers/scheduledHandlers.ts';
import { isJsonValue, type JsonValue } from '@core/types/jsonValues.ts';
import { isFunction, isString } from '@core/typeGuards.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import { getIcon, getIconFromString, getIconFromStringSync, getIconSync, type IconOptions } from '@core/ui/icons/iconservice/public.ts';
import type { NotificationType } from '@core/ui/notifications/notifications.ts';
import type { AuthManager } from '@core/auth/public.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import type { Router } from '@core/routing/router/Router.ts';
import type { loadingState } from '@core/loadingState.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';

interface PageServicesDependencies {
    pageId: string;
    pageContext: PageContext;
    loadingState: typeof loadingState;
    storage: StorageService;
    router: Router;
    auth: AuthManager;
    languageService: LanguageService;
    pageDom: PageDom;
    resources: PageResources;
}

class PageServices {
    readonly #dependencies: PageServicesDependencies;
    #clipboard: ClipboardApi | null = null;
    #detachedContextReady: Promise<JsonValue | null> | null = null;
    #languageReady: Promise<LanguageService> | null = null;

    constructor(dependencies: PageServicesDependencies) {
        this.#dependencies = dependencies;
    }

    clipboard(): ClipboardApi {
        return this.#clipboard || (this.#clipboard = this.#dependencies.pageContext.clipboard);
    }

    hasClipboardSupport(): boolean {
        return Boolean(this.clipboard().isSupported?.());
    }

    async copyToClipboard(text: string, options: { notify?: (message: string, type: NotificationType) => void } = {}): Promise<void> {
        await this.clipboard().copyText(text, {
            ...options,
            notify: isFunction(options.notify) ? options.notify : (message, type) => this.#dependencies.pageContext.notifications.show(message, type)
        });
    }

    clearDomCache(): void {
        domCache.clear();
    }

    getIcon(name: IconName, options?: IconOptions): Promise<TrustedHtml> {
        return getIcon(name, options);
    }

    getIconSync(name: IconName, options?: IconOptions): TrustedHtml {
        return getIconSync(name, options);
    }

    getIconFromString(name: string, options?: IconOptions): Promise<TrustedHtml> {
        return getIconFromString(name, options);
    }

    getIconFromStringSync(name: string, options?: IconOptions): TrustedHtml {
        return getIconFromStringSync(name, options);
    }

    applyIconMap(iconMap: Record<string, IconDefinition>, resolver?: (name: IconName, options?: IconOptions) => TrustedHtml): void {
        applyPageIconMap({ pageId: this.#dependencies.pageId, iconMap, queryUI: (selector) => this.#dependencies.pageDom.query(selector), updateHTML: (element, html, options) => this.#dependencies.pageDom.updateHtml(element, html, options), resolver: resolver ?? ((name, options) => this.getIconSync(name, options)) });
    }

    showLoading(message: string = i18n.t('common.loading')): PageLoadingHandle {
        return showPageLoadingHandle(this.#dependencies.loadingState, message);
    }

    hideLoading(handle: PageLoadingHandle | null): void {
        hidePageLoadingHandle(this.#dependencies.loadingState, handle);
    }

    async withLoading<T>(operation: () => Promise<T>, message: string = i18n.t('common.processing')): Promise<T> {
        return withPageLoadingHandle(this.#dependencies.loadingState, message, operation);
    }

    saveToStorage(key: string, value: JsonValue | null | undefined): void {
        savePageStorageValue(this.#dependencies.storage, key, value);
    }

    loadFromStorage(key: string, defaultValue: JsonValue | null = null): JsonValue | null {
        const value = loadPageStorageValue(this.#dependencies.storage, key, defaultValue);
        return isJsonValue(value) ? value : defaultValue;
    }

    removeFromStorage(key: string): void {
        removePageStorageValue(this.#dependencies.storage, key);
    }

    navigate(path: string, parameters: Record<string, string | null | undefined> = {}): void {
        navigatePageRoute(this.#dependencies.router, path, parameters);
    }

    currentRoute(): string | null {
        const route = getPageCurrentRoute(this.#dependencies.router);
        return isString(route) ? route : null;
    }

    isAuthenticated(): boolean {
        return resolvePageAuthenticated(this.#dependencies.auth);
    }

    async requireAuth(): Promise<void> {
        if (!this.isAuthenticated()) {
            this.navigate(AUTH_ROUTE_LOGIN, { redirect: this.currentRoute() });
            throw err('Authentication required');
        }
    }

    isDetached(): boolean {
        return windowIdentity.isDetachedContext();
    }

    async awaitDetachedContext(): Promise<void> {
        const pathname = getLocation().pathname || '';
        if (!(pathname.endsWith('/detached.html') || pathname === '/detached.html') || !this.isDetached()) return;
        if (!this.#detachedContextReady) {
            this.#detachedContextReady = Promise.resolve(request(getWindowService(), 'runtimeWindowService').awaitDetachedContext({ timeout: 8000 }));
        }
        await this.#detachedContextReady;
    }

    async ensureLanguageInitialized(): Promise<LanguageService> {
        const service = request(this.#dependencies.languageService, 'Language');
        this.#languageReady ??= Promise.resolve(service.initialize()).then(() => service);
        return this.#languageReady;
    }

    sanitizeText(value: string | null | undefined, options?: Record<string, string | null>): string {
        return this.#dependencies.pageContext.sanitizer.text(value, options);
    }

    sanitizeOptionalText(value: string | null | undefined, options?: Record<string, string | null>): string | null {
        return this.#dependencies.pageContext.sanitizer.optionalText(value, options);
    }

    sanitizeClassName(value: string | null | undefined, fallback: string | Record<string, string | null>, options?: Record<string, string | null>): string {
        return isString(fallback) ? this.#dependencies.pageContext.sanitizer.className(value, fallback, options) : this.#dependencies.pageContext.sanitizer.className(value, '', fallback);
    }

    createConfigurationManager(): ConfigurationManager {
        return request(new (request(ConfigurationManager, 'CM'))(), 'CM instance');
    }

    get modals(): ModalPresenterApi {
        return requireModalPresenter();
    }

    getStyleProperty(property: string, element?: Element): string {
        return getComputedStyleStrict(element || dom.getDocumentElement())
            .getPropertyValue(property)
            .trim();
    }

    createDebouncedHandler<TArguments extends (JsonValue | undefined)[]>(handler: (...inputArguments: TArguments) => void, delay = 300): ((...inputArguments: TArguments) => void) & { cancel: () => void } {
        return createDebouncedHandler(handler, delay, { setTimer: (callback, timeoutMs) => this.#requireTimer(callback, timeoutMs), clearTimer: (timerId) => this.#dependencies.resources.clearTimer(timerId), nowMs: monotonicMs });
    }

    createThrottledHandler<TArguments extends (JsonValue | undefined)[]>(handler: (...inputArguments: TArguments) => void, delay = 100): ((...inputArguments: TArguments) => void) & { cancel: () => void } {
        return createThrottledHandler(handler, delay, { setTimer: (callback, timeoutMs) => this.#requireTimer(callback, timeoutMs), clearTimer: (timerId) => this.#dependencies.resources.clearTimer(timerId), nowMs: monotonicMs });
    }

    #requireTimer(callback: () => void, timeoutMs: number): number {
        const timerId = this.#dependencies.resources.setTimeout(callback, timeoutMs);
        if (timerId === null) throw err('Failed to schedule page service timer');
        return timerId;
    }
}

export { PageServices };
export interface PageServicesOwnerHost {
    services: PageServices;
}
export type { PageServicesDependencies };
