/* SoAI - Shared layout account manager [frontend/assets/ts/core/layout/header/AccountManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import type { WebuiUser } from '@core/api/contracts/webuiUserContracts.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import type { HeaderServiceResolver } from '@core/layout/HeaderInterface.ts';
import { isFunction, isObject, isString } from '@core/typeGuards.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';

export interface AccountManagerHost {
    resolveService: HeaderServiceResolver;
    getDom: (key: string) => HTMLElement | null;
    optionalHTMLElement: (selector: string, context?: Element) => HTMLElement | null;
    addClassName: (element: Element, className: string | string[]) => void;
    removeClassName: (element: Element, className: string | string[]) => void;
    updateText: (element: Element, text: string) => void;
}

const MENU_USER_KEY = 'current-user';

interface MenuSelectors {
    [key: string]: string;
}

const MENU_SELECTORS: Readonly<MenuSelectors> = Object.freeze({
    [MENU_USER_KEY]: `[data-header-menu="${MENU_USER_KEY}"]`
});

interface MenuTargets {
    container: HTMLElement;
    wrapper: HTMLElement;
}

interface AccountManagerOptions {
    header: AccountManagerHost;
}

interface AuthService {
    onLogin: (callback: () => void) => () => void;
    onLogout: (callback: () => void) => () => void;
    getCurrentUser: () => WebuiUser | null;
    isAdmin: () => boolean;
}

export class AccountManager {
    header: AccountManagerHost;
    menuTargets: MenuTargets | null = null;
    #auth: AuthService | null = null;
    #unsubscribeLogin: (() => void) | null = null;
    #unsubscribeLogout: (() => void) | null = null;

    constructor({ header }: AccountManagerOptions) {
        this.header = header;
        this.menuTargets = null;
    }

    async initialize(): Promise<void> {
        this.resolveMenuTargets();
        this.#clearAuthDisposers();

        const isAuthService = <T>(value: T): value is T & AuthService => isObject(value) && 'onLogin' in value && isFunction(value.onLogin) && 'onLogout' in value && isFunction(value.onLogout) && 'getCurrentUser' in value && isFunction(value.getCurrentUser) && 'isAdmin' in value && isFunction(value.isAdmin);

        const auth = this.header.resolveService('core.auth', isAuthService, 'Auth');
        this.#auth = auth;
        try {
            this.#unsubscribeLogin = auth.onLogin(() => this.update());
            this.#unsubscribeLogout = auth.onLogout(() => this.update());
        } catch (subscriptionError) {
            this.#clearAuthDisposers();
            this.#auth = null;
            throw subscriptionError;
        }
        this.update();
    }

    destroy(): void {
        this.#clearAuthDisposers();
    }

    localize(): void {
        this.update();
    }

    resolveMenuTargets(forceRefresh: boolean = false): MenuTargets | null {
        if (!forceRefresh && this.menuTargets && this.menuTargets.container && this.menuTargets.wrapper) {
            return this.menuTargets;
        }
        const dropdown = this.header.getDom('userDropdown');
        if (!(dropdown instanceof HTMLElement)) {
            errorHandler.error('AccountManager', 'Header user dropdown must be an HTMLElement');
            return null;
        }
        const wrapper = this.header.getDom('userWrapper');
        if (!(wrapper instanceof HTMLElement)) {
            errorHandler.error('AccountManager', 'Header user wrapper must be an HTMLElement');
            return null;
        }
        const selector = MENU_SELECTORS[MENU_USER_KEY];
        if (!isString(selector)) {
            errorHandler.error('AccountManager', 'Menu selector not found');
            return null;
        }
        const container = this.header.optionalHTMLElement(selector, dropdown);
        if (!(container instanceof HTMLElement)) {
            errorHandler.error('AccountManager', 'Header user menu item must be an HTMLElement');
            return null;
        }
        this.menuTargets = { container: container, wrapper: wrapper };
        return this.menuTargets;
    }

    update(): void {
        const targets = this.resolveMenuTargets();
        if (!targets) {
            return;
        }
        const { container, wrapper } = targets;
        const auth = this.#auth;
        if (!auth) {
            errorHandler.error('AccountManager', 'Auth service is unavailable');
            return;
        }
        const user = auth.getCurrentUser();
        const username = user?.username ?? '';
        if (!username) {
            this.header.addClassName(wrapper, 'u-hidden');
            return;
        }
        dom.toggleClass(wrapper, 'u-hidden', false);
        const isAdminUser = auth.isAdmin();
        const label = this.header.optionalHTMLElement('.user-dropdown-text', container);
        if (label) {
            this.header.updateText(label, username);
            setTooltipText(label, username);
        }
        const roleBadge = this.header.optionalHTMLElement('.user-dropdown-role', container);
        if (roleBadge) {
            this.header.removeClassName(roleBadge, 'status-orange status-green');
            this.header.addClassName(roleBadge, isAdminUser ? 'status-orange' : 'status-green');
            this.header.updateText(roleBadge, isAdminUser ? i18n.t('header.roles.admin') : i18n.t('header.roles.user'));
        }
    }

    #clearAuthDisposers(): void {
        const unsubscribeLogin = this.#unsubscribeLogin;
        this.#unsubscribeLogin = null;
        unsubscribeLogin?.();
        const unsubscribeLogout = this.#unsubscribeLogout;
        this.#unsubscribeLogout = null;
        unsubscribeLogout?.();
    }
}
