/* SoAI - Dashboard routed page [frontend/assets/ts/pages/dashboard/DashboardPage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import { buildSignalRequestOptions } from '@core/api/requestOptions.ts';
import { bindPageActionDispatcher } from '@core/dom/dataActionBinding.ts';
import { getWindow } from '@core/environment/public.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { i18n } from '@core/i18n/index.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { toTrustedHtml, type TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { JsonObject, JsonValue } from '@core/types/jsonValues.ts';
import type { FirstRunModalService } from '@core/firstrun/protocols.ts';
import type { LogStream } from '@features/logging/public.ts';
import { isDashboardActionId, type DashboardActionId } from '@pages/dashboard/actions.ts';
import type { DashboardRuntime, StatusManagerContract } from '@pages/dashboard/contracts/contracts.ts';
import { PAGE_ID, PAGE_MODULE_ID } from '@pages/dashboard/contracts/constants.ts';
import { DASHBOARD_REQUIRED_RESOURCES_FOR_READY, dashboardLogger, type DashboardPageDependencies } from '@pages/dashboard/contracts/DashboardPageSupport.ts';
import { DashboardActionDispatchController } from '@pages/dashboard/controllers/DashboardActionDispatchController.ts';
import type { DashboardBlueprint, DashboardBlueprintId } from '@pages/dashboard/controllers/dashboardBlueprints.ts';
import type { DashboardLiveDataKey, DashboardSectionId } from '@pages/dashboard/controllers/dashboardLiveData.ts';
import { DashboardSubscriptionsController } from '@pages/dashboard/controllers/dashboardSubscriptionsController.ts';
import { composeDashboardRuntime } from '@pages/dashboard/controllers/composeDashboardRuntime.ts';
import { requireDashboardUi } from '@pages/dashboard/dom.ts';
import { DASHBOARD_GRID_SETTINGS } from '@pages/dashboard/rendering/layout/constants.ts';
import { destroyDashboardWidgetRuntime, handleDashboardLiveDataUpdate, queueDashboardSectionRender } from '@pages/dashboard/services/service.ts';
import { createInitialDashboardState } from '@pages/dashboard/state/dashboardStateModel.ts';
import type { DashboardUiRefs } from '@pages/dashboard/types.ts';
import { renderDashboardPageView } from '@pages/dashboard/view.ts';
import type { DashboardEditionContribution } from '@core/edition/dashboardContribution.ts';

class DashboardPage extends StaticBasePage {
    #ui: DashboardUiRefs | null = null;
    #blueprints: Map<DashboardBlueprintId, DashboardBlueprint> | null = null;
    readonly #runtime: DashboardRuntime;
    readonly #firstRunModals: FirstRunModalService;
    readonly #logStream: LogStream;
    readonly #edition: DashboardEditionContribution | null;
    readonly #subscriptions: DashboardSubscriptionsController = new DashboardSubscriptionsController();
    constructor({ firstRunModals, logStream, edition }: DashboardPageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#firstRunModals = firstRunModals;
        this.#logStream = logStream;
        this.#edition = edition;
        this.#runtime = this.createRuntime();
        this.layout.configure({
            onResponsiveLayout: () => {
                this.#runtime.layout.updateResponsiveLayout();
                this.#runtime.layoutEdit.sync();
            }
        });
    }
    #getUi(): DashboardUiRefs {
        if (this.#ui) {
            return this.#ui;
        }
        this.#ui = requireDashboardUi({ pageDom: this.pageDom });
        return this.#ui;
    }
    override getRequiredResources(): string[] {
        return [...DASHBOARD_REQUIRED_RESOURCES_FOR_READY];
    }
    override async renderView(): Promise<TrustedHtml> {
        return toTrustedHtml(renderDashboardPageView({ columns: DASHBOARD_GRID_SETTINGS.columns }));
    }
    override async beforePageInitialize(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.beforePageInitialize(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#blueprints = this.#runtime.createBlueprints();
        this.#runtime.layout.load(this.#blueprints);
    }
    override async setupPage(parameters: JsonObject | null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.setupPage(parameters, context);
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        this.#runtime.layout.initialize();
        this.#runtime.layoutEdit.initialize();
        await this.createSections();
    }
    async createSections(): Promise<void> {
        const ui = this.#getUi();
        const { fragment, rendered } = this.#runtime.layout.renderSections();
        this.pageDom.replaceContent(ui.grid, fragment, { escape: false });
        this.pageDom.flush();
        this.#runtime.layout.applyInitialLayout();
        await Promise.all(rendered.map(({ id, section }: { id: DashboardBlueprintId; section: Element }): Promise<void> => this.loadSectionContent(id, section)));
    }
    override async prepareInitialContent(_parameters: JsonObject | null, context: { signal?: AbortSignal } | null = null): Promise<void> {
        const signal = context?.signal;
        throwIfAborted(signal);
        this.setupDashboardSubscriptions();
        await this.streaming.ensureSubscriptions(buildSignalRequestOptions({ signal }));
        throwIfAborted(signal);
        await this.#runtime.sectionRenderQueue.setSectionsReady(true);
        throwIfAborted(signal);
        if (!this.isDestroyed) {
            await this.#runtime.logs.activate();
        }
        this.#runtime.logs.render();
    }
    override async onHide(): Promise<void> {
        await this.#runtime.sectionRenderQueue.setSectionsReady(false);
        this.#runtime.logs.deactivate();
        await super.onHide();
    }
    async loadSectionContent(id: DashboardBlueprintId, section: Element): Promise<void> {
        const blueprint = this.#blueprints?.get(id);
        if (!blueprint) {
            throw new Error(`Unsupported dashboard section "${id}" requested`);
        }
        if (id === 'logs') {
            this.#runtime.logs.mount(this.pageDom.requireHTMLElement('#logs-content', section));
        }
        await blueprint.render();
    }
    override async loadData(_parameters: JsonObject | null, context: { signal?: AbortSignal } | null = null): Promise<void> {
        const signal = context?.signal;
        await this.pageLifecycle.run('dashboard:loadData', async (): Promise<void> => {
            throwIfAborted(signal);
        });
    }
    override async startLiveUpdates(parameters?: JsonObject | null, context: { signal?: AbortSignal; setStage?(stage: string): void } = {}): Promise<void> {
        await super.startLiveUpdates(parameters, context);
        const { signal } = context;
        throwIfAborted(signal);
        if (this.isDestroyed) {
            return;
        }
        await this.#firstRunModals.handlePageShow('dashboard', signal ? { signal } : {});
    }
    setupDashboardSubscriptions(): void {
        const productSection = this.#runtime.productSection;
        this.#subscriptions.setup(
            {
                streaming: this.streaming,
                pageDom: this.pageDom,
                registerDashboardSubscription: (subscription) => this.pageResources.track(subscription),
                handleLiveDataUpdate: (type, payload) => this.handleLiveDataUpdate(type, payload),
                queueSectionRender: (sectionId) => this.queueSectionRender(sectionId)
            },
            productSection ? (listener) => productSection.subscribe(listener) : null
        );
    }
    override async onRefresh(parameters: JsonObject | null): Promise<void> {
        destroyDashboardWidgetRuntime(this.#runtime);
        this.#subscriptions.destroy();
        this.#runtime.sectionRenderQueue.clear();
        this.#runtime.liveDataContext.dataReceived.clear();
        this.#runtime.liveDataContext.sectionDataFingerprints.clear();
        this.#runtime.liveDataContext.state = createInitialDashboardState();
        this.#runtime.liveDataContext.rawHardwareSnapshot = null;
        this.#blueprints = null;
        this.#ui = null;
        await super.onRefresh(parameters);
    }
    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners('dashboard-destroy');
        destroyDashboardWidgetRuntime(this.#runtime);
        this.#runtime.sectionRenderQueue.clear();
        this.#runtime.liveDataContext.dataReceived.clear();
        this.#runtime.liveDataContext.sectionDataFingerprints.clear();
        this.#runtime.liveDataContext.state = createInitialDashboardState();
        this.#runtime.liveDataContext.rawHardwareSnapshot = null;
        this.#subscriptions.destroy();
        this.#ui = null;
    }
    bindPageEvents(): void {
        const signal = this.pageLifecycle.beginListeners();
        const root = this.#getUi().root;
        bindPageActionDispatcher({
            root,
            signal,
            label: 'DashboardPage',
            isAction: isDashboardActionId,
            events: {
                click: {
                    mouseButton: 'primary',
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => DashboardActionDispatchController.dispatchClickAction(this.#runtime, event, action, actionElement)
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ event, action }): void => DashboardActionDispatchController.dispatchChangeAction(this.#runtime, event, action)
                }
            }
        });
        const handleDashboardCustomizationChanged = (): void => this.handleCustomizationChange();
        getWindow().addEventListener('soai:dashboard:customization:changed', handleDashboardCustomizationChanged, { signal });
        this.pageResources.track(
            this.layout.registerUnsavedChanges({
                hasUnsavedChanges: (): boolean => this.#runtime.memo.hasChanges() || this.#runtime.layoutEdit.hasChanges(),
                confirmMessage: i18n.t('common.unsavedChanges'),
                guardId: 'dashboard-dirty-guard'
            })
        );
    }
    handleCustomizationChange(): void {
        this.#runtime.layoutEdit.sync();
    }
    handleLiveDataUpdate(type: DashboardLiveDataKey, payload: JsonValue | null): void {
        handleDashboardLiveDataUpdate({
            liveDataContext: this.#runtime.liveDataContext,
            queueRender: (sectionId: DashboardSectionId): void => {
                this.queueSectionRender(sectionId);
            },
            isDestroyed: (): boolean => this.isDestroyed,
            type,
            payload
        });
        if (type === 'metrics') {
            this.#runtime.throughput.update();
        }
    }
    queueSectionRender(sectionId: DashboardSectionId): void {
        queueDashboardSectionRender(
            {
                isDestroyed: (): boolean => this.isDestroyed,
                blueprints: this.#blueprints,
                queue: this.#runtime.sectionRenderQueue
            },
            sectionId
        );
    }
    private createRuntime(): DashboardRuntime {
        return composeDashboardRuntime({
            infrastructure: {
                auth: this.dependencies.auth,
                feedback: this.feedback,
                layout: this.layout,
                pageDom: this.pageDom,
                pageElements: this.pageElements,
                pageResources: this.pageResources,
                router: this.dependencies.router,
                services: this.services,
                storage: this.dependencies.storage
            },
            state: {
                getBlueprints: () => this.#blueprints,
                getCurrentStatus: (): StatusManagerContract | null => this.dependencies.stateManager.status ?? null,
                isDestroyed: () => this.isDestroyed
            },
            logs: {
                ensureReady: async () => {
                    if (!isFunction(this.#logStream.subscribe)) throw new Error('Log stream service must expose subscribe before dashboard logs activation');
                    return this.#logStream;
                },
                debug: (message, detail) => dashboardLogger('debug', message, detail),
                error: (message, detail) => dashboardLogger('error', message, detail)
            },
            actions: {
                onLogsAction: (actionId: DashboardActionId, target: HTMLElement) => this.#runtime.logs.handleAction(actionId, target),
                onImageUploadOpen: () => this.#runtime.imageCard.triggerUploadDialog(),
                onImageDelete: () => this.#runtime.imageCard.handleDelete(),
                onImageToggleFit: () => this.#runtime.imageCard.handleToggleFit()
            },
            edition: this.#edition
        });
    }
}
export { DashboardPage, PAGE_ID, PAGE_MODULE_ID };
