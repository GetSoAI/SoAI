/* SoAI - Login page DOM contracts [frontend/assets/ts/pages/login/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowForm, narrowImage, narrowInput } from '@core/dom/narrowElement.ts';
import type { LoginUiRefs } from '@pages/login/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

type LoginDomHost = PageDomOwnerHost;

const requireForm = (host: LoginDomHost): HTMLFormElement => {
    return narrowForm(host.pageDom.requireHTMLElement('login-form'), 'Login form');
};

const requireUsername = (host: LoginDomHost): HTMLInputElement => {
    return narrowInput(host.pageDom.requireHTMLElement('username'), 'Login username field');
};

const requirePassword = (host: LoginDomHost): HTMLInputElement => {
    return narrowInput(host.pageDom.requireHTMLElement('password'), 'Login password field');
};

const requireLoginButton = (host: LoginDomHost): HTMLButtonElement => {
    return narrowButton(host.pageDom.requireHTMLElement('login-button'), 'Login submit button');
};

const requireLogo = (host: LoginDomHost): HTMLImageElement => {
    return narrowImage(host.pageDom.requireHTMLElement('login-logo'), 'Login logo');
};

export const optionalLoginRoot = (host: LoginDomHost): HTMLElement | null => host.pageDom.optionalHTMLElement('login-root');

export const requireLoginUi = (host: LoginDomHost): LoginUiRefs => {
    const root = host.pageDom.requireHTMLElement('login-root');
    return {
        root,
        logo: requireLogo(host),
        form: requireForm(host),
        username: requireUsername(host),
        password: requirePassword(host),
        loginButton: requireLoginButton(host),
        loginButtonText: host.pageDom.requireHTMLElement('login-button-text'),
        loginError: host.pageDom.requireHTMLElement('login-error')
    };
};
