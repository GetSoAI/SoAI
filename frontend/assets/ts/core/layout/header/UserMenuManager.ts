/* SoAI - Shared layout user menu manager [frontend/assets/ts/core/layout/header/UserMenuManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { errorHandler } from '@core/errorHandler.ts';
import { drainCleanupStack } from '@core/lifecycle/cleanup.ts';
import { HeaderDropdownController } from '@core/layout/header/dropdownController.ts';
import { i18n } from '@core/i18n/index.ts';
import type { HeaderServiceResolver } from '@core/layout/HeaderInterface.ts';
import { isFunction, isObject } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

export interface UserMenuManagerHost {
    on: (target: EventTarget, event: string, handler: (event: Event) => void) => (() => void) | void;
    getDomMany: (keys: string[]) => (HTMLElement | null)[];
    closeDropdowns: (options?: { except?: string | string[] | undefined }) => void;
    addClassName: (element: Element, className: string | string[]) => void;
    removeClassName: (element: Element, className: string | string[]) => void;
    updateAttribute: (element: Element, attr: string, value: string) => void;
    updateText: (element: Element, text: string) => void;
    optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null;
    handleLogout: () => Promise<void>;
    resolveService: HeaderServiceResolver;
}

const MENU_LOGOUT_KEY = 'logout';
const MENU_CURRENT_USER_KEY = 'current-user';

interface UserMenuManagerOptions {
    header: UserMenuManagerHost;
}

interface RouterInterface {
    navigateWithQuery: (page: string, query: Record<string, string>) => void;
}

const isRouterInterface = <T>(value: T): value is T & RouterInterface => isObject(value) && 'navigateWithQuery' in value && isFunction(value.navigateWithQuery);

export class UserMenuManager {
    header: UserMenuManagerHost;
    button: HTMLElement | null = null;
    dropdown: HTMLElement | null = null;
    wrapper: HTMLElement | null = null;
    itemMap: Map<string, HTMLElement> = new Map();
    readonly #dropdownController: HeaderDropdownController;
    #disposers: Array<() => void> = [];

    constructor({ header }: UserMenuManagerOptions) {
        this.header = header;
        if (!this.header || !isFunction(this.header.on)) {
            throw new Error('UserMenuManager requires a header with event binding support');
        }
        this.button = null;
        this.dropdown = null;
        this.wrapper = null;
        this.itemMap = new Map();
        this.#dropdownController = new HeaderDropdownController({ host: this.header, dropdownId: 'user' });
    }

    #trackDisposer(disposer: (() => void) | void): void {
        if (typeof disposer === 'function') {
            this.#disposers.push(disposer);
        }
    }

    #disposeBindings(): void {
        drainCleanupStack(this.#disposers, (runtimeError) => {
            errorHandler.warn('Header', 'User menu binding cleanup failed', runtimeError);
        });
    }

    async initialize(): Promise<void> {
        this.#disposeBindings();
        const [button, dropdown, wrapper] = this.header.getDomMany(['userButton', 'userDropdown', 'userWrapper']);
        this.button = button ?? null;
        this.dropdown = dropdown ?? null;
        this.wrapper = wrapper ?? null;
        if (!(this.button && this.dropdown)) {
            throw new Error('User menu markup is incomplete');
        }
        if (!isFunction(this.header.closeDropdowns)) {
            throw new Error('User menu requires header dropdown coordination support APIs');
        }
        this.#dropdownController.attach(this.button, this.dropdown);
        this.#trackDisposer(
            this.header.on(this.button, 'click', (event: Event) => {
                event.preventDefault();
                event.stopPropagation();
                this.header.closeDropdowns({ except: 'user' });
                this.toggleDropdown();
            })
        );
        this.bindMenuItems();
        this.localize();
    }

    destroy(): void {
        this.#disposeBindings();
        this.#dropdownController.reset();
        this.button = null;
        this.dropdown = null;
        this.wrapper = null;
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
        if (this.button) {
            const label = i18n.t('header.actions.openUserMenu');
            this.header.updateAttribute(this.button, 'aria-label', label);
            setTooltipText(this.button, label);
            this.header.updateAttribute(this.button, 'aria-haspopup', 'true');
            this.header.updateAttribute(this.button, 'aria-expanded', this.#dropdownController.isOpen() ? 'true' : 'false');
        }
        const logoutElement = this.itemMap.get(MENU_LOGOUT_KEY);
        if (logoutElement) {
            const logoutLabel = i18n.t('header.menu.logout');
            this.header.updateText(logoutElement, logoutLabel);
            setTooltipText(logoutElement, logoutLabel);
            this.header.updateAttribute(logoutElement, 'aria-label', logoutLabel);
        }
    }

    bindMenuItems(): void {
        this.itemMap.clear();
        const router = this.header.resolveService('core.router', isRouterInterface, 'Router');
        const currentUserElement = this.findMenuItem(MENU_CURRENT_USER_KEY);
        if (currentUserElement) {
            this.itemMap.set(MENU_CURRENT_USER_KEY, currentUserElement);
            this.#trackDisposer(
                this.header.on(currentUserElement, 'click', (event: Event) => {
                    event.preventDefault();
                    router.navigateWithQuery('settings', { tab: 'users' });
                    this.hide();
                })
            );
        }
        const logoutElement = this.findMenuItem(MENU_LOGOUT_KEY);
        if (logoutElement) {
            this.itemMap.set(MENU_LOGOUT_KEY, logoutElement);
            this.#trackDisposer(
                this.header.on(logoutElement, 'click', (event: Event) => {
                    event.preventDefault();
                    this.header.handleLogout();
                    this.hide();
                })
            );
        }
    }

    findMenuItem(key: string): HTMLElement | null {
        if (!this.dropdown) {
            return null;
        }
        return this.header.optionalHTMLElement(`[data-header-menu="${key}"]`, this.dropdown);
    }

    getMenuItem(key: string): HTMLElement | null {
        return this.itemMap.get(key) || null;
    }

    showWrapper(): void {
        if (this.wrapper) {
            this.header.removeClassName(this.wrapper, 'u-hidden');
        }
    }

    hideWrapper(): void {
        if (this.wrapper) {
            this.header.addClassName(this.wrapper, 'u-hidden');
        }
        this.hide();
    }
}
