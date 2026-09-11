/* SoAI - Models routed page [frontend/assets/ts/pages/models/ModelsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { prepareCollectionReveal, releasePreparedCollection } from '@core/collectionpage/revealLifecycle.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { METRICS, MODELS, MODELS_LAST_USED } from '@core/realtime/streammanager/resources/ids.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { bindPluginLogoFallbacks } from '@features/catalog/public.ts';
import { PAGE_ID, PAGE_MODULE_ID } from '@pages/models/contracts/modelsPageConstants.ts';
import { isModelsDataActionId } from '@pages/models/actions.ts';
import { bindModelsModalLifecycleEvents } from '@pages/models/controllers/page/modelsModalLifecycleController.ts';
import { requireModelsRoot } from '@pages/models/dom.ts';
import { ModelsPageDomain } from '@pages/models/controllers/page/ModelsPageDomain.ts';
import type { ModelsPageDependencies } from '@pages/models/types.ts';

class ModelsPage extends StaticBasePage {
    readonly #domain: ModelsPageDomain;

    constructor(dependencies: ModelsPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#domain = new ModelsPageDomain({
            pageDependencies: dependencies,
            infrastructure: {
                pageId: this.pageId,
                sanitizer: this.pageContext.sanitizer,
                auth: this.dependencies.auth,
                dom: this.dependencies.dom,
                stateManager: this.dependencies.stateManager,
                api: this.dependencies.api,
                router: this.dependencies.router,
                storage: this.dependencies.storage,
                layout: this.layout,
                streaming: this.streaming,
                services: this.services,
                pageElements: this.pageElements,
                pageLifecycle: this.pageLifecycle,
                pageDom: this.pageDom,
                pageResources: this.pageResources,
                feedback: this.feedback
            },
            storage: this.dependencies.storage,
            pageHost: this.pageHost,
            pageLifecycle: this.pageLifecycle,
            collectionOwners: { layout: this.layout, streaming: this.streaming }
        });
        this.layout.configure({ getActionsMenuBreakpoint: () => 1200 });
    }

    override getRequiredResources(): string[] {
        return [MODELS, METRICS, MODELS_LAST_USED];
    }

    override async renderView(): Promise<TrustedHtml> {
        return await this.#domain.lifecycle.render();
    }

    override async setupPage(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#domain.setupMetrics();
        this.#domain.setupLastUsed();
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#domain.initializeView();
        await super.setupPage(parameters, context);
    }

    override async initializeShell(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.state.initializeShell(this.#domain.lifecycle, parameters, async () => this.#domain.pageLifecycleController.initializeShell(), context);
    }

    bindPageEvents(): void {
        this.#domain.layout.setupEventListeners();
        if (!this.#domain.session.cardController) throw new Error('ModelsPage.setupEventListeners requires cardController to be initialized');
        const signal = this.pageLifecycle.beginListeners();
        const root = requireModelsRoot({ pageDom: this.pageDom });
        bindPluginLogoFallbacks(root, signal);
        bindPageActionDispatcher({
            label: 'ModelsPage',
            root,
            signal,
            isAction: isModelsDataActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    ignorePrevented: true,
                    onAction: ({ event, action, actionElement }) => {
                        if (event instanceof MouseEvent) this.#domain.bindings.rootClickHandler(event, action, actionElement);
                    }
                }
            }
        });
        const managers = this.#domain.bindings.managerBundle;
        bindModelsModalLifecycleEvents({ services: this.services }, signal, { downloadModalManager: managers.downloadModalManager, editModelModalManager: managers.editModelModalManager, renameModelModalManager: managers.renameModelModalManager, providersManager: managers.providersManager, virtualModelsManager: managers.virtualModelsManager });
    }

    override async loadData(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#domain.pageLifecycleController.loadData(parameters, context, async (loadParameters, loadContext) => {
            this.#domain.initializeView();
            await super.loadData(loadParameters, loadContext);
        });
    }

    override async onRefresh(parameters: JsonObject | null): Promise<void> {
        await super.onRefresh(parameters);
        await this.#domain.pageLifecycleController.refresh(parameters);
    }

    override async prepareInitialContent(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        if (signalAborted(context.signal ?? null) || this.isDestroyed) return;
        await this.#domain.pageLifecycleController.show();
        await super.prepareInitialContent(parameters, context);
        if (!signalAborted(context.signal ?? null) && !this.isDestroyed && this.#domain.collections.runtime) this.#domain.renderItems();
    }

    override async startLiveUpdates(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#domain.lifecycle.startLiveUpdates({ signal: context.signal });
        await super.startLiveUpdates(parameters, context);
    }

    override async commitInitialContent(context: { signal?: AbortSignal } = {}): Promise<void> {
        await prepareCollectionReveal({ pageId: this.pageId, collections: this.#domain.collections, layout: this.#domain.layout, isDestroyed: () => this.isDestroyed }, this.pageHost.getSection(), context.signal ?? null);
        await super.commitInitialContent(context);
    }

    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        releasePreparedCollection(this.pageHost.getSection(), context.signal ?? null);
    }

    override async onHide(): Promise<void> {
        this.#domain.pageLifecycleController.hide();
        await super.onHide();
    }

    protected override beforePageRefreshCleanup(): void {
        this.pageLifecycle.abortListeners('refresh');
    }

    protected override refreshDomainState(): void {
        if (this.#domain.collections.runtime?.size() === 0) this.#domain.collections.runtime.refresh();
    }

    protected override cleanupDomainState(): void {
        this.#domain.collections.cleanupState();
    }

    protected override onCollectionStateCleaned(): void {
        this.#domain.state.reset();
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners('models-destroy');
        await this.#domain.destroy();
    }
}

export { ModelsPage, PAGE_ID, PAGE_MODULE_ID };
