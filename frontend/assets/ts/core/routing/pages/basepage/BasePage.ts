/* SoAI - Frontend base page ownership [frontend/assets/ts/core/routing/pages/basepage/BasePage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { BasePageConstructorOptions, BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { isJsonObject, type JsonObject, type JsonValue } from '@core/types/jsonValues.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { PageContext } from '@core/pagecontext/public.ts';
import { normalizePageIdentifier } from '@core/pageIdentity.ts';
import { commitPageInitialVisualState } from '@core/runtime/pageVisualCommit.ts';
import { isString } from '@core/typeGuards.ts';
import { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageCollapsibleCards } from '@core/routing/pages/basepagelayout/PageCollapsibleCards.ts';
import { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import { composePageFoundation } from '@core/routing/pages/basepage/composePageFoundation.ts';
import { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { PageRuntimePhaseContext } from '@core/runtime/pageRuntimeContracts.ts';

abstract class BasePage {
    readonly pageLifecycle: PageLifecycle;
    readonly layout: PageLayout;
    readonly streaming: PageStreaming;
    readonly services: PageServices;
    readonly pageElements: PageUi;
    readonly pageDom: PageDom;
    readonly pageResources: PageResources;
    readonly collapsibleCards: PageCollapsibleCards;
    readonly feedback: PageFeedback;
    readonly pageHost: PageHost;
    protected readonly dependencies: BasePageDependencies;
    readonly #pageId: string;
    readonly pageContext: PageContext;

    constructor(pageId: string, { dependencies, pageContext = null }: BasePageConstructorOptions) {
        const constructorName = isString(new.target?.name) && new.target.name ? new.target.name : 'page';
        const name = normalizePageIdentifier(pageId, constructorName);
        this.#pageId = name;
        this.pageHost = new PageHost(name);
        this.pageContext = pageContext ?? new PageContext({ pageId: name });
        this.dependencies = dependencies;
        this.feedback = new PageFeedback(name, this.pageContext);
        this.pageResources = new PageResources();
        this.pageDom = new PageDom({ getContext: () => this.pageHost.getContext() });
        const foundation = composePageFoundation({
            pageId: name,
            auth: dependencies.auth,
            languageService: dependencies.languageService,
            loading: dependencies.loadingState,
            pageContext: this.pageContext,
            pageDom: this.pageDom,
            pageHost: this.pageHost,
            resources: this.pageResources,
            router: dependencies.router,
            storage: dependencies.storage
        });
        this.services = foundation.services;
        this.layout = foundation.layout;
        this.pageElements = foundation.pageElements;
        this.collapsibleCards = foundation.collapsibleCards;
        this.streaming = foundation.streaming;
        this.pageLifecycle = foundation.pageLifecycle;
    }

    protected beforePageRefreshCleanup(): void {}

    protected refreshDomainState(): void {}

    protected cleanupDomainState(): void {}

    get pageId(): string {
        return this.#pageId;
    }

    get isInitialized(): boolean {
        return this.pageLifecycle.isInitialized;
    }

    get isDestroyed(): boolean {
        return this.pageLifecycle.isDestroyed;
    }

    get container(): HTMLElement | null {
        return this.pageHost.container;
    }

    set container(container: HTMLElement | null) {
        if (container === null) {
            this.pageHost.clearContainer();
            return;
        }
        this.pageHost.setContainer(container);
    }

    setContainer(container: HTMLElement): this {
        this.pageHost.setContainer(container);
        return this;
    }

    resolveHostContainer(): HTMLElement {
        return this.pageHost.resolveContainer();
    }

    protected getPageSection(): HTMLElement | null {
        return this.pageHost.getSection();
    }

    getDomContext(): Element | null {
        return this.pageHost.getContext();
    }

    async ensureDataSubscriptions(options: { signal?: AbortSignal } = {}): Promise<void> {
        await this.streaming.ensureSubscriptions(options);
    }

    async initialize(point?: JsonObject): Promise<void> {
        await this.services.awaitDetachedContext();
        await this.pageLifecycle.initialize(point, {
            render: (parameters) => this.render(parameters ?? undefined),
            refresh: (parameters, context) => this.onRefresh(parameters, context),
            initializeDomain: (parameters, context) => this.#initializeDomain(parameters, context),
            readiness: {
                prepare: (parameters, context) => this.#prepareRuntime(parameters, context),
                afterReveal: (context) => this.afterPageReveal(context)
            }
        });
    }

    async #initializeDomain(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.onInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.afterInitialization(parameters, context);
    }

    async #prepareRuntime(parameters: JsonObject, context: PageRuntimePhaseContext): Promise<void> {
        const { signal, setStage } = context;
        await this.ensureDataSubscriptions({ signal });
        setStage('ensureDataSubscriptions');
        if (signalAborted(signal)) return;
        await this.loadData(parameters, { signal });
        setStage('loadData');
        if (signalAborted(signal)) return;
        await this.prepareInitialContent(parameters, { signal });
        setStage('prepareInitialContent');
        if (signalAborted(signal)) return;
        await this.bindPageEvents({ signal });
        setStage('bindPageEvents');
        if (signalAborted(signal)) return;
        await this.startLiveUpdates(parameters, { signal, setStage: (stage) => setStage(`startLiveUpdates:${stage}`) });
        setStage('startLiveUpdates');
        if (signalAborted(signal)) return;
        await this.commitInitialContent({ signal });
        setStage('commitInitialContent');
    }

    abstract render(parameters?: JsonObject): Promise<TrustedHtml>;

    async loadData(_parameters?: JsonObject | null, _context?: { signal?: AbortSignal } | null): Promise<void> {}

    async beforePageInitialize(_parameters?: JsonObject | null, _context: { signal?: AbortSignal } = {}): Promise<void> {}

    async setupPage(_parameters?: JsonObject | null, _context: { signal?: AbortSignal } = {}): Promise<void> {}

    async initializeShell(_parameters?: JsonObject | null, _context: { signal?: AbortSignal } = {}): Promise<void> {}

    async prepareInitialContent(_parameters?: JsonObject | null, _context?: { signal?: AbortSignal } | null): Promise<void> {}

    async commitInitialContent({ signal }: { signal?: AbortSignal } = {}): Promise<void> {
        await commitPageInitialVisualState({ pageId: this.pageId, section: this.getPageSection(), flushDOMUpdates: () => this.pageDom.flush() }, signal ?? null);
    }

    async afterPageReveal(_context: { signal?: AbortSignal } = {}): Promise<void> {}

    protected async afterInitialization(_parameters: JsonObject | null, _context: { signal?: AbortSignal } = {}): Promise<void> {}

    abstract bindPageEvents(_context?: { signal?: AbortSignal }): Promise<void> | void;

    async onInitialize(point?: JsonValue | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        return this.pageLifecycle.run('onInit', async () => {
            if (signalAborted(context.signal ?? null)) {
                return;
            }
            const parameters = isJsonObject(point) ? point : null;
            await this.beforePageInitialize(parameters, context);
            if (signalAborted(context.signal ?? null)) {
                return;
            }
            await this.dependencies.storage.ready;
            if (signalAborted(context.signal ?? null)) {
                return;
            }
            this.pageLifecycle.setup();
            await this.setupPage(parameters, context);
            if (signalAborted(context.signal ?? null)) {
                return;
            }
            await this.initializeShell(parameters, context);
            if (signalAborted(context.signal ?? null)) {
                return;
            }
            this.pageDom.flush();
        });
    }

    async onRefresh(point?: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        return this.pageLifecycle.run('onRefresh', async () => {
            await this.pageLifecycle.refresh(
                point ?? null,
                {
                    beforeCleanup: () => this.beforePageRefreshCleanup(),
                    getRequiredResources: () => this.getRequiredResources(),
                    refreshDomainState: () => this.refreshDomainState(),
                    onInitialize: (parameters, initializeContext) => this.onInitialize(parameters, initializeContext)
                },
                context
            );
        });
    }

    abstract getRequiredResources(): string[];

    async startLiveUpdates(_parameters?: JsonObject | null, context: { signal?: AbortSignal; setStage?(stage: string): void } = {}): Promise<void> {
        return this.pageLifecycle.run('startLiveUpdates', async () => {
            context.setStage?.('subscriptions');
            await this.streaming.verifySubscriptions();
        });
    }

    async hide(): Promise<void> {
        await this.pageLifecycle.hide(
            () => this.onCancel('hide'),
            async () => this.onHide()
        );
    }

    async onHide(): Promise<void> {
        await this.layout.hide();
    }

    cancel(reason: string): void {
        this.pageLifecycle.cancel(reason);
        this.onCancel(reason);
    }

    protected onCancel(_reason: string): void {}

    async destroy(..._arguments: (JsonObject | null)[]): Promise<boolean> {
        this.cancel('destroy');
        return this.pageLifecycle.run('destroy', async () => {
            return this.pageLifecycle.destroy({
                onDestroy: () => this.onDestroy(),
                cleanupDomainState: () => this.cleanupDomainState(),
                onCollectionStateCleaned: () => this.onCollectionStateCleaned()
            });
        });
    }

    abstract onDestroy(): Promise<void>;

    protected onCollectionStateCleaned(): void {}

    async cleanup(): Promise<boolean> {
        return this.pageLifecycle.cleanup(
            () => this.cleanupDomainState(),
            () => this.onCollectionStateCleaned()
        );
    }
}

export { BasePage };
