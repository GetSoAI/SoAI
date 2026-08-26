/* SoAI - Updates routed page [frontend/assets/ts/pages/updates/UpdatesPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { narrowButton } from '@core/dom/narrowElement.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage, type RenderContext } from '@core/StaticBasePage.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { isUpdatesActionId } from '@pages/updates/actions.ts';
import type { UpdatesPageDependencies } from '@pages/updates/contracts/contracts.ts';
import { handleUpdatesPageClick } from '@pages/updates/controllers/events.ts';
import { UpdatesPageWorkflowController } from '@pages/updates/controllers/UpdatesPageWorkflowController.ts';
import { initializeUpdatesPageShell } from '@pages/updates/controllers/updatesPageShellController.ts';
import { requireUpdatesUi } from '@pages/updates/dom.ts';
import { renderUpdatesPageView } from '@pages/updates/view.ts';
import type { UpdatesEditionContribution, UpdatesProductController } from '@core/edition/updatesContribution.ts';

export const PAGE_ID = 'updates';

class UpdatesPage extends StaticBasePage {
    #workflowController: UpdatesPageWorkflowController;
    #productController: UpdatesProductController | null = null;
    readonly #product: UpdatesEditionContribution | null;

    constructor(dependencies: UpdatesPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        if (!dependencies || !isFunction(dependencies.restartOverlay?.show)) {
            throw new Error('UpdatesPage requires a restart overlay service dependency');
        }
        this.#workflowController = new UpdatesPageWorkflowController({
            restartOverlay: dependencies.restartOverlay,
            api: this.dependencies.api,
            pageResources: this.pageResources,
            feedback: this.feedback,
            pageElements: this.pageElements,
            pageDom: this.pageDom,
            pageContext: this.pageContext,
            services: this.services,
            stateManager: this.dependencies.stateManager,
            streaming: this.streaming,
            storage: this.dependencies.storage
        });
        this.#product = dependencies.product;
    }

    override async renderView(_context: RenderContext): Promise<TrustedHtml> {
        const product = this.#product;
        return renderUpdatesPageView({
            generateStandardHeader: (options) => this.layout.generateHeader(options),
            getIconSync: (iconName, options) => this.services.getIconSync(iconName, options),
            productMarkup:
                product?.render({
                    getIconSync: (iconName, options) => this.services.getIconSync(iconName, options)
                }) ?? null,
            productStats: product?.stats ?? []
        });
    }

    override getRequiredResources(): string[] {
        return [];
    }
    override async initializeShell(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }

        const root = this.resolveHostContainer();
        const ui = requireUpdatesUi(this.pageDom);
        this.#workflowController.setUi(ui);
        const systemController = initializeUpdatesPageShell({
            ui,
            checkButton: narrowButton(this.pageDom.requireHTMLElement('#checkUpdatesBtn', root), '#checkUpdatesBtn'),
            createSystemHost: () => this.#workflowController.createSystemHost(),
            createNoticeHost: () => ({
                updateText: (element, text) => this.pageDom.updateText(element, text),
                toggleHidden: (element, hidden) => this.pageElements.toggleHidden(element, hidden)
            })
        });
        const product = this.#product;
        const productController = product === null ? null : product.createController(this.#workflowController.createProductRuntimeDependencies());
        if (productController !== null) {
            await productController.initialize();
        }
        if (signalAborted(context.signal ?? null)) {
            productController?.destroy();
            systemController.destroy();
            return;
        }
        this.#productController = productController;
        this.#workflowController.setControllers(systemController, productController);
        this.layout.setupResponsive();
    }

    bindPageEvents(): void {
        bindPageActionDispatcher({
            root: this.resolveHostContainer(),
            signal: this.pageLifecycle.beginListeners(),
            label: 'UpdatesPage',
            isAction: (value): value is string => isUpdatesActionId(value) || (this.#product?.isAction(value) ?? false),
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    ignoreFormControls: true,
                    onAction: ({ event, action, actionElement }): void => {
                        if (isUpdatesActionId(action)) {
                            handleUpdatesPageClick({
                                event,
                                actionElement,
                                handlers: this.#workflowController.createActionHandlers()
                            });
                            return;
                        }
                        event.preventDefault();
                        void this.#productController?.handleAction(action, actionElement);
                    }
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ action, actionElement }): void => {
                        void this.#productController?.handleAction(action, actionElement);
                    }
                }
            }
        });
    }

    onPageCleanup(): void {
        this.#cleanupPageState();
    }

    override async onDestroy(): Promise<void> {
        this.#cleanupPageState();
    }

    #cleanupPageState(): void {
        this.pageLifecycle.abortListeners('updates-cleanup');
        this.#productController = null;
        this.#workflowController.cleanup();
    }
}

export { UpdatesPage };
