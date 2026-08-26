/* SoAI - Prompts routed page [frontend/assets/ts/pages/prompts/PromptsPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { PROMPTS } from '@core/realtime/streammanager/resources/ids.ts';
import type { SaveController } from '@core/save/public.ts';
import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { CONTENT_PREVIEW_MODAL_ID } from '@core/ui/modals/contentpreview/constants.ts';
import { isPromptsActionId } from '@pages/prompts/actions.ts';
import { PAGE_ID } from '@pages/prompts/contracts/PromptsPageSupport.ts';
import { dispatchPromptsClickAction } from '@pages/prompts/controllers/page/clickDispatch.ts';
import { PromptsPageRuntime } from '@pages/prompts/controllers/page/PromptsPageRuntime.ts';
import { createPromptsPromptPreviewHost } from '@pages/prompts/controllers/page/adapters.ts';
import { createPromptsSaveController } from '@pages/prompts/controllers/page/createPromptsSaveController.ts';
import { setupPromptsPageNonClickEvents } from '@pages/prompts/controllers/page/events.ts';
import { beforePageInitialize, loadData, onCollectionShellReady, onDestroy } from '@pages/prompts/controllers/page/service.ts';
import { initializePromptsViewMode } from '@pages/prompts/controllers/page/viewModeController.ts';
import { resolvePromptsSaveButtons } from '@pages/prompts/dom.ts';
import { openPromptContentPreview } from '@features/prompts/public.ts';
import { prepareCollectionReveal, releasePreparedCollection } from '@core/collectionpage/revealLifecycle.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import type { TrustedHtml } from '@core/security/public.ts';

class PromptsPage extends StaticBasePage {
    readonly #runtime: PromptsPageRuntime;
    readonly #save: SaveController;

    constructor(basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#runtime = new PromptsPageRuntime({
            owners: {
                dom: this.dependencies.dom,
                api: this.dependencies.api,
                storage: this.dependencies.storage,
                pageHost: this.pageHost,
                pageLifecycle: this.pageLifecycle,
                layout: this.layout,
                streaming: this.streaming,
                services: this.services,
                pageElements: this.pageElements,
                pageDom: this.pageDom,
                pageResources: this.pageResources,
                feedback: this.feedback
            }
        });
        this.#save = createPromptsSaveController(this.#runtime);
        this.pageResources.track(
            this.#runtime.components.promptEnhancer.onPromptCreated((promptId) => {
                terminateHandledPromise(openPromptContentPreview(createPromptsPromptPreviewHost(this.#runtime, this.#runtime.components.promptEnhancer, this.#save), promptId));
            })
        );
    }

    override getRequiredResources(): string[] {
        return [PROMPTS];
    }

    override async renderView(): Promise<TrustedHtml> {
        return await this.#runtime.collectionLifecycle.render();
    }

    #initializeCollectionView(): void {
        this.#runtime.collectionState.initializeView(this.#runtime.collections, this.#runtime.getCollectionViewOverrides());
    }

    override async loadData(parameters?: JsonObject, context?: { signal?: AbortSignal }): Promise<void> {
        this.#initializeCollectionView();
        await super.loadData(parameters, context);
        await loadData(this.#runtime);
    }

    override async setupPage(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        this.#initializeCollectionView();
        await super.setupPage(parameters, context);
    }

    override async beforePageInitialize(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await beforePageInitialize(this.#runtime, parameters);
    }

    override async initializeShell(parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.initializeShell(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        await this.#runtime.collectionState.initializeShell(
            this.#runtime.collectionLifecycle,
            parameters,
            async (readyParameters, layout) => {
                await onCollectionShellReady(this.#runtime, readyParameters ?? null, layout);
            },
            context
        );
    }

    bindPageEvents(): void {
        const signal = this.pageLifecycle.beginListeners();
        if (!(this.getDomContext() instanceof HTMLElement)) throw new Error('PromptsPage root container is not initialized');
        const ui = this.#runtime.operations.requireUi();
        initializePromptsViewMode(this.#runtime, ui);
        const contentPreviewModal = this.services.modals.requireElement(CONTENT_PREVIEW_MODAL_ID);
        const actionRoots: readonly HTMLElement[] = [ui.root, contentPreviewModal];
        setupPromptsPageNonClickEvents(this.#runtime, this.#save, actionRoots, signal);
        contentPreviewModal.addEventListener(
            'core.modal.close',
            () => {
                this.#runtime.state.viewedPromptId = null;
                this.#save.notifyChanged();
            },
            { signal }
        );
        this.#save.attach({ resolveSaveButtons: () => resolvePromptsSaveButtons(ui.root), autoNotifyRoot: ui.root, autoNotifyAdditionalRoots: [contentPreviewModal] });
        for (const [index, root] of actionRoots.entries()) {
            bindPageActionDispatcher({
                root,
                signal,
                label: index === 0 ? 'PromptsPage' : 'PromptsPage content preview modal',
                isAction: isPromptsActionId,
                assertKnownActions: index === 0,
                events: {
                    click: {
                        mouseButton: 'primary',
                        preventDefault: 'never',
                        onAction: ({ event, action, actionElement }) => dispatchPromptsClickAction(this.#runtime, this.#save, action, actionElement, event)
                    }
                }
            });
        }
    }

    override async startLiveUpdates(parameters?: JsonObject, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#runtime.collectionLifecycle.startLiveUpdates({ signal: context.signal });
        await super.startLiveUpdates(parameters, context);
    }

    override async prepareInitialContent(parameters?: JsonObject, context?: { signal?: AbortSignal }): Promise<void> {
        await super.prepareInitialContent(parameters, context);
        if (!signalAborted(context?.signal ?? null) && !this.isDestroyed && this.#runtime.collections.runtime) this.#runtime.operations.renderItems();
    }

    override async commitInitialContent(context: { signal?: AbortSignal } = {}): Promise<void> {
        await prepareCollectionReveal({ pageId: this.pageId, collections: this.#runtime.collections, layout: this.#runtime.collectionLayout, isDestroyed: () => this.isDestroyed }, this.pageHost.getSection(), context.signal ?? null);
        await super.commitInitialContent(context);
    }

    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        releasePreparedCollection(this.pageHost.getSection(), context.signal ?? null);
    }

    protected override beforePageRefreshCleanup(): void {
        this.pageLifecycle.abortListeners('refresh');
    }

    protected override refreshDomainState(): void {
        if (this.#runtime.collections.runtime?.size() === 0) this.#runtime.collections.runtime.refresh();
    }

    protected override cleanupDomainState(): void {
        this.#runtime.collections.cleanupState();
    }

    protected override onCollectionStateCleaned(): void {
        this.#runtime.collectionState.reset();
    }

    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners('prompts-destroy');
        this.#save.dispose();
        await onDestroy(this.#runtime);
        this.#runtime.state.clear();
        this.#runtime.collectionLifecycle.dispose();
        this.#runtime.collectionData.destroy();
    }
}

export { PromptsPage };
