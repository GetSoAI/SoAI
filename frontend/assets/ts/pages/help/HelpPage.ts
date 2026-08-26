/* SoAI - Help routed page [frontend/assets/ts/pages/help/HelpPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { optionalTrimmedString } from '@core/types/payloadValueReaders.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { applyLogoBranding } from '@core/ui/branding/pageBranding.ts';
import { HELP_ACTION_NAVIGATE_ABOUT, isHelpActionId } from '@pages/help/actions.ts';
import { requireHelpUi } from '@pages/help/dom.ts';
import type { HelpUiRefs } from '@pages/help/types.ts';
import { renderHelpPageView } from '@pages/help/view.ts';

export const PAGE_ID = 'help';
export const PAGE_MODULE_ID = 'pages.HelpPage';

class HelpPage extends StaticBasePage {
    #ui: HelpUiRefs | null = null;
    #targetSectionId: string | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        this.#targetSectionId = optionalTrimmedString(parameters['section']);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return renderHelpPageView({
            generateStandardHeader: (options) => this.layout.generateHeader(options),
            getIconSync: (iconName, options) => this.services.getIconSync(iconName, options)
        });
    }

    override async setupPage(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#ui = requireHelpUi({
            requireHTMLElement: (selector, context) => this.pageDom.requireHTMLElement(selector, context)
        });
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#applyBranding();
        this.#scrollToRequestedSection();
    }

    bindPageEvents(): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Help page UI missing');
        }
        const signal = this.pageLifecycle.beginListeners();
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'HelpPage',
            isAction: isHelpActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action }): void => {
                        if (action === HELP_ACTION_NAVIGATE_ABOUT) {
                            const router = this.dependencies.router;
                            if (!router) {
                                throw new Error('Help page router missing');
                            }
                            router.navigate('about');
                        }
                    }
                }
            }
        });
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
    }

    #applyBranding(): void {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('Help page UI missing');
        }
        applyLogoBranding(this.pageDom, ui.logo);
    }

    #scrollToRequestedSection(): void {
        const sectionId = this.#targetSectionId;
        if (!sectionId) {
            return;
        }
        const timerId = this.pageResources.setTimer(() => {
            const section = this.pageDom.optionalHTMLElement(`#help-section-${sectionId}`);
            if (section) {
                scrollElementIntoView(section, { block: 'start' });
                return;
            }
            throw new Error(`Help section not found for "${sectionId}"`);
        }, 0);
        if (timerId === null) {
            throw new Error('Help section scroll timer allocation failed');
        }
    }
}

export { HelpPage };
