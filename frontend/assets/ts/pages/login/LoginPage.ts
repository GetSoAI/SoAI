/* SoAI - Login routed page [frontend/assets/ts/pages/login/LoginPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import { bindFormSubmit } from '@core/dom/formSubmit.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { getWindowOpen } from '@core/environment/public.ts';
import { AUTH_ROUTE_LOGIN } from '@core/routing/router/authRouteTarget.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { SOAI_WEBSITE_URL } from '@core/ui/branding/pageBranding.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { LOGIN_ACTION_OPEN_DOCUMENTATION, LOGIN_ACTION_SUBMIT, isLoginActionId } from '@pages/login/actions.ts';
import { clearLoginCooldown, initializeLoginUi, isLoginCooldownActive, redirectLoginToWizardIfNeeded, resolveLoginUiForPage, submitLoginForm, updateLoginStatusMessage } from '@pages/login/controllers/page/service.ts';
import type { LoginUiRefs } from '@pages/login/types.ts';
import { renderLoginPageView } from '@pages/login/view.ts';
import { LoginSession } from '@pages/login/controllers/page/LoginSession.ts';

export const PAGE_ID = AUTH_ROUTE_LOGIN;
export const PAGE_MODULE_ID = 'pages.LoginPage';

class LoginPage extends StaticBasePage {
    readonly #session: LoginSession;
    #ui: LoginUiRefs | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#session = new LoginSession({ auth: this.dependencies.auth, streaming: this.streaming, pageElements: this.pageElements, pageDom: this.pageDom, pageResources: this.pageResources, stateManager: this.dependencies.stateManager, storage: this.dependencies.storage });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        void parameters;
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return toTrustedHtml(renderLoginPageView({ sanitizer: this.pageContext.sanitizer }));
    }

    override async loadData(): Promise<void> {
        const needsWizardRedirect = await redirectLoginToWizardIfNeeded(this.#session);
        if (needsWizardRedirect) {
            return;
        }
        this.#ui = resolveLoginUiForPage(this.#session, this.#ui);
        await initializeLoginUi(this.#session, this.#ui);
    }

    bindPageEvents(): void {
        const ui = resolveLoginUiForPage(this.#session, this.#ui);
        this.#ui = ui;
        const signal = this.pageLifecycle.beginListeners();
        bindFormSubmit({
            root: ui.root,
            signal,
            form: ui.form,
            capture: true,
            onSubmit: ({ event }): void => {
                this.#handleSubmit(event);
            }
        });
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'LoginPage',
            isAction: isLoginActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ action, event }): void => {
                        if (action === LOGIN_ACTION_OPEN_DOCUMENTATION) {
                            event.preventDefault();
                            getWindowOpen()(`${SOAI_WEBSITE_URL}/documentation`, '_blank', 'noopener,noreferrer');
                            return;
                        }
                        if (action !== LOGIN_ACTION_SUBMIT) {
                            throw new Error('Unsupported login action');
                        }
                    }
                }
            }
        });
        const handleLoginInput = (event: Event): void => this.#handleInput(event);
        ui.root.addEventListener('input', handleLoginInput, { signal, capture: true });
    }

    #handleInput(event: Event): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Login UI missing');
        }
        const target = event.target;
        if (!(target instanceof HTMLInputElement)) {
            return;
        }
        if (target !== ui.username && target !== ui.password) {
            return;
        }
        if (isLoginCooldownActive(this.#session)) {
            return;
        }
        updateLoginStatusMessage(this.#session, ui);
    }

    #handleSubmit(event: Event): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Login UI missing');
        }
        terminateHandledPromise(submitLoginForm(this.#session, ui, event));
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        clearLoginCooldown(this.#session);
        this.#ui = null;
    }
}

export { LoginPage };
