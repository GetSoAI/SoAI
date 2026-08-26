/* SoAI - Hardware page render controller [frontend/assets/ts/pages/hardware/controllers/renderController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { ElementOptions } from '@core/dom/dom.ts';
import { errorHandler } from '@core/errorHandler.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { i18n } from '@core/i18n/index.ts';
import { buildChartColorContext } from '@core/ui/chartColors.ts';
import { ChartFilters, FILTER_TYPES, HistoryChartControlsManager, HistoryChartRuntime, initializeHistoryChartFilters } from '@features/charts/public.ts';
import { isCandlestickActive, resetHistoryState, trimHistoryData } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import type { HardwareChartContext } from '@pages/hardware/controllers/render/effects.ts';
import { applyChartDefaults, invalidateChartControlSync, refreshChartControls, syncMetricOptions, updateDeviceSelector, type HardwareRenderFiltersContext } from '@pages/hardware/controllers/render/events.ts';
import { createHardwareChartPresentationController, type HardwareChartPresentationController } from '@pages/hardware/controllers/render/hardwareChartPresentationController.ts';
import { initializeWidgetManager, renderNetworkCard, renderStorageCard, updateGpuTelemetryIndicators, updateHeaderStats, type HardwareRenderActionsContext, type HardwareRenderCache } from '@pages/hardware/controllers/render/rendering.ts';
import { buildDeviceCategoryOptions, buildMetricOptions, formatMetricValue, getMetricLabel, getMetricScaleBounds } from '@pages/hardware/mappers/mappers.ts';
import type { NetworkCardRenderer } from '@pages/hardware/rendering/cards/NetworkCardRenderer.ts';
import type { StorageCardRenderer } from '@pages/hardware/rendering/cards/StorageCardRenderer.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

type HardwareChartFilterHandlers = {
    onChartTypeChange: (value: string | number) => void;
    onDeviceChange: (value: string | number) => void;
    onMetricChange: (value: string | number) => void;
    onTimeRangeChange: (value: string | number) => void;
    onCandleIntervalChange: (value: string | number) => void;
};

type HardwareRenderControllerDependencies = {
    state: HardwarePageState;
    dataController: HardwareDataController;
    chartRuntime: HistoryChartRuntime;
    historyControlsManager: HistoryChartControlsManager;
    requireHTMLElement: (id: string) => HTMLElement;
    requireUI: (selector: string, context?: Element | null) => Element;
    optionalUI: (selector: string, context?: Element | null) => Element | null;
    createElement: (tag: string, attrs?: ElementOptions) => Element;
    updateText: (element: Element, text: string) => void;
    flushDOMUpdates: () => void;
    networkCardRenderer: NetworkCardRenderer;
    storageCardRenderer: StorageCardRenderer;
    processController: ProcessTableManager;
    gpuController: GpuControlManager;
};

class HardwareRenderController {
    state: HardwarePageState;
    dataController: HardwareDataController;
    chartRuntime: HistoryChartRuntime;
    historyControlsManager: HistoryChartControlsManager;
    requireHTMLElement: (id: string) => HTMLElement;
    requireUI: (selector: string, context?: Element | null) => Element;
    optionalUI: (selector: string, context?: Element | null) => Element | null;
    createElement: (tag: string, attrs?: ElementOptions) => Element;
    updateText: (element: Element, text: string) => void;
    flushDOMUpdates: () => void;
    networkCardRenderer: NetworkCardRenderer;
    storageCardRenderer: StorageCardRenderer;
    processController: ProcessTableManager;
    gpuController: GpuControlManager;
    chartFilters: ChartFilters | null = null;
    renderCache: HardwareRenderCache;
    chartContext: HardwareChartContext;
    actionsContext: HardwareRenderActionsContext;
    filtersContext: HardwareRenderFiltersContext;
    #chartPresentationController: HardwareChartPresentationController;
    #chartFiltersSetupSequence = 0;
    #widgetManagerReadyTask: Promise<void> | null = null;

    constructor(dependencies: HardwareRenderControllerDependencies) {
        this.state = dependencies.state;
        this.dataController = dependencies.dataController;
        this.chartRuntime = dependencies.chartRuntime;
        this.historyControlsManager = dependencies.historyControlsManager;
        this.requireHTMLElement = dependencies.requireHTMLElement;
        this.requireUI = dependencies.requireUI;
        this.optionalUI = dependencies.optionalUI;
        this.createElement = dependencies.createElement;
        this.updateText = dependencies.updateText;
        this.flushDOMUpdates = dependencies.flushDOMUpdates;
        this.networkCardRenderer = dependencies.networkCardRenderer;
        this.storageCardRenderer = dependencies.storageCardRenderer;
        this.processController = dependencies.processController;
        this.gpuController = dependencies.gpuController;
        this.renderCache = {
            historyStatusElement: null,
            widgetManager: null,
            widgetManagerInitialized: false
        };
        this.#chartPresentationController = createHardwareChartPresentationController(() => dependencies.requireHTMLElement('hardwareHistoryChart'));
        this.chartContext = {
            state: this.state,
            chartRuntime: this.chartRuntime,
            requireHTMLElement: this.requireHTMLElement,
            beginChartPresentationLoad: () => this.#chartPresentationController.beginLoad(),
            completeChartPresentationLoad: (sequence) => this.#chartPresentationController.completeLoad(sequence),
            resetChartPresentation: () => this.#chartPresentationController.reset(),
            destroyChartPresentation: () => this.#chartPresentationController.destroy(),
            getMetricScaleBounds: () => getMetricScaleBounds(this.state),
            buildChartColorContext: () =>
                buildChartColorContext({
                    device: this.state.selectedDevice,
                    deviceOptions: buildDeviceCategoryOptions(this.state),
                    metric: this.state.selectedMetric,
                    metricOptions: buildMetricOptions(this.state, this.dataController.getSelectedHistoryTarget().type, this.state.selectedMetric)
                }),
            getMetricLabel: () => getMetricLabel(this.state),
            formatMetricValue: (value: number) => formatMetricValue(this.state, value),
            isCandlestickActive: () => isCandlestickActive(this.state),
            resetHistoryState: (options) => resetHistoryState(this.state, options),
            trimHistoryData: (force?: boolean) => trimHistoryData(this.state, force)
        };
        this.actionsContext = {
            state: this.state,
            chartRuntime: this.chartRuntime,
            optionalUI: this.optionalUI,
            requireHTMLElement: this.requireHTMLElement,
            requireUI: this.requireUI,
            createElement: this.createElement,
            updateText: this.updateText,
            networkCardRenderer: this.networkCardRenderer,
            storageCardRenderer: this.storageCardRenderer,
            processController: this.processController,
            gpuController: this.gpuController
        };
        this.filtersContext = {
            state: this.state,
            dataController: this.dataController,
            historyControlsManager: this.historyControlsManager,
            chartContext: this.chartContext,
            chartFilters: this.chartFilters
        };
    }

    beginChartFiltersSetup(): number {
        this.#chartFiltersSetupSequence += 1;
        return this.#chartFiltersSetupSequence;
    }

    isChartFiltersSetupCurrent(sequence: number): boolean {
        return this.#chartFiltersSetupSequence === sequence;
    }

    async ensureChartModules(sequence: number | null = null): Promise<void> {
        await this.chartRuntime.loadDefaults();
        if (sequence !== null && !this.isChartFiltersSetupCurrent(sequence)) {
            return;
        }
        applyChartDefaults(this.filtersContext, this.chartRuntime.getDefaults());
    }

    initializeChartFilters(handlers: HardwareChartFilterHandlers): void {
        const container = this.requireHTMLElement('hardwareChartFilters');
        const categories = buildDeviceCategoryOptions(this.state);
        if (!categories[0]) {
            throw new Error('Hardware chart filters require at least one device option');
        }
        if (!categories.some((entry) => entry.value === this.state.selectedDevice)) {
            this.state.selectedDevice = categories[0].value;
        }
        this.dataController.ensureMetricForDevice(this.dataController.getSelectedHistoryTarget().type);
        this.chartFilters = initializeHistoryChartFilters({
            container,
            pageId: 'hardware',
            chartRuntime: this.chartRuntime,
            config: {
                showCategory: true,
                showSubcategory: true,
                categories,
                subcategories: buildMetricOptions(this.state, this.dataController.getSelectedHistoryTarget().type, this.state.selectedMetric),
                timeRangeOptions: this.state.availableTimeRanges,
                candleIntervals: this.state.baseCandleIntervals,
                initialChartType: this.state.chartType,
                initialCategory: this.state.selectedDevice,
                initialSubcategory: this.state.selectedMetric,
                initialTimeRange: this.state.timeRange,
                initialCandleInterval: this.state.candlestickIntervalMinutes,
                filterLabels: {
                    [FILTER_TYPES.CATEGORY]: i18n.t('hardware.cards.history.filters.device'),
                    [FILTER_TYPES.SUBCATEGORY]: i18n.t('hardware.cards.history.filters.metric'),
                    [FILTER_TYPES.CANDLE_INTERVAL]: i18n.t('hardware.cards.history.filters.interval')
                }
            },
            handlers: {
                [FILTER_TYPES.CHART_TYPE]: handlers.onChartTypeChange,
                [FILTER_TYPES.CATEGORY]: handlers.onDeviceChange,
                [FILTER_TYPES.SUBCATEGORY]: handlers.onMetricChange,
                [FILTER_TYPES.TIME_RANGE]: handlers.onTimeRangeChange,
                [FILTER_TYPES.CANDLE_INTERVAL]: handlers.onCandleIntervalChange
            }
        });
        this.filtersContext.chartFilters = this.chartFilters;
    }

    disposeChartFilters(): void {
        this.#chartFiltersSetupSequence += 1;
        invalidateChartControlSync(this.filtersContext);
        this.chartFilters?.dispose();
        this.chartFilters = null;
        this.filtersContext.chartFilters = null;
    }

    async refreshChartControls(options: { range?: boolean; candles?: boolean } = {}): Promise<void> {
        await refreshChartControls(this.filtersContext, options);
    }

    updateDeviceSelector(snapshot: HardwarePageSnapshot | null = this.state.lastSnapshot): boolean {
        return updateDeviceSelector(this.filtersContext, snapshot);
    }

    syncMetricOptions(): void {
        syncMetricOptions(this.filtersContext);
    }

    refreshHeaderStats(snapshot: HardwarePageSnapshot | null = this.state.lastSnapshot): void {
        if (!snapshot) {
            return;
        }
        updateHeaderStats(this.actionsContext, snapshot);
    }

    async waitForInitialWidgets(): Promise<void> {
        await (this.#widgetManagerReadyTask ?? Promise.resolve());
    }

    handleSnapshot(snapshot: HardwarePageSnapshot): boolean {
        this.processController.handleSnapshotUpdate();
        this.refreshHeaderStats(snapshot);
        updateGpuTelemetryIndicators(this.actionsContext, snapshot);
        const selectionChanged = updateDeviceSelector(this.filtersContext, snapshot);
        renderNetworkCard(this.actionsContext);
        renderStorageCard(this.actionsContext);
        this.processController.renderProcessCard();
        const shouldWaitForWidgets = !this.renderCache.widgetManagerInitialized;
        this.#trackWidgetManagerTask(initializeWidgetManager(this.actionsContext, this.renderCache, snapshot), shouldWaitForWidgets);
        return selectionChanged;
    }

    #trackWidgetManagerTask(task: Promise<void>, shouldWaitForWidgets: boolean): void {
        if (!shouldWaitForWidgets || this.#widgetManagerReadyTask !== null) {
            void task.catch((error) => {
                errorHandler.error('HardwareRenderController', 'Hardware widget update failed', ensureError(error));
            });
            return;
        }
        const trackedTask = task.finally(() => {
            if (this.#widgetManagerReadyTask === trackedTask) {
                this.#widgetManagerReadyTask = null;
            }
        });
        this.#widgetManagerReadyTask = trackedTask;
    }

    applyPermissionGates(): void {
        const actions = new Set(this.state.webuiPermissions?.actions ?? []);
        const canTuneGpu = actions.has('HW_GPU_TUNING');
        const canViewProcesses = actions.has('HW_PROCESS_VIEW');
        const canKillProcesses = actions.has('PLUGIN_ADMIN');

        const gpuSection = this.optionalUI('#gpu-control-section');
        if (canTuneGpu && !gpuSection) {
            throw new Error('Hardware GPU controls panel missing');
        }
        if (gpuSection) {
            gpuSection.classList.toggle(CSS_CLASSES.HIDDEN, !canTuneGpu);
        }
        this.gpuController.setDomRequired(canTuneGpu);

        const processCard = this.optionalUI('#hardware-process-card');
        if (canViewProcesses && !processCard) {
            throw new Error('Hardware process panel missing');
        }
        if (processCard) {
            processCard.classList.toggle(CSS_CLASSES.HIDDEN, !canViewProcesses);
        }

        this.processController.setDomRequired(canViewProcesses);
        this.processController.setKillPermission(canViewProcesses && canKillProcesses);
        if (!canViewProcesses) {
            this.processController.reset();
        }
    }
}

export { HardwareRenderController };
export type { HardwareRenderControllerDependencies, HardwareChartFilterHandlers };
