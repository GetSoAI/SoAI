/* SoAI - Frontend settings menu ownership [frontend/assets/ts/core/layout/header/settingsmenumanager/SettingsMenuManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { dom } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { HeaderDropdownController } from '@core/layout/header/dropdownController.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import { getWindowService } from '@core/runtimeenv/public.ts';
import { isFunction } from '@core/typeGuards.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { MENU_ITEM_KEYS, isRouter, type ErrorHandlerInterface, type MenuItemEntry, type Router, type SettingsMenuManagerHost } from '@core/layout/header/settingsmenumanager/contracts.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

interface SettingsMenuManagerOptions {
    header: SettingsMenuManagerHost;
}

export class SettingsMenuManager {
    header: SettingsMenuManagerHost;
    button: HTMLElement | null = null;
    dropdown: HTMLElement | null = null;
    items: MenuItemEntry[] = [];
    itemMap: Map<string, HTMLElement> = new Map();
    errorHandler: ErrorHandlerInterface;
    readonly #dropdownController: HeaderDropdownController;
    #disposers: Array<() => void> = [];

    constructor({ header }: SettingsMenuManagerOptions) {
        this.header = header;
        if (!this.header || !isFunction(this.header.on)) {
            throw new Error('SettingsMenuManager requires a header with event binding support');
        }
        const windowService = getWindowService();
        if (!windowService || !isFunction(windowService.openDetached)) {
            throw new Error('SettingsMenuManager requires runtime window services');
        }
        const handler = errorHandler;
        if (!handler || !isFunction(handler.warn)) {
            throw new Error('SettingsMenuManager requires an error handler');
        }
        this.button = null;
        this.dropdown = null;
        this.items = [];
        this.itemMap = new Map();
        this.errorHandler = handler;
        this.#dropdownController = new HeaderDropdownController({ host: this.header, dropdownId: 'settings' });
    }

    #trackDisposer(disposer: (() => void) | void): void {
        if (typeof disposer === 'function') {
            this.#disposers.push(disposer);
        }
    }

    #disposeBindings(): void {
        drainCleanupStack(this.#disposers, (runtimeError) => {
            this.errorHandler.warn('Header', 'Settings menu binding cleanup failed', runtimeError);
        });
    }

    async initialize(): Promise<void> {
        this.#disposeBindings();
        const [button, dropdown] = this.header.getDomMany(['settingsButton', 'settingsDropdown']);
        this.button = button ?? null;
        this.dropdown = dropdown ?? null;
        if (!(this.button && this.dropdown)) {
            throw new Error('Settings menu markup is incomplete');
        }
        if (!isFunction(this.header.closeDropdowns)) {
            throw new Error('Settings menu requires header dropdown coordination support APIs');
        }
        this.#dropdownController.attach(this.button, this.dropdown);
        this.#trackDisposer(
            this.header.on(this.button, 'click', (event: Event) => {
                if (event.defaultPrevented) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                try {
                    this.header.closeDropdowns({ except: 'settings' });
                } catch (error) {
                    const runtimeError = ensureError(error);
                    this.errorHandler.warn('Header', 'Failed to close other dropdowns (settings continues)', runtimeError);
                    this.header.logger('warn', 'Failed to close other dropdowns (settings continues)', runtimeError);
                }
                try {
                    this.toggleDropdown();
                } catch (error) {
                    const runtimeError = ensureError(error);
                    this.errorHandler.warn('Header', 'Failed to toggle settings dropdown', runtimeError);
                    this.header.logger('warn', 'Failed to toggle settings dropdown', runtimeError);
                }
            })
        );
        this.buildMenuItems();
        this.localize();
    }

    destroy(): void {
        this.#disposeBindings();
        this.#dropdownController.reset();
        this.button = null;
        this.dropdown = null;
        this.items = [];
        this.itemMap.clear();
    }

    hide(): void {
        this.#dropdownController.hide();
    }

    show(): void {
        this.#dropdownController.show();
    }

    toggleDropdown(forceState: boolean | null = null): void {
        this.#dropdownController.toggle(forceState);
    }

    localize(): void {
        const localizeItem = (key: string, label: string): void => {
            const element = this.itemMap.get(key);
            if (!element) {
                return;
            }
            this.header.updateText(element, label);
            setTooltipText(element, label);
            this.header.updateAttribute(element, 'aria-label', label);
        };
        localizeItem('logs', i18n.t('header.menu.logs'));
        localizeItem('settings', i18n.t('header.menu.settings'));
        localizeItem('updates', i18n.t('header.menu.updates'));
        localizeItem('about', i18n.t('header.menu.about'));
        localizeItem('logout', i18n.t('header.menu.logout'));
        if (this.button) {
            const label = i18n.t('header.actions.openSettings');
            this.header.updateAttribute(this.button, 'aria-label', label);
            setTooltipText(this.button, label);
            this.header.updateAttribute(this.button, 'aria-haspopup', 'true');
            this.header.updateAttribute(this.button, 'aria-expanded', this.#dropdownController.isOpen() ? 'true' : 'false');
        }
    }

    buildMenuItems(): void {
        this.items = [];
        this.itemMap.clear();
        const router = this.header.resolveService('core.router', isRouter, 'Router');
        MENU_ITEM_KEYS.forEach((key) => {
            const element = this.findMenuItem(key);
            if (!element) {
                return;
            }
            const action = this.resolveAction(key, router);
            const item: MenuItemEntry = { key, element, action };
            this.items.push(item);
            this.itemMap.set(key, element);
            this.bindMenuItem(item);
        });
    }

    bindMenuItem(item: MenuItemEntry): void {
        const { element, action } = item;
        if (!element || !isFunction(action)) {
            return;
        }
        this.#trackDisposer(
            this.header.on(element, 'click', (event: Event) => {
                if (event.defaultPrevented) {
                    return;
                }
                event.preventDefault();
                event.stopImmediatePropagation();
                action();
                this.hide();
            })
        );
    }

    resolveAction(key: string, router: Router): () => void {
        switch (key) {
            case 'logs':
                return (): void => {
                    try {
                        const windowService = getWindowService();
                        if (!isFunction(windowService.getOpenWindows) || !isFunction(windowService.closeWindow) || !isFunction(windowService.openDetached)) {
                            throw new Error('Logs detached service is unavailable');
                        }
                        const openWindows = windowService.getOpenWindows();
                        for (const openWindow of openWindows) {
                            if (openWindow.pageId === 'logs') {
                                windowService.closeWindow(openWindow.windowId);
                            }
                        }
                        windowService.openDetached('logs', {
                            title: i18n.t('logs.windowTitle')
                        });
                    } catch (error) {
                        const runtimeError = ensureError(error);
                        this.errorHandler.warn('Header', 'Failed to open logs detached window', runtimeError);
                        this.header.logger('warn', 'Failed to open logs detached window', runtimeError);
                    }
                };
            case 'settings':
                return (): void => terminateHandledPromise(router.navigate('settings'));
            case 'updates':
                return (): void => terminateHandledPromise(router.navigate('updates'));
            case 'about':
                return (): void => terminateHandledPromise(router.navigate('about'));
            case 'logout':
                return (): void => {
                    terminateHandledPromise(this.header.handleLogout());
                };
            default:
                return (): void => {};
        }
    }

    findMenuItem(key: string): HTMLElement | null {
        if (!this.dropdown) {
            return null;
        }
        const element = dom.resolve(`[data-header-menu="${key}"]`, this.dropdown);
        return element instanceof HTMLElement ? element : null;
    }

    getMenuItem(key: string): HTMLElement | null {
        return this.itemMap.get(key) || null;
    }
}

export type { SettingsMenuManagerHost };
