/* SoAI - Shared layout header [frontend/assets/ts/core/layout/header/Header.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { getBranding } from '@core/branding/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { getEventHub } from '@core/environment/public.ts';
import { measureLayoutViewport } from '@core/layout/elementGeometry.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { LifecycleModel } from '@core/LifecycleModel.ts';
import { resolveKernelService, resolveOptionalKernelService } from '@core/runtime/runtimeContext.ts';
import { isArray, isFunction, isString, isThenable } from '@core/typeGuards.ts';
import { createLayoutFrameManager } from '@core/primitives/layoutFrameManager.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { defineHeaderActions } from '@core/layout/header/actions.ts';
import { createHeaderControllerBundle } from '@core/layout/header/adapters.ts';
import { isSidebarService, isStorageService } from '@core/layout/header/contracts.ts';
import { optionalDocumentHTMLElement } from '@core/layout/header/dom.ts';
import { DYNAMIC_TITLE_COMPONENTS, HEADER_SELECTORS, isHeaderDomKey, type ClockFormat, type CloseDropdownsOptions, type HeaderController } from '@core/layout/header/state.ts';
import { bindHeaderActionBridge, bindHeaderHamburgerMenu, cleanupHeaderActionBridge, escapeHeaderValue, handleHeaderLogout, hideHeaderNotificationCenter, loadHeaderIcons, logHeaderMessage, normalizeCloseDropdownExclusions, replaceHeaderNodeMarkup } from '@core/layout/header/effects.ts';
import { applyHeaderLocalization, bindHeaderGlobalEvents, bindHeaderSidebarCollapse, setupHeaderGlobalClickHandler } from '@core/layout/header/events.ts';
import { createHeaderIconsService } from '@core/layout/header/service.ts';
import type { HeaderControllers, HeaderEscapableValue, HeaderServiceGuard, HeaderServiceValue, IconsService, LayoutFrameManager, StorageService } from '@core/layout/HeaderInterface.ts';
import { LOG_ID, SHORT_LOG_ID } from '@core/layout/header/HeaderSupport.ts';
import type { TelemetryValue } from '@core/telemetry/contracts.ts';
class LayoutHeader extends LifecycleModel {
    readonly icons: IconsService;
    readonly controllers: HeaderControllers;
    readonly hiddenClass: string;
    #serviceCache: Map<string, HeaderServiceValue>;
    #domRegistry: Map<string, HTMLElement | null>;
    #layoutFrameManager: LayoutFrameManager | null;
    #hamburgerDispose: (() => void) | null;
    #controllerOrder: HeaderController[];
    #actionEventDisposers: (() => void)[];
    #storageService: StorageService | null;
    #eventHub: EventTarget;
    constructor() {
        super({ name: 'LayoutHeader', type: 'component' });
        this.hiddenClass = CSS_CLASSES.HIDDEN;
        this.#serviceCache = new Map();
        this.#domRegistry = new Map();
        this.#layoutFrameManager = null;
        this.#hamburgerDispose = null;
        this.#actionEventDisposers = [];
        this.#storageService = null;
        this.#eventHub = getEventHub();
        this.icons = createHeaderIconsService((node, markup) => {
            replaceHeaderNodeMarkup(node, markup);
        });
        const resolveHeaderService = <T extends HeaderServiceValue>(serviceId: string, guard?: HeaderServiceGuard<T> | undefined, label?: string | undefined): HeaderServiceValue | T => {
            if (!guard) {
                return this.#resolveService(serviceId);
            }
            return this.#resolveService(serviceId, guard, label);
        };
        const created = createHeaderControllerBundle({
            dom: {
                getDom: (key) => this.getDom(key),
                getDomMany: (keys) => this.getDomMany(keys),
                removeClassName: (element, className) => this.lifecycleDom.removeClass(element, className),
                updateProperty: (element, property, value) => this.lifecycleDom.updateProperty(element, property, value),
                addClassName: (element, className) => this.lifecycleDom.addClass(element, className),
                updateAttribute: (element, attr, value) => this.lifecycleDom.updateAttribute(element, attr, value),
                updateHTML: (element, html, options) => this.lifecycleDom.updateHtml(element, html, options),
                updateText: (element, text) => this.lifecycleDom.updateText(element, text),
                optionalUI: (selector, context) => this.lifecycleDom.optional(selector, context),
                optionalHTMLElement: (selector, context) => this.lifecycleDom.optionalHTMLElement(selector, context)
            },
            lifecycle: {
                on: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler),
                setTimer: (callback, delay, options) => {
                    const timerOptions = options && typeof options.repeat === 'boolean' ? { repeat: options.repeat } : undefined;
                    return this.lifecycleResources.setTimer(callback, delay, timerOptions);
                },
                clearTimer: (id) => this.lifecycleResources.clearTimer(id),
                getLayoutFrameManager: () => this.layoutFrameManager
            },
            services: {
                resolveService: resolveHeaderService,
                getStorage: () => this.getStorage(),
                handleLogout: async () => await this.handleLogout()
            },
            presentation: {
                hiddenClass: this.hiddenClass,
                icons: this.icons,
                dynamicComponents: DYNAMIC_TITLE_COMPONENTS,
                closeDropdowns: this.closeDropdowns,
                getClockFormat: () => this.getClockFormat(),
                updateLogosForTheme: () => getBranding().updateAllLogos(),
                isMobilePortrait: () => this.isMobilePortrait(),
                escape: (value) => escapeHeaderValue(value),
                logger: (level, message, data) => logHeaderMessage(level, message, data)
            }
        });
        this.controllers = created.controllers;
        this.#controllerOrder = created.order;
    }
    get layoutFrameManager(): LayoutFrameManager | null {
        return this.#layoutFrameManager;
    }
    async initialize(): Promise<void> {
        if (this.isInitialized || this.isDestroyed) {
            if (!this.isDestroyed) {
                await this.destroy();
            }
            this.resetLifecycleState();
        }
        await this.initializeLifecycle();
    }
    override async onInitialize(): Promise<void> {
        await this.lifecycleResources.cleanup();
        this.resetCaches();
        defineHeaderActions();
        this.#actionEventDisposers = bindHeaderActionBridge({ on: (target, eventName, handler) => this.lifecycleResources.addEventListener(target, eventName, handler), getEventHubTarget: () => this.getEventHubTarget() });
        this.#layoutFrameManager = createLayoutFrameManager();
        this.#storageService = this.resolveService('core.storage', isStorageService, 'Header storage');
        for (const controller of this.#controllerOrder) {
            if (!isFunction(controller.initialize)) continue;
            const result = controller.initialize();
            if (isThenable(result)) await result;
        }
        await loadHeaderIcons({ getDom: (key) => this.getDom(key), icons: this.icons });
        this.#hamburgerDispose = bindHeaderHamburgerMenu(this.#hamburgerDispose, { getDom: (key) => this.getDom(key), on: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler), handleClick: async (event) => await this.handleHamburgerClick(event) });
        bindHeaderSidebarCollapse({ getDom: (key) => this.getDom(key), resolveSidebar: () => this.resolveService('core.layout.sidebar', isSidebarService, 'Sidebar service'), isMobilePortrait: () => this.isMobilePortrait(), on: (target, event, handler, options) => this.lifecycleResources.addEventListener(target, event, handler, options) });
        applyHeaderLocalization({ controllers: this.controllers, controllerOrder: this.#controllerOrder, getDom: (key) => this.getDom(key) });
        setupHeaderGlobalClickHandler({ getDomMany: (keys) => this.getDomMany(keys), closeDropdowns: this.closeDropdowns, on: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler) });
        bindHeaderGlobalEvents({
            on: (target, event, handler) => this.lifecycleResources.addEventListener(target, event, handler),
            getEventHubTarget: () => this.getEventHubTarget(),
            applyLocalization: () => this.applyLocalization(),
            controllers: this.controllers
        });
        this.controllers.responsive.refresh();
        this.controllers.title.refreshDisplayedTitle();
        errorHandler.info(LOG_ID, 'Header initialized');
    }
    override async onDestroy(): Promise<void> {
        await this.lifecycleResources.cleanup();
        if (isFunction(this.#hamburgerDispose)) this.#hamburgerDispose();
        this.#hamburgerDispose = null;
        for (const controller of this.#controllerOrder) {
            if (isFunction(controller.destroy)) controller.destroy();
        }
        if (this.#layoutFrameManager) this.#layoutFrameManager.cancel();
        this.#layoutFrameManager = null;
        this.#storageService = null;
        this.resetCaches();
        cleanupHeaderActionBridge(this.#actionEventDisposers);
        this.#actionEventDisposers = [];
    }
    resetCaches(): void {
        this.#domRegistry.clear();
        this.#serviceCache.clear();
        this.icons.reset();
    }
    resolveService(serviceId: string): HeaderServiceValue;
    resolveService<T extends HeaderServiceValue>(serviceId: string, guard: HeaderServiceGuard<T>, label?: string | undefined): T;
    resolveService<T extends HeaderServiceValue>(serviceId: string, guard?: HeaderServiceGuard<T> | undefined, label?: string | undefined): HeaderServiceValue {
        if (!guard) return this.#resolveService(serviceId);
        return this.#resolveService(serviceId, guard, label);
    }
    #resolveService(serviceId: string): HeaderServiceValue;
    #resolveService<T extends HeaderServiceValue>(serviceId: string, guard: HeaderServiceGuard<T>, label?: string | undefined): T;
    #resolveService<T extends HeaderServiceValue>(serviceId: string, guard?: HeaderServiceGuard<T> | undefined, label?: string | undefined): HeaderServiceValue {
        const token = isString(serviceId) ? serviceId.trim() : '';
        if (!token) {
            throw new Error('Header resolveService requires a non-empty serviceId');
        }
        if (this.#serviceCache.has(token)) {
            const cached = this.#serviceCache.get(token);
            if (cached === undefined) {
                throw new Error(`Header service cache corrupted for ${token}`);
            }
            if (guard && !guard(cached)) {
                throw new Error(`${label || token} service does not match the required interface`);
            }
            return cached;
        }
        const value = resolveKernelService(token);
        this.#serviceCache.set(token, value);
        if (guard && !guard(value)) {
            throw new Error(`${label || token} service does not match the required interface`);
        }
        return value;
    }
    resolveOptionalService(target: string): HeaderServiceValue {
        const token = isString(target) ? target.trim() : '';
        if (!token) return null;
        return resolveOptionalKernelService(token);
    }
    readonly closeDropdowns = (options: CloseDropdownsOptions = {}): void => {
        const exclusions = normalizeCloseDropdownExclusions(options);
        if (!exclusions.has('search')) {
            this.controllers.search.collapse({ blur: false });
        }
        if (!exclusions.has('notifications')) {
            hideHeaderNotificationCenter({ resolveOptionalService: (serviceId) => this.resolveOptionalService(serviceId) });
        }
        if (!exclusions.has('settings') && this.controllers.menu) {
            this.controllers.menu.hide();
        }
        if (!exclusions.has('user') && this.controllers.user) {
            this.controllers.user.hide();
        }
    };
    private getDom(key: string): HTMLElement | null {
        if (!isHeaderDomKey(key)) return null;
        if (this.#domRegistry.has(key)) return this.#domRegistry.get(key) ?? null;
        const selector = HEADER_SELECTORS[key];
        const node = selector ? optionalDocumentHTMLElement(selector) : null;
        this.#domRegistry.set(key, node);
        return node;
    }
    private getDomMany(keys: string[]): (HTMLElement | null)[] {
        return (isArray(keys) ? keys : []).map((key) => this.getDom(key));
    }
    private isMobilePortrait(): boolean {
        const { width, height } = measureLayoutViewport();
        return width <= 767 && height > width;
    }
    async handleHamburgerClick(event: Event): Promise<void> {
        event.preventDefault();
        event.stopImmediatePropagation();
        try {
            const sidebar = this.resolveService('core.layout.sidebar', isSidebarService, 'Sidebar service');
            const result = sidebar.toggle();
            if (isThenable(result)) await result;
        } catch (error) {
            const runtimeError = ensureError(error);
            errorHandler.warn(SHORT_LOG_ID, 'Sidebar toggle failed', runtimeError);
        }
    }
    updateLogosForTheme(): void {
        getBranding().updateAllLogos();
    }
    applyLocalization(): void {
        defineHeaderActions();
        applyHeaderLocalization({ controllers: this.controllers, controllerOrder: this.#controllerOrder, getDom: (key) => this.getDom(key) });
    }
    private async handleLogout(): Promise<void> {
        const resolveHeaderService = <T extends HeaderServiceValue>(serviceId: string, guard?: HeaderServiceGuard<T> | undefined, label?: string | undefined): HeaderServiceValue | T => {
            if (!guard) {
                return this.#resolveService(serviceId);
            }
            return this.#resolveService(serviceId, guard, label);
        };
        await handleHeaderLogout({ resolveService: resolveHeaderService });
    }
    setClockFormat(format: ClockFormat): void {
        const normalized: ClockFormat = format === '12h' ? '12h' : '24h';
        this.getStorage().setClockFormat(normalized);
    }
    private getClockFormat(): ClockFormat {
        return this.getStorage().getClockFormat() === '12h' ? '12h' : '24h';
    }
    getEventHubTarget(): EventTarget {
        if (!this.#eventHub) this.#eventHub = getEventHub();
        return this.#eventHub;
    }
    private getStorage(): StorageService {
        if (!this.#storageService) throw new Error('Header storage service is not initialized');
        return this.#storageService;
    }
    escape(value: HeaderEscapableValue): string {
        return escapeHeaderValue(value);
    }
    logger(level: string, message: string, data?: TelemetryValue): void {
        logHeaderMessage(level, message, data);
    }
}
export { LayoutHeader };
