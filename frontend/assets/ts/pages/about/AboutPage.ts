/* SoAI - About routed page [frontend/assets/ts/pages/about/AboutPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { showCreditsModal, showLicenseModal } from '@core/licenseservice/service.ts';
import { capitalize } from '@core/primitives/text.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { applyLogoBranding } from '@core/ui/branding/pageBranding.ts';
import { ABOUT_ACTION_SHOW_CREDITS, ABOUT_ACTION_SHOW_LICENSE, isAboutActionId } from '@pages/about/actions.ts';
import { EasterEggController } from '@pages/about/controllers/EasterEggController.ts';
import { optionalAboutLogoSection, requireAboutUi } from '@pages/about/dom.ts';
import type { AboutHardwareCapabilities, AboutSystemInfo, AboutUiRefs } from '@pages/about/types.ts';
import { renderAboutPageView } from '@pages/about/view.ts';

export const PAGE_ID = 'about';
export const PAGE_MODULE_ID = 'pages.AboutPage';

class AboutPage extends StaticBasePage {
    readonly #resources = new ResourceTracker();
    #systemInfo: AboutSystemInfo | null = null;
    #hardwareCapabilities: AboutHardwareCapabilities | null = null;
    #ui: AboutUiRefs | null = null;
    #easterEggController: EasterEggController | null = null;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
    }

    override getRequiredResources(): string[] {
        return [];
    }

    override async beforeRender(parameters: JsonObject): Promise<JsonObject> {
        await super.beforeRender(parameters);
        return {};
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        return toTrustedHtml(renderAboutPageView());
    }

    override async loadData(_parameters?: JsonObject | null, context: { signal?: AbortSignal } | null = null): Promise<void> {
        const api = this.dependencies.api;
        if (!api?.system?.info || !api.hardware?.capabilities) {
            this.#systemInfo = null;
            this.#hardwareCapabilities = null;
            errorHandler.warn('AboutPage', 'Optional About diagnostics API is unavailable', new Error('About diagnostics API unavailable'));
            return;
        }
        const signal = context?.signal;
        const requestOptions = signal ? { signal } : {};
        const [systemInfo, hardwareCapabilities] = await Promise.allSettled([(async () => await api.system.info(requestOptions))(), (async () => await api.hardware.capabilities(requestOptions))()]);
        throwIfAborted(signal);
        if (systemInfo.status === 'fulfilled') {
            this.#systemInfo = systemInfo.value.soaiVersion === null ? {} : { version: systemInfo.value.soaiVersion };
        } else {
            this.#systemInfo = null;
            errorHandler.warn('AboutPage', 'System information is unavailable', ensureError(systemInfo.reason));
        }
        if (hardwareCapabilities.status === 'fulfilled') {
            this.#hardwareCapabilities = hardwareCapabilities.value.platform === undefined ? {} : { platform: hardwareCapabilities.value.platform };
        } else {
            this.#hardwareCapabilities = null;
            errorHandler.warn('AboutPage', 'Hardware capabilities are unavailable', ensureError(hardwareCapabilities.reason));
        }
    }

    override async setupPage(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#ui = requireAboutUi({
            requireHTMLElement: (selector, context) => this.pageDom.requireHTMLElement(selector, context),
            optionalHTMLElement: (selector, context) => this.pageDom.optionalHTMLElement(selector, context)
        });
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#applyBranding();
    }

    override async prepareInitialContent(parameters: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.prepareInitialContent(parameters, context);
        this.#updateVersion();
        this.#updatePlatform();
    }

    bindPageEvents(): void {
        const ui = this.#requireUi();
        this.#initializeEasterEgg();
        const signal = this.pageLifecycle.beginListeners();
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'AboutPage',
            isAction: isAboutActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'always',
                    onAction: ({ action }): void => {
                        if (action === ABOUT_ACTION_SHOW_LICENSE) {
                            void this.#handleLicenseClick().catch((error) => {
                                errorHandler.warn('AboutPage', 'Failed to open license modal', error);
                            });
                            return;
                        }
                        if (action === ABOUT_ACTION_SHOW_CREDITS) {
                            void this.#handleCreditsClick().catch((error) => {
                                errorHandler.warn('AboutPage', 'Failed to open credits modal', error);
                            });
                        }
                    }
                }
            }
        });
    }

    override async onHide(): Promise<void> {
        this.#cleanupInteractiveRuntime();
        await super.onHide();
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#cleanupInteractiveRuntime();
        this.#resources.cleanup();
    }

    #cleanupInteractiveRuntime(): void {
        this.#easterEggController?.cleanup();
        this.#easterEggController = null;
    }

    #applyBranding(): void {
        const ui = this.#requireUi();
        applyLogoBranding(this.pageDom, ui.logo);
    }

    #updateVersion(): void {
        const ui = this.#requireUi();
        const value = this.#systemInfo?.version ?? null;
        this.pageDom.updateText(ui.version, value || i18n.t('common.notAvailable'));
    }

    #updatePlatform(): void {
        const ui = this.#requireUi();
        const platform = this.#hardwareCapabilities?.platform ?? '';
        const normalized = platform ? capitalize(platform) : i18n.t('common.notAvailable');
        this.pageDom.updateText(ui.platform, normalized);
    }

    #initializeEasterEgg(): void {
        const domHost = {
            requireHTMLElement: (selector: string, context?: Element) => this.pageDom.requireHTMLElement(selector, context),
            optionalHTMLElement: (selector: string, context?: Element) => this.pageDom.optionalHTMLElement(selector, context)
        };
        const logoSection = optionalAboutLogoSection(domHost);
        if (!logoSection) return;
        this.#easterEggController = new EasterEggController();
        this.#easterEggController.attach(logoSection, () => this.#systemInfo?.version ?? null);
    }

    #requireUi(): AboutUiRefs {
        const ui = this.#ui;
        if (!ui) {
            throw new Error('About page UI missing');
        }
        return ui;
    }

    async #handleLicenseClick(): Promise<void> {
        await showLicenseModal();
    }

    async #handleCreditsClick(): Promise<void> {
        await showCreditsModal();
    }
}

export { AboutPage };
