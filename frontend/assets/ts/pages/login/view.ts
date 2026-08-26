/* SoAI - Login page rendering [frontend/assets/ts/pages/login/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';
import { renderSecretInputControl, resolveSecretInputType } from '@core/ui/secretInput.ts';
import { LOGIN_ACTION_OPEN_DOCUMENTATION, LOGIN_ACTION_SUBMIT } from '@pages/login/actions.ts';

interface Sanitizer {
    html(value: string): string;
    attribute(value: string): string;
}

export const renderLoginPageView = (dependencies: { sanitizer: Sanitizer }): string => {
    const sanitizer = dependencies.sanitizer;
    const usernameLabel = sanitizer.html(i18n.t('login.usernameLabel'));
    const usernamePlaceholder = sanitizer.attribute(i18n.t('login.usernamePlaceholder'));
    const passwordLabel = sanitizer.html(i18n.t('login.passwordLabel'));
    const passwordPlaceholder = sanitizer.attribute(i18n.t('login.passwordPlaceholder'));
    const signInTitle = sanitizer.attribute(i18n.t('login.signInButton'));
    const passwordType = resolveSecretInputType();
    const passwordInput = `<input type="${passwordType}" id="password" name="password" required autocomplete="current-password"
                                       class="form-input secret-input" placeholder="${passwordPlaceholder}">`;
    const documentationLinkPlaceholder = 'DOCUMENTATION_LINK_PLACEHOLDER';
    const helpTextEscaped = sanitizer.html(i18n.t('login.helpText', { documentationLink: documentationLinkPlaceholder }));
    const documentationLabel = sanitizer.html(i18n.t('login.helpTextDocumentationLabel'));
    const documentationHref = sanitizer.attribute(`${SOAI_WEBSITE_URL}/documentation`);
    const documentationLink = `<a class="login-help-link" href="${documentationHref}" data-action="${LOGIN_ACTION_OPEN_DOCUMENTATION}" rel="noopener noreferrer">${documentationLabel}</a>`;
    const helpText = helpTextEscaped.replace(documentationLinkPlaceholder, documentationLink);

    return `
        <div id="login-root" class="login-container" data-section="login" data-page-transition-surface="true">
            <div class="login-layout">
                <div class="login-card">
                    <div class="login-header">
                        <img id="login-logo" src="" alt="${sanitizer.attribute(i18n.t('login.logoAlt'))}" class="login-logo logo logo-ui" data-logo-type="ui" data-logo-variant="standard">
                        <h1>${sanitizer.html(i18n.t('login.welcomeTitle'))}</h1>
                        <p>${sanitizer.html(i18n.t('login.tagline'))}</p>
                    </div>

                    <form id="login-form" class="login-form" method="post">
                        <div class="form-group">
                            <label for="username">${usernameLabel}</label>
                            <input type="text" id="username" name="username" required autocomplete="username"
                                   class="form-input" placeholder="${usernamePlaceholder}">
                        </div>
                        <div class="form-group" id="password-section">
                            <label for="password">${passwordLabel}</label>
                            ${renderSecretInputControl({ inputId: 'password', inputMarkup: passwordInput })}
                        </div>

                        <button type="submit" id="login-button" class="ui-button ui-variant-accent login-button" data-action="${LOGIN_ACTION_SUBMIT}" aria-label="${signInTitle}" data-tooltip="${signInTitle}">
                            <span id="login-button-text">${sanitizer.html(i18n.t('login.signInButton'))}</span>
                        </button>

                        <div id="login-error" class="form-disclaimer form-disclaimer-error u-hidden"></div>
                    </form>

                    <div class="login-footer">
                        <p class="login-help-text">
                            ${helpText}
                        </p>
                    </div>
                </div>
            </div>

            <div class="login-background">
                <div class="login-background-pattern"></div>
            </div>
        </div>
    `;
};
