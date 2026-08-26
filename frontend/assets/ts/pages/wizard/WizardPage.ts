/* SoAI - Wizard routed page [frontend/assets/ts/pages/wizard/WizardPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import type { LicenseServiceInterface } from '@core/licenseservice/types.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { AUTH_ROUTE_WIZARD } from '@core/routing/router/authRouteTarget.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { WizardState } from '@features/wizard/public.ts';
import { WizardPageDomain } from '@pages/wizard/controllers/page/WizardPageDomain.ts';

export const PAGE_ID = AUTH_ROUTE_WIZARD;
export const PAGE_MODULE_ID = 'pages.WizardPage';

interface WizardPageDependencies {
    licenseService: LicenseServiceInterface;
}

class WizardPage extends StaticBasePage {
    readonly state: WizardState;
    readonly #domain: WizardPageDomain;

    constructor({ licenseService }: WizardPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        if (!licenseService || !isFunction(licenseService.fetchLicenseData)) throw new TypeError('WizardPage requires a license service with fetchLicenseData()');
        this.#domain = new WizardPageDomain({
            auth: this.dependencies.auth,
            feedback: this.feedback,
            languageService: this.dependencies.languageService,
            licenseService,
            pageContext: this.pageContext,
            pageDom: this.pageDom,
            pageElements: this.pageElements,
            pageHost: this.pageHost,
            pageLifecycle: this.pageLifecycle,
            router: this.dependencies.router,
            services: this.services,
            storage: this.dependencies.storage
        });
        this.state = this.#domain.state;
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforePageInitialize(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(_parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.loadStatus();
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        await this.#domain.resolveVisibility();
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return toTrustedHtml(this.#domain.render());
    }

    override async initializeShell(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.initialize();
    }

    bindPageEvents(): void {
        this.#domain.bindPageEvents();
    }

    override async onDestroy(): Promise<void> {
        this.#domain.destroy();
    }
}

export { WizardPage };
