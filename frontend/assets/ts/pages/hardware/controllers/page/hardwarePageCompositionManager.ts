/* SoAI - Hardware state, controller, renderer, and modal composition [frontend/assets/ts/pages/hardware/controllers/page/hardwarePageCompositionManager.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { terminateHandledPromise } from '@core/primitives/terminateHandledPromise.ts';
import type { ApiClient } from '@core/api/service.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import type { PageLifecycle } from '@core/routing/pages/basepage/PageLifecycle.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageFeedback } from '@core/routing/pages/basepagecore/PageFeedback.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';
import type { PageServices } from '@core/routing/pages/basepagecore/PageServices.ts';
import type { PageUi } from '@core/routing/pages/basepagecore/PageUi.ts';
import type { PageLayout } from '@core/routing/pages/basepagelayout/PageLayout.ts';
import type { PageStreaming } from '@core/routing/pages/basepagestreams/PageStreaming.ts';
import type { ResourceReconciliationSnapshot } from '@core/realtime/streammanager/resources/resourceReconciliationTypes.ts';
import { throwIfAborted } from '@core/errors/abort.ts';
import { HistoryChartControlsManager, HistoryChartRuntime } from '@features/charts/public.ts';
import type { ExportPreviewModal } from '@features/exportpreview/public.ts';
import { HistoryStateManager, type SoAIBenchHistoryModal, type SoAIBenchRunModal, type SystemInfoModal } from '@features/hardware/public.ts';
import type { HardwarePageDependencies } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import { buildHistoryRequestParameters, type HardwareHistoryContext } from '@pages/hardware/controllers/data/effects.ts';
import { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import { HardwareInteractionController } from '@pages/hardware/controllers/interactionController.ts';
import { HardwareOverflowNavController } from '@pages/hardware/controllers/hardwareOverflowNavController.ts';
import { HardwareLayoutController, type HardwareLayoutPageHost, type HardwareLayoutStorage } from '@pages/hardware/controllers/page/hardwareLayoutController.ts';
import { applyHardwarePageControls, persistHardwarePageControls } from '@pages/hardware/controllers/page/hardwarePageControlsController.ts';
import { HardwareRealtimeController } from '@pages/hardware/controllers/realtimeController.ts';
import { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import type { NetworkCardRenderer } from '@pages/hardware/rendering/cards/NetworkCardRenderer.ts';
import type { StorageCardRenderer } from '@pages/hardware/rendering/cards/StorageCardRenderer.ts';
import { buildHardwareExportSnapshotRequest } from '@pages/hardware/services/history/hardwareHistoryExport.ts';
import { createHardwareGpuController, composeHardwareProcessController, initializeHardwareUi } from '@pages/hardware/services/service.ts';
import { createHardwarePageState, type HardwarePageState } from '@pages/hardware/state/state.ts';
import type { ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';
import { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

interface HardwareCompositionOwners {
    api: ApiClient;
    storage: HardwareLayoutStorage;
    router: { navigate(route: string): Promise<void> };
    dom: {
        setHTML(element: Element, html: import('@core/security/public.ts').TrustedHtml | string, options?: { escape?: boolean }): void;
        setStyle(element: Element, property: string, value: string | null): void;
        hasClass(element: Element, className: string): boolean;
        getDocument(): Document;
    };
    pageLifecycle: PageLifecycle;
    pageDom: PageDom;
    pageResources: PageResources;
    pageElements: PageUi;
    services: PageServices;
    streaming: PageStreaming;
    feedback: PageFeedback;
    layout: PageLayout;
}

interface HardwarePageRuntime {
    state: HardwarePageState;
    chartRuntime: HistoryChartRuntime;
    historyControlsManager: HistoryChartControlsManager;
    historyStateManager: HistoryStateManager;
    gpuController: GpuControlManager;
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
    networkCardRenderer: NetworkCardRenderer;
    storageCardRenderer: StorageCardRenderer;
    systemInfoModal: SystemInfoModal;
    exportPreviewModal: ExportPreviewModal;
    soaibenchHistoryModal: SoAIBenchHistoryModal;
    soaibenchRunModal: SoAIBenchRunModal;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    realtimeController: HardwareRealtimeController;
    interactionController: HardwareInteractionController;
    overflowNavController: HardwareOverflowNavController;
    layoutController: HardwareLayoutController;
}

const composeHardwarePageRuntime = (owners: HardwareCompositionOwners, dependencies: HardwarePageDependencies, logger: ModuleLoggerFunctionValue): HardwarePageRuntime => {
    const state = createHardwarePageState();
    applyHardwarePageControls(owners.storage, state);
    const chartRuntime = new HistoryChartRuntime();
    const historyControlsManager = new HistoryChartControlsManager({ chartRuntime });
    const historyStateManager = new HistoryStateManager();
    const overflowNavController = new HardwareOverflowNavController();
    const dataController = new HardwareDataController({ state, chartOhlc: chartRuntime.getOhlc(), logger });
    let gpuController: GpuControlManager | null = null;
    let historyModal: SoAIBenchHistoryModal | null = null;
    const ui = initializeHardwareUi({
        owners,
        renderGpuControls: (options) => {
            if (!gpuController) throw new Error('Hardware GPU controller is not initialized');
            gpuController.renderGpuControls(options);
        },
        showSoAIBenchHistory: async (request) => {
            if (!historyModal) throw new Error('Hardware benchmark history modal is not initialized');
            await historyModal.open(request);
        }
    });
    historyModal = ui.soaibenchHistoryModal;
    gpuController = createHardwareGpuController({ owners, state, chartRuntime, historyModal: ui.soaibenchHistoryModal, runModal: ui.soaibenchRunModal }, dependencies.security);
    const processController = composeHardwareProcessController({ owners, state });
    const memorySwapController = new MemorySwapPanelController({
        optionalHTMLElement: (selector: string, parent?: Element | null) => owners.pageDom.optionalHTMLElement(selector, parent ?? undefined),
        updateText: (element: Element, text: string) => owners.pageDom.updateText(element, text),
        createElement: (tag: string, attrs?: ElementOptions) => owners.pageElements.createElement(tag, attrs),
        setStyle: (element: Element, property: string, value: string) => owners.dom.setStyle(element, property, value)
    });
    const layoutController = new HardwareLayoutController(createHardwareLayoutDependencies(owners, state, logger));
    const renderController = new HardwareRenderController({
        state,
        dataController,
        chartRuntime,
        historyControlsManager,
        requireHTMLElement: (id: string) => owners.pageDom.requireHTMLElement(id),
        requireUI: (selector: string, context?: Element | null) => owners.pageDom.require(selector, context ?? undefined),
        optionalUI: (selector: string, context?: Element | null) => owners.pageDom.optional(selector, context ?? undefined),
        createElement: (tag: string, attrs?: ElementOptions) => owners.pageElements.createElement(tag, attrs),
        updateText: (element: Element, text: string) => owners.pageDom.updateText(element, text),
        flushDOMUpdates: () => owners.pageDom.flush(),
        networkCardRenderer: ui.networkCardRenderer,
        storageCardRenderer: ui.storageCardRenderer,
        processController,
        gpuController
    });
    const realtimeController = new HardwareRealtimeController({
        state,
        dataController,
        renderController,
        historyStateManager,
        historyControlsManager,
        chartDataTransforms: chartRuntime.getDataTransforms(),
        chartOhlc: chartRuntime.getOhlc(),
        logger,
        runWithBoundary: <T>(boundaryKey: string, functionValue: () => Promise<T>) => owners.pageLifecycle.run(boundaryKey, functionValue),
        handleError: (error, message, options) => owners.feedback.handle(error, message, options),
        getStreamManager: async (options) => {
            throwIfAborted(options.signal);
            return owners.streaming.runtime();
        },
        peekStreamManager: () => owners.streaming.runtime(),
        ensureDataSubscriptions: (options) => owners.streaming.ensureSubscriptions(options),
        subscribeToResourceState: (resource: string, listener: (snapshot: ResourceReconciliationSnapshot) => void) => owners.streaming.subscribeResourceState(resource, listener),
        trackDisposable: (resource, onDispose) => owners.pageResources.track(resource, onDispose),
        hasProcessPanel: () => layoutController.hasPanel('processes'),
        resources: owners.pageResources,
        gpuController,
        processController,
        memorySwapController
    });
    const interactionController = new HardwareInteractionController({
        processController,
        memorySwapController,
        gpuController,
        systemInfoModal: ui.systemInfoModal,
        dataController,
        renderController,
        realtimeController,
        exportHistoryCsv: () => openHardwareExportPreview(state, chartRuntime, historyControlsManager, dataController, ui.exportPreviewModal),
        persistPageControls: () => persistHardwarePageControls(owners.storage, state, { column: processController.sortColumn, direction: processController.sortDirection }),
        navigateToLogs: () => {
            terminateHandledPromise(owners.router.navigate('logs'));
        },
        logger
    });
    return { state, chartRuntime, historyControlsManager, historyStateManager, gpuController, processController, memorySwapController, networkCardRenderer: ui.networkCardRenderer, storageCardRenderer: ui.storageCardRenderer, systemInfoModal: ui.systemInfoModal, exportPreviewModal: ui.exportPreviewModal, soaibenchHistoryModal: ui.soaibenchHistoryModal, soaibenchRunModal: ui.soaibenchRunModal, dataController, renderController, realtimeController, interactionController, overflowNavController, layoutController };
};

const createHardwareLayoutDependencies = (owners: HardwareCompositionOwners, state: HardwarePageState, logger: ModuleLoggerFunctionValue): HardwareLayoutPageHost => ({
    state,
    storage: owners.storage,
    logger,
    optionalUI: (selector, context) => owners.pageDom.optional(selector, context ?? undefined),
    optionalHTMLElement: (selector, context) => owners.pageDom.optionalHTMLElement(selector, context ?? undefined),
    requireHTMLElement: (selector, context) => owners.pageDom.requireHTMLElement(selector, context ?? undefined),
    replaceElementContent: (target, content, options) => owners.pageDom.replaceContent(target, content, options),
    flushDOMUpdates: () => owners.pageDom.flush(),
    isDetached: () => owners.services.isDetached(),
    on: (target, event, handler, options) => owners.pageResources.on(target, event, handler, options),
    updateStyle: (element, property, value) => owners.pageDom.updateStyle(element, property, value),
    updateStyles: (element, styles) => owners.pageDom.updateStyles(element, styles),
    applyGridPosition: (element, position) => owners.layout.applyGridPosition(element, position),
    createSection: (id, options) => owners.pageElements.createSection(id, options)
});

const openHardwareExportPreview = async (state: HardwarePageState, chartRuntime: HistoryChartRuntime, historyControlsManager: HistoryChartControlsManager, dataController: HardwareDataController, exportPreviewModal: ExportPreviewModal): Promise<void> => {
    const historyContext: HardwareHistoryContext = { state, chartOhlc: chartRuntime.getOhlc(), historyControlsManager, getSelectedHistoryTarget: () => dataController.getSelectedHistoryTarget(), resolveSupportedHistoryComponent: (component) => dataController.resolveSupportedHistoryComponent(component) };
    await exportPreviewModal.open(buildHardwareExportSnapshotRequest(buildHistoryRequestParameters(historyContext)));
};

export { composeHardwarePageRuntime };
export type { HardwareCompositionOwners, HardwarePageRuntime };
