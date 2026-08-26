/* SoAI - Forbidden routed page [frontend/assets/ts/pages/forbidden/ForbiddenPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { getWindow } from '@core/environment/public.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { i18n } from '@core/i18n/index.ts';
import { DEFAULT_AUTHENTICATED_ROUTE } from '@core/routing/router/authRouteTarget.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isObject, isString } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isForbiddenActionId, FORBIDDEN_ACTION_GO_BACK, FORBIDDEN_ACTION_GO_DEFAULT_ROUTE } from '@pages/forbidden/actions.ts';
import { requireForbiddenUi } from '@pages/forbidden/dom.ts';
import { renderForbiddenPageView } from '@pages/forbidden/view.ts';

export const PAGE_ID = 'forbidden';
export const PAGE_MODULE_ID = 'pages.ForbiddenPage';

const resolveRequestedComponent = (parameters: JsonObject): string | null => {
    const candidate = parameters['page'];
    if (!isString(candidate)) {
        return null;
    }
    const value = candidate.trim();
    return value ? value : null;
};

class ForbiddenPage extends StaticBasePage {
    #requestedPageTitle: string | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        const requestedComponent = resolveRequestedComponent(parameters);
        this.#requestedPageTitle = this.#resolveRequestedPageTitle(requestedComponent);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return renderForbiddenPageView({
            generateStandardHeader: (options) => this.layout.generateHeader(options),
            getIconSync: (name, options) => this.services.getIconSync(name, options),
            requestedPageTitle: this.#requestedPageTitle
        });
    }

    bindPageEvents(): void {
        const ui = requireForbiddenUi({
            requireHTMLElement: (selector, context) => this.pageDom.requireHTMLElement(selector, context)
        });
        const signal = this.pageLifecycle.beginListeners();
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'ForbiddenPage',
            isAction: isForbiddenActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action }): void => {
                        if (action === FORBIDDEN_ACTION_GO_BACK) {
                            getWindow().history.back();
                            return;
                        }
                        if (action === FORBIDDEN_ACTION_GO_DEFAULT_ROUTE) {
                            this.dependencies.router.navigate(DEFAULT_AUTHENTICATED_ROUTE);
                        }
                    }
                }
            }
        });
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#requestedPageTitle = null;
    }

    #resolveRequestedPageTitle(component: string | null): string | null {
        if (!component) {
            return null;
        }
        try {
            const registryCandidate = this.dependencies.router.parseRoute(component);
            if (registryCandidate && isObject(registryCandidate.route) && typeof registryCandidate.route.getTitle === 'function') {
                const title = registryCandidate.route.getTitle();
                return isString(title) && title.trim() ? title : null;
            }
        } catch (error) {
            errorHandler.warn('ForbiddenPage', 'Failed to resolve requested page title', ensureError(error));
            return null;
        }

        if (component === 'terminal') {
            return i18n.t('pages.terminal.title');
        }
        if (component === 'power') {
            return i18n.t('pages.power.title');
        }
        if (component === 'settings') {
            return i18n.t('pages.settings.title');
        }
        return null;
    }
}

export { ForbiddenPage };
