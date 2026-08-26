/* SoAI - Hardware page interaction controller [frontend/assets/ts/pages/hardware/controllers/interactionController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { ensureError } from '@core/errors/coerce.ts';
import type { Router } from '@core/routing/router/Router.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { FILTER_TYPES } from '@features/charts/public.ts';
import { METRIC_CONFIG, type SystemInfoModal } from '@features/hardware/public.ts';
import type { HardwareActionId } from '@pages/hardware/actions.ts';
import { isCandlestickActive } from '@pages/hardware/controllers/data/effects.ts';
import type { HardwareDataController } from '@pages/hardware/controllers/dataController.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import { createHardwareInteractionHandlers, type HardwareInteractionHandlers } from '@pages/hardware/controllers/interaction/events.ts';
import type { HardwareRealtimeController } from '@pages/hardware/controllers/realtimeController.ts';
import { refreshChartControls, syncMetricOptions, updateChartFilterValue, updateDeviceSelector, updateMetricFilterOptions } from '@pages/hardware/controllers/render/events.ts';
import { renderNetworkCard, renderStorageCard, setHistoryStatus } from '@pages/hardware/controllers/render/rendering.ts';
import type { HardwareRenderController } from '@pages/hardware/controllers/renderController.ts';
import type { HardwareUi } from '@pages/hardware/dom.ts';
import { formatHistoryErrorMessage } from '@pages/hardware/mappers/mappers.ts';
import { areSameSelection, getDefaultMetricForDevice, getSelectionFromQuery, metricSupportsDevice } from '@pages/hardware/state/hardwareSelection.ts';
import type { ModuleLoggerFunctionValue } from '@pages/hardware/types.ts';
import type { MemorySwapPanelController } from '@pages/hardware/widgets/memoryswap/MemorySwapPanelController.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

type HardwareInteractionControllerDependencies = {
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
    gpuController: GpuControlManager;
    systemInfoModal: SystemInfoModal;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    realtimeController: HardwareRealtimeController;
    exportHistoryCsv: () => Promise<void>;
    persistPageControls: () => void;
    logger: ModuleLoggerFunctionValue;
    navigateToLogs: () => void;
};

class HardwareInteractionController {
    processController: ProcessTableManager;
    memorySwapController: MemorySwapPanelController;
    gpuController: GpuControlManager;
    systemInfoModal: SystemInfoModal;
    dataController: HardwareDataController;
    renderController: HardwareRenderController;
    realtimeController: HardwareRealtimeController;
    exportHistoryCsv: () => Promise<void>;
    persistPageControls: () => void;
    logger: ModuleLoggerFunctionValue;
    ui: HardwareUi | null = null;
    handlers: HardwareInteractionHandlers;

    constructor(dependencies: HardwareInteractionControllerDependencies) {
        this.processController = dependencies.processController;
        this.memorySwapController = dependencies.memorySwapController;
        this.gpuController = dependencies.gpuController;
        this.systemInfoModal = dependencies.systemInfoModal;
        this.dataController = dependencies.dataController;
        this.renderController = dependencies.renderController;
        this.realtimeController = dependencies.realtimeController;
        this.exportHistoryCsv = dependencies.exportHistoryCsv;
        this.persistPageControls = dependencies.persistPageControls;
        this.logger = dependencies.logger;
        this.handlers = createHardwareInteractionHandlers({
            processController: this.processController,
            memorySwapController: this.memorySwapController,
            gpuController: this.gpuController,
            systemInfoModal: this.systemInfoModal,
            exportHistoryCsv: this.exportHistoryCsv,
            navigateToLogs: dependencies.navigateToLogs,
            applyDeviceSelectionWithUi: (value: string | number, preferredMetric: string | null) => this.applyDeviceSelectionWithUi(value, preferredMetric),
            updateAndBootstrap: () => this.updateAndBootstrap()
        });
    }

    getChartFilterHandlers(): {
        onChartTypeChange: (value: string | number) => void;
        onDeviceChange: (value: string | number) => void;
        onMetricChange: (value: string | number) => void;
        onTimeRangeChange: (value: string | number) => void;
        onCandleIntervalChange: (value: string | number) => void;
    } {
        return {
            onChartTypeChange: (value: string | number) => {
                this.runChartFilterChange('chart type', async () => this.handleChartTypeChange(value));
            },
            onDeviceChange: (value: string | number) => {
                this.runChartFilterChange('device', async () => this.handleDeviceChange(value));
            },
            onMetricChange: (value: string | number) => {
                this.runChartFilterChange('metric', async () => this.handleMetricChange(value));
            },
            onTimeRangeChange: (value: string | number) => {
                this.runChartFilterChange('time range', async () => this.handleTimeRangeChange(value));
            },
            onCandleIntervalChange: (value: string | number) => {
                this.runChartFilterChange('candle interval', async () => this.handleCandleIntervalChange(value));
            }
        };
    }

    bindUi(ui: HardwareUi): void {
        this.ui = ui;
    }

    handleRootActionClick(event: MouseEvent, action: HardwareActionId, actionElement: HTMLElement): Promise<void> {
        return this.handlers.handleRootActionClick(event, action, actionElement);
    }

    handleRootClickMiss(event: MouseEvent): void {
        this.handlers.handleRootClickMiss(event);
    }

    handleRootActionInput(event: Event, action: HardwareActionId, actionElement: HTMLElement): void {
        this.handlers.handleRootActionInput(event, action, actionElement);
    }

    handleRootActionChange(event: Event, action: HardwareActionId, actionElement: HTMLElement): void {
        this.handlers.handleRootActionChange(event, action, actionElement);
    }

    handleRootActionKeydown(event: KeyboardEvent, action: HardwareActionId, actionElement: HTMLElement): void {
        this.handlers.handleRootActionKeydown(event, action, actionElement);
    }

    dispose(): void {
        this.ui = null;
    }

    applySelectionFromQuery(router: Pick<Router, 'getQueryParameters'>): boolean {
        const selection = getSelectionFromQuery(router, METRIC_CONFIG);
        if (!selection) return false;
        const preferredMetric = selection.metric ?? getDefaultMetricForDevice(selection.component, METRIC_CONFIG);
        if (areSameSelection(selection.selectionValue, this.dataController.state.selectedDevice, this.dataController.state.selectedMetric, preferredMetric, this.dataController.state.lastSnapshot ?? null, this.dataController.state.supportedHistoryComponents)) return false;
        this.applyDeviceSelectionWithUi(selection.selectionValue, preferredMetric);
        return true;
    }

    async handleChartTypeChange(value: string | number): Promise<void> {
        const chartType = String(value);
        this.dataController.state.chartType = chartType;
        await refreshChartControls(this.renderController.filtersContext, { range: false, candles: true });
        this.persistPageControls();
        await this.scheduleChartBootstrap({ force: true, resetView: true });
    }

    async handleDeviceChange(value: string | number): Promise<void> {
        this.applyDeviceSelectionWithUi(value, null);
        updateMetricFilterOptions(this.renderController.filtersContext, this.dataController.state.selectedMetric);
        await this.updateAndBootstrap();
        this.persistPageControls();
    }

    async handleMetricChange(value: string | number): Promise<void> {
        const target = this.dataController.getSelectedHistoryTarget();
        const metric = String(value);
        if (metricSupportsDevice(metric, target.type, METRIC_CONFIG) && this.dataController.state.selectedMetric !== metric) {
            this.dataController.state.selectedMetric = metric;
            await this.updateAndBootstrap();
            this.persistPageControls();
        } else {
            updateChartFilterValue(this.renderController.filtersContext, FILTER_TYPES.SUBCATEGORY, this.dataController.state.selectedMetric);
        }
    }

    async handleTimeRangeChange(value: string | number): Promise<void> {
        const range = Number.parseInt(String(value), 10);
        if (!isFiniteNumber(range) || range === this.dataController.state.timeRange) return;
        this.dataController.state.timeRange = range;
        this.dataController.state.lastResolvedCandlestickIntervalMs = undefined;
        await refreshChartControls(this.renderController.filtersContext);
        this.persistPageControls();
        await this.updateAndBootstrap();
    }

    async handleCandleIntervalChange(value: string | number): Promise<void> {
        const interval = Number.parseInt(String(value), 10);
        if (isFiniteNumber(interval) && interval > 0) {
            this.dataController.state.candlestickIntervalMinutes = interval;
            this.dataController.state.lastResolvedCandlestickIntervalMs = undefined;
            await refreshChartControls(this.renderController.filtersContext, { range: false, candles: true });
            if (isCandlestickActive(this.dataController.state)) {
                this.dataController.state.candlestickData = [];
                this.dataController.state.candlestickBuckets.clear();
            }
            this.persistPageControls();
            await this.updateAndBootstrap();
        } else {
            updateChartFilterValue(this.renderController.filtersContext, FILTER_TYPES.CANDLE_INTERVAL, this.dataController.state.candlestickIntervalMinutes);
        }
    }

    private updateAndBootstrap(): Promise<void> {
        return this.scheduleChartBootstrap({ force: true, resetView: true });
    }

    private runChartFilterChange(label: string, task: () => Promise<void>): void {
        task().catch((error) => {
            this.logger('warn', `Hardware ${label} filter change failed`, error);
        });
    }

    private scheduleChartBootstrap(options: { force: boolean; resetView: boolean }): Promise<void> {
        return this.realtimeController.scheduleChartBootstrap(options).catch((error) => {
            this.logger('warn', 'Hardware chart bootstrap failed', error);
        });
    }

    private applyDeviceSelectionWithUi(value: string | number, preferredMetric: string | null): void {
        try {
            this.dataController.applyDeviceSelection(value, { preferredMetric });
        } catch (error) {
            const runtimeError = ensureError(error);
            setHistoryStatus(this.renderController.actionsContext, this.renderController.renderCache, formatHistoryErrorMessage(runtimeError));
            throw runtimeError;
        }
        updateDeviceSelector(this.renderController.filtersContext, this.dataController.state.lastSnapshot);
        syncMetricOptions(this.renderController.filtersContext);
        renderStorageCard(this.renderController.actionsContext);
        renderNetworkCard(this.renderController.actionsContext);
    }
}

export { HardwareInteractionController };
export type { HardwareInteractionControllerDependencies };
