/* SoAI - Hardware routed page [frontend/assets/ts/pages/hardware/HardwarePage.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { BasePageDependencies } from '@core/routing/pages/pagetypes/public.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import { createHeaderActionController, type HeaderActionController } from '@core/headerActionBus.ts';
import { i18n } from '@core/i18n/index.ts';
import { DomObserver } from '@core/dom/dom.ts';
import { bindPageActionDispatcher, bindTypedResolvedDataActionListener } from '@core/dom/dataActionBinding.ts';
import { signalAborted } from '@core/lifecycle/abortSignals.ts';
import { HARDWARE } from '@core/realtime/streammanager/resources/ids.ts';
import { closeDetachedRuntimeWindowsByPage, openDetachedRuntimeWindow } from '@core/runtimeenv/public.ts';
import { createModuleLogger } from '@core/runtime/runtimeContext.ts';
import type { TrustedHtml } from '@core/security/public.ts';
import { StaticBasePage } from '@core/StaticBasePage.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { isHardwareActionId } from '@pages/hardware/actions.ts';
import type { HardwarePageDependencies } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { prepareHardwarePageContent } from '@pages/hardware/controllers/effects.ts';
import { composeHardwarePageRuntime, type HardwarePageRuntime } from '@pages/hardware/controllers/page/hardwarePageCompositionManager.ts';
import { destroyChart } from '@pages/hardware/controllers/render/effects.ts';
import { syncMetricOptions, updateDeviceSelector } from '@pages/hardware/controllers/render/events.ts';
import { destroyWidgetManager, resetHistoryStatusElement } from '@pages/hardware/controllers/render/rendering.ts';
import { initializeHardwarePageBootstrapController } from '@pages/hardware/controllers/page/hardwarePageBootstrapController.ts';
import { renderHardwarePageView } from '@pages/hardware/view.ts';
export const PAGE_ID = 'hardware';
export const PAGE_MODULE_ID = 'pages.HardwarePage';
const hardwareLogger = createModuleLogger('HardwarePage', { defaultLevel: 'warn' });
class HardwarePage extends StaticBasePage {
    readonly #runtime: HardwarePageRuntime;
    #detachActionController: HeaderActionController | null = null;
    constructor({ storage, security }: HardwarePageDependencies, basePageDependencies: BasePageDependencies) {
        super(PAGE_ID, { dependencies: basePageDependencies });
        this.#runtime = composeHardwarePageRuntime(
            {
                api: this.dependencies.api,
                storage: this.dependencies.storage,
                router: this.dependencies.router,
                dom: this.dependencies.dom,
                pageLifecycle: this.pageLifecycle,
                pageDom: this.pageDom,
                pageResources: this.pageResources,
                pageElements: this.pageElements,
                services: this.services,
                streaming: this.streaming,
                feedback: this.feedback,
                layout: this.layout
            },
            { storage, security },
            hardwareLogger
        );
        this.layout.configure({ onResponsiveLayout: () => this.#runtime.layoutController.onResponsiveLayout() });
    }
    override async renderView(): Promise<TrustedHtml> {
        return renderHardwarePageView({
            getIconSync: (iconName: IconName, options?: IconOptions) => this.services.getIconSync(iconName, options),
            generateStandardHeader: (options) => this.layout.generateHeader(options)
        });
    }
    override getRequiredResources(): string[] {
        return [HARDWARE];
    }
    override async setupPage(_parameters: JsonObject | null = null, context: { signal?: AbortSignal } = {}): Promise<void> {
        await this.#runtime.layoutController.initialize();
        if (signalAborted(context.signal ?? null)) {
            return;
        }
        const hasProcessPanel = this.#runtime.layoutController.hasPanel('processes');
        this.#runtime.processController.setDomRequired(hasProcessPanel);
        this.#runtime.memorySwapController.setProcessPermission(hasProcessPanel);
        this.#runtime.renderController.applyPermissionGates();
        const setupSequence = this.#runtime.renderController.beginChartFiltersSetup();
        await this.#runtime.renderController.ensureChartModules(setupSequence);
        if (signalAborted(context.signal ?? null) || !this.#runtime.renderController.isChartFiltersSetupCurrent(setupSequence)) {
            return;
        }
        this.#runtime.renderController.initializeChartFilters(this.#runtime.interactionController.getChartFilterHandlers());
        if (hasProcessPanel) {
            this.#runtime.processController.suspendProcessRowsHydration();
            this.#runtime.processController.initialize();
        }
        this.#runtime.memorySwapController.initialize();
        if (!this.services.isDetached()) {
            this.#detachActionController ??= createHeaderActionController({ actionId: 'detach', contextId: 'hardware' });
            this.#detachActionController.show({ onClick: () => this.#openDetachedWindow() });
        }
    }
    override async loadData(_parameters?: JsonObject | null, _context: { signal?: AbortSignal } | null = null): Promise<void> {
        if (this.#runtime.layoutController.hasPanel('processes')) {
            this.#runtime.processController.reset();
        }
        this.#runtime.memorySwapController.resetProcessData();
        updateDeviceSelector(this.#runtime.renderController.filtersContext, this.#runtime.state.lastSnapshot);
        syncMetricOptions(this.#runtime.renderController.filtersContext);
    }
    bindPageEvents(): void {
        const signal = this.pageLifecycle.beginListeners();
        const root = this.resolveHostContainer();
        initializeHardwarePageBootstrapController({
            root,
            signal,
            pageDom: this.pageDom,
            interactionController: this.#runtime.interactionController,
            overflowNavController: this.#runtime.overflowNavController,
            systemInfoModal: this.#runtime.systemInfoModal,
            exportPreviewModal: this.#runtime.exportPreviewModal,
            soaibenchHistoryModal: this.#runtime.soaibenchHistoryModal,
            soaibenchRunModal: this.#runtime.soaibenchRunModal
        });
        bindTypedResolvedDataActionListener({
            eventType: 'click',
            signal,
            root,
            isAction: isHardwareActionId,
            mouseButton: 'primary',
            preventDefault: 'never',
            onAction: ({ event, action, actionElement }): Promise<void> => {
                if (!(event instanceof MouseEvent)) {
                    throw new Error('Hardware click action requires a mouse event');
                }
                return this.#runtime.interactionController.handleRootActionClick(event, action, actionElement);
            },
            onMiss: ({ event }): void => {
                if (!(event instanceof MouseEvent)) {
                    throw new Error('Hardware click miss requires a mouse event');
                }
                this.#runtime.interactionController.handleRootClickMiss(event);
            }
        });
        bindPageActionDispatcher({
            label: 'HardwarePage',
            root,
            signal,
            isAction: isHardwareActionId,
            events: {
                input: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => this.#runtime.interactionController.handleRootActionInput(event, action, actionElement)
                },
                change: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => this.#runtime.interactionController.handleRootActionChange(event, action, actionElement)
                },
                keydown: {
                    preventDefault: 'never',
                    onAction: ({ event, action, actionElement }): void => {
                        if (!(event instanceof KeyboardEvent)) {
                            throw new Error('Hardware keydown action requires a keyboard event');
                        }
                        this.#runtime.interactionController.handleRootActionKeydown(event, action, actionElement);
                    }
                }
            }
        });
        this.pageResources.track(
            this.layout.registerUnsavedChanges({
                hasUnsavedChanges: (): boolean => this.#runtime.layoutController.hasChanges(),
                confirmMessage: i18n.t('common.unsavedChanges'),
                guardId: 'hardware-layout-dirty-guard'
            })
        );
    }
    override async prepareInitialContent(_parameters?: JsonObject | null, context: { signal?: AbortSignal } | null = null): Promise<void> {
        const signal = context?.signal ?? null;
        await prepareHardwarePageContent({
            applySelectionFromQuery: () => this.#runtime.interactionController.applySelectionFromQuery(this.dependencies.router),
            scheduleChartBootstrap: async (options) => this.#runtime.realtimeController.scheduleChartBootstrap(options),
            signal
        });
        await this.#runtime.renderController.waitForInitialWidgets();
    }
    override async afterPageReveal(context: { signal?: AbortSignal } = {}): Promise<void> {
        await super.afterPageReveal(context);
        if (this.#runtime.layoutController.hasPanel('processes')) {
            await DomObserver.animationFrame();
            if (context.signal?.aborted) {
                return;
            }
            await DomObserver.animationFrame();
            if (context.signal?.aborted) {
                return;
            }
            this.#runtime.processController.hydrateProcessRows();
        }
    }
    override async onHide(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#disposeDetachAction();
        this.#runtime.gpuController.setDomRequired(false);
        this.#runtime.exportPreviewModal.disposeForPageLifecycle('pageHide');
        this.#runtime.overflowNavController.dispose();
        this.#runtime.interactionController.dispose();
        this.#runtime.memorySwapController.dispose();
        resetHistoryStatusElement(this.#runtime.renderController.renderCache);
        this.#runtime.realtimeController.cleanupAllStreams();
        this.#runtime.realtimeController.resetBootstrapState();
        destroyWidgetManager(this.#runtime.renderController.renderCache);
        await destroyChart(this.#runtime.renderController.chartContext);
        this.#runtime.renderController.disposeChartFilters();
        await super.onHide();
    }
    override async onRefresh(payload?: JsonObject | null): Promise<void> {
        await super.onRefresh(payload);
        await this.#runtime.realtimeController.ensureWebuiPermissionsLoaded();
        this.#runtime.memorySwapController.setProcessPermission(this.#runtime.layoutController.hasPanel('processes'));
        this.#runtime.realtimeController.setupRealtimeSubscriptions();
        await this.streaming.ensureSubscriptions();
    }
    override async onDestroy(): Promise<void> {
        this.pageLifecycle.abortListeners();
        this.#disposeDetachAction();
        this.#runtime.exportPreviewModal.disposeForPageLifecycle('pageDestroy');
        this.#runtime.overflowNavController.dispose();
        this.#runtime.layoutController.destroy();
        this.#runtime.interactionController.dispose();
        this.#runtime.memorySwapController.dispose();
        resetHistoryStatusElement(this.#runtime.renderController.renderCache);
        this.#runtime.realtimeController.cleanupAllStreams();
        this.#runtime.realtimeController.resetBootstrapState();
        destroyWidgetManager(this.#runtime.renderController.renderCache);
        await destroyChart(this.#runtime.renderController.chartContext);
        this.#runtime.chartRuntime.reset();
        this.streaming.resetManager();
        this.#runtime.gpuController.dispose();
        this.#runtime.renderController.disposeChartFilters();
    }

    #openDetachedWindow(): void {
        closeDetachedRuntimeWindowsByPage(PAGE_ID);
        openDetachedRuntimeWindow(PAGE_ID, { title: i18n.t('pages.hardware.title') });
    }

    #disposeDetachAction(): void {
        this.#detachActionController?.dispose();
        this.#detachActionController = null;
    }
}
export { HardwarePage };
