/* SoAI - Plugins routed page [frontend/assets/ts/pages/plugins/PluginsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { prepareCollectionReveal, releasePreparedCollection } from '@core/collectionpage/revealLifecycle.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { PLUGINS, PLUGINS_LAST_USED } from '@core/realtime/streammanager/resources/ids.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { PAGE_ID } from '@features/plugins/public.ts';
import { bindPluginLogoFallbacks } from '@features/catalog/public.ts';
import { isPluginsActionId } from '@pages/plugins/actions.ts';
import { loadPluginsPageData } from '@pages/plugins/controllers/page/effects.ts';
import { cleanupPluginsPageOnDestroy } from '@pages/plugins/controllers/page/events.ts';
import { PluginsPageDomain } from '@pages/plugins/controllers/page/PluginsPageDomain.ts';
import { bindPluginsPageModalEventListeners } from '@pages/plugins/controllers/page/pluginsPageEventListenersController.ts';
import { requirePluginsUi } from '@pages/plugins/dom.ts';
import type { PluginsPageDependencies } from '@pages/plugins/types.ts';

class PluginsPage extends StaticBasePage {
    readonly #domain: PluginsPageDomain;

    constructor(dependencies: PluginsPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        if (!dependencies) throw new Error('PluginsPage requires dependencies');
        this.#domain = new PluginsPageDomain({
            pageDependencies: dependencies,
            infrastructure: {
                api: this.dependencies.api,
                auth: this.dependencies.auth,
                router: this.dependencies.router,
                dom: this.dependencies.dom,
                stateManager: this.dependencies.stateManager,
                sanitizer: this.pageContext.sanitizer,
                pageDom: this.pageDom,
                feedback: this.feedback,
                pageResources: this.pageResources,
                services: this.services,
                pageElements: this.pageElements,
                layout: this.layout,
                streaming: this.streaming
            },
            storage: this.dependencies.storage,
            pageHost: this.pageHost,
            pageLifecycle: this.pageLifecycle,
            collectionOwners: { layout: this.layout, streaming: this.streaming }
        });
    }

    override getRequiredResources(): string[] {
        return [PLUGINS, PLUGINS_LAST_USED];
    }

    override async renderView(): Promise<TrustedHtml> {
        return await this.#domain.lifecycle.render();
    }

    override async setupPage(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#domain.initializeView();
        this.#domain.runtime.progressController.initializeOperationProgress();
        this.#domain.setupLastUsed();
        await super.setupPage(parameters, context);
    }

    override async initializeShell(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.state.initializeShell(
            this.#domain.lifecycle,
            parameters,
            async () => {
                await this.#domain.runtime.lifecycleController.onCollectionShellReady();
            },
            context
        );
    }

    bindPageEvents(): void {
        this.#domain.layout.setupEventListeners();
        if (!this.#domain.session.cardController) throw new Error('PluginsPage.setupEventListeners requires cardController to be initialized');
        const signal = this.pageLifecycle.beginListeners();
        const ui = requirePluginsUi({ getDomContext: () => this.pageHost.getContext() });
        bindPluginLogoFallbacks(ui.root, signal);
        const runtime = this.#domain.runtime;
        bindPageActionDispatcher({
            root: ui.root,
            signal,
            label: 'PluginsPage',
            isAction: isPluginsActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }) => {
                        if (event instanceof MouseEvent) runtime.rootEventController.handleRootClick(event, action, actionElement);
                    }
                },
                change: { preventDefault: 'never', onAction: ({ event, action, actionElement }) => runtime.rootEventController.handleRootChange(event, action, actionElement) }
            }
        });
        runtime.presentationController.initializeViewMode(ui);
        bindPluginsPageModalEventListeners({
            signal,
            interactionController: runtime.interactionController,
            modalCloseDependencies: {
                downloadModalManager: runtime.modalManagers.downloadModalManager,
                configManager: runtime.modalManagers.configManager,
                manageBackendModalManager: runtime.modalManagers.manageBackendModalManager,
                infoManager: runtime.modalManagers.infoManager,
                cloneManager: runtime.modalManagers.cloneManager,
                concurrentManager: runtime.modalManagers.concurrentManager
            }
        });
    }

    override async loadData(parameters?: JsonObject, context?: { signal?: AbortSignal }): Promise<void> {
        this.#domain.initializeView();
        await super.loadData(parameters, context);
        const domain = this.#domain;
        await loadPluginsPageData({
            cardController: domain.session.cardController,
            runWithBoundary: (scope, task) => this.pageLifecycle.run(scope, task),
            withCollectionLoading: async (task, options) => {
                await domain.lifecycle.withLoading(async () => {
                    await task();
                    return true;
                }, options);
            },
            ensureCollectionStream: async () => {
                await domain.collections.ensureStream({ allowDiscovery: true });
            },
            getLoadingText: () => i18n.t('plugins.loading.plugins'),
            ensureDataSubscriptions: () => this.streaming.ensureSubscriptions(),
            loadInitialData: () => domain.runtime.lifecycleController.loadInitialData(),
            updateStats: () => domain.runtime.coreControllers.statsController.updateStats(),
            beginRecentItemsSync: () => domain.session.recentItems.beginSync(),
            armRecentItems: (sequence) => domain.session.recentItems.armSync(sequence)
        });
    }

    override async beforePageInitialize(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#domain.runtime.lifecycleController.beforePageInitialize(parameters);
    }

    override async onRefresh(parameters: JsonObject | null): Promise<void> {
        const sequence = this.#domain.session.recentItems.beginSync();
        await super.onRefresh(parameters);
        await this.#domain.runtime.lifecycleController.onRefresh();
        this.#domain.session.recentItems.armSync(sequence);
    }

    override async prepareInitialContent(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        const sequence = this.#domain.session.recentItems.beginSync();
        if (signalAborted(context.signal ?? null) || this.isDestroyed) return;
        await this.#domain.runtime.lifecycleController.prepareInitialContent({ signal: context.signal });
        if (signalAborted(context.signal ?? null) || this.isDestroyed) return;
        this.#domain.session.recentItems.armSync(sequence);
        await super.prepareInitialContent(parameters, context);
        if (this.#domain.collections.runtime) this.#domain.runtime.presentationController.renderItems();
    }

    override async startLiveUpdates(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#domain.lifecycle.startLiveUpdates({ signal: context.signal });
        await super.startLiveUpdates(parameters, context);
        await this.#domain.runtime.lifecycleController.startLiveUpdates();
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
        this.#domain.session.recentItems.clear();
        this.#domain.runtime.presentationController.renderItems();
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
        this.#domain.session.recentItems.clear();
        this.pageLifecycle.abortListeners('plugins-destroy');
        await cleanupPluginsPageOnDestroy({ session: this.#domain.session, runtime: this.#domain.runtime });
        this.#domain.dispose();
    }
}

export { PluginsPage };
