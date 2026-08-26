/* SoAI - Hardware page controller rendering [frontend/assets/ts/pages/hardware/controllers/render/rendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementOptions } from '@core/dom/dom.ts';
import { isArray, isFiniteNumber, isFunction, isHTMLElement } from '@core/typeGuards.ts';
import { HistoryChartRuntime } from '@features/charts/public.ts';
import { getGpuDevices, HardwareWidgetManager } from '@features/hardware/public.ts';
import { HIDDEN } from '@pages/hardware/contracts/hardwarePageSupport.ts';
import type { GpuControlManager } from '@pages/hardware/controllers/gpucontrol/GpuControlManager.ts';
import type { GpuControlTelemetry } from '@pages/hardware/controllers/gpucontrol/gpuControlTelemetryController.ts';
import { resolveGpuMetricFromDevice } from '@pages/hardware/realtime/hardwarerealtimemetricresolvers/actions.ts';
import type { NetworkCardRenderer } from '@pages/hardware/rendering/cards/NetworkCardRenderer.ts';
import type { StorageCardRenderer } from '@pages/hardware/rendering/cards/StorageCardRenderer.ts';
import type { HardwarePageState } from '@pages/hardware/state/state.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import { buildHardwareHeaderStats, formatHardwareTotalUptime } from '@pages/hardware/widgets/hardwareHeaderStats.ts';
import type { ProcessTableManager } from '@pages/hardware/widgets/processes/service.ts';

type HardwareRenderActionsContext = {
    state: HardwarePageState;
    chartRuntime: HistoryChartRuntime;
    optionalUI: (selector: string, context?: Element | null) => Element | null;
    requireHTMLElement: (id: string) => HTMLElement;
    requireUI: (selector: string, context?: Element | null) => Element;
    createElement: (tag: string, attrs?: ElementOptions) => Element;
    updateText: (element: Element, text: string) => void;
    networkCardRenderer: NetworkCardRenderer;
    storageCardRenderer: StorageCardRenderer;
    processController: ProcessTableManager;
    gpuController: GpuControlManager;
};

type HardwareRenderCache = {
    historyStatusElement: HTMLElement | null;
    widgetManager: HardwareWidgetManager | null;
    widgetManagerInitialized: boolean;
};

const renderNetworkCard = (context: HardwareRenderActionsContext): void => {
    context.networkCardRenderer.render(context.state.lastSnapshot ?? null);
};

const renderStorageCard = (context: HardwareRenderActionsContext): void => {
    context.storageCardRenderer.render(context.state.lastSnapshot ?? null);
};

const setHistoryStatus = (context: HardwareRenderActionsContext, cache: HardwareRenderCache, message: string | null = null, tone: string | null = null): void => {
    const element = resolveHistoryStatusElement(context, cache);
    if (!message) {
        element.textContent = '';
        element.classList.add(HIDDEN);
        element.removeAttribute('data-tone');
        element.removeAttribute('data-overlay');
        return;
    }
    element.textContent = message;
    element.classList.remove(HIDDEN);
    if (tone) {
        element.dataset['tone'] = tone;
    } else {
        element.removeAttribute('data-tone');
    }
    if (!(isArray(context.state.historyData) && context.state.historyData.length) && !(isArray(context.state.candlestickData) && context.state.candlestickData.length)) {
        element.dataset['overlay'] = 'true';
    } else {
        element.removeAttribute('data-overlay');
    }
};

const resetHistoryStatusElement = (cache: HardwareRenderCache): void => {
    cache.historyStatusElement = null;
};

const updateHeaderStats = (context: HardwareRenderActionsContext, snapshot: HardwarePageSnapshot): void => {
    const capabilities = snapshot.capabilities;
    const values = buildHardwareHeaderStats({
        snapshot,
        capabilities,
        currentMetrics: context.state.currentMetrics,
        processCount: context.processController.getProcessCount()
    });
    const processElement = context.optionalUI('hardware-stat-processes');
    if (processElement) context.updateText(processElement, values.processes);
    const cpuElement = context.optionalUI('hardware-stat-cpu');
    if (cpuElement) context.updateText(cpuElement, values.cpu);
    const totalRamElement = context.optionalUI('hardware-stat-total-ram');
    if (totalRamElement) context.updateText(totalRamElement, values.totalRam);
    const totalVramElement = context.optionalUI('hardware-stat-total-vram');
    if (totalVramElement) context.updateText(totalVramElement, values.totalVram);
    const totalMemoryElement = context.optionalUI('hardware-stat-total-memory');
    if (totalMemoryElement) context.updateText(totalMemoryElement, values.totalMemory);
    const platformElement = context.optionalUI('hardware-stat-platform');
    if (platformElement) context.updateText(platformElement, values.platform);
    const systemUptimeElement = context.optionalUI('systemUptime');
    if (systemUptimeElement) context.updateText(systemUptimeElement, values.systemUptime);
    const totalUptimeElement = context.optionalUI('totalUptime');
    if (totalUptimeElement) context.updateText(totalUptimeElement, values.totalUptime);
};

const handleMetricsUpdate = (context: HardwareRenderActionsContext, value: import('@pages/hardware/types.ts').MetricsData | null): void => {
    if (!value) return;
    const element = context.optionalUI('totalUptime');
    if (element) context.updateText(element, formatHardwareTotalUptime(value));
};

const updateGpuTelemetryIndicators = (context: HardwareRenderActionsContext, snapshot: HardwarePageSnapshot): void => {
    const devices = getGpuDevices(snapshot);
    if (!devices.length) {
        context.gpuController.setGpuTelemetryByDeviceId({});
        return;
    }
    const map: Record<string, GpuControlTelemetry> = {};
    devices.forEach((gpu) => {
        const id = gpu.deviceId;
        if (typeof id !== 'string' || !id) {
            throw new TypeError('gpu.deviceId is required');
        }
        const chartOhlc = context.chartRuntime.getOhlc();
        const temperatureCelsius = resolveGpuMetricFromDevice('temperature', gpu, chartOhlc);
        const coreUtilizationPercent = resolveGpuMetricFromDevice('utilization', gpu, chartOhlc);
        const memoryUtilizationPercent = resolveGpuMetricFromDevice('percent_used', gpu, chartOhlc);
        const powerDrawWatts = resolveGpuMetricFromDevice('power_draw_watts', gpu, chartOhlc);
        const powerLimitWatts = resolveGpuMetricFromDevice('power_limit_watts', gpu, chartOhlc);
        if (isFiniteNumber(temperatureCelsius) || isFiniteNumber(coreUtilizationPercent) || isFiniteNumber(memoryUtilizationPercent) || isFiniteNumber(powerDrawWatts) || isFiniteNumber(powerLimitWatts)) {
            map[id] = { temperatureCelsius, coreUtilizationPercent, memoryUtilizationPercent, powerDrawWatts, powerLimitWatts };
        }
    });
    context.gpuController.setGpuTelemetryByDeviceId(map);
};

const initializeWidgetManager = async (context: HardwareRenderActionsContext, cache: HardwareRenderCache, snapshot: HardwarePageSnapshot): Promise<void> => {
    if (cache.widgetManagerInitialized) {
        const manager = cache.widgetManager;
        if (manager && isFunction(manager.handleSnapshotUpdate)) {
            await manager.handleSnapshotUpdate(snapshot);
        }
        return;
    }
    cache.widgetManagerInitialized = true;
    const container = context.requireHTMLElement('hardwareWidgetsContainer');
    const existing = cache.widgetManager;
    if (existing && isFunction(existing.destroy)) {
        existing.destroy();
    }
    cache.widgetManager = new HardwareWidgetManager({ container });
    await cache.widgetManager.initialize(snapshot);
};

const destroyWidgetManager = (cache: HardwareRenderCache): void => {
    if (cache.widgetManager && isFunction(cache.widgetManager.destroy)) {
        cache.widgetManager.destroy();
    }
    cache.widgetManager = null;
    cache.widgetManagerInitialized = false;
};

const resolveHistoryStatusElement = (context: HardwareRenderActionsContext, cache: HardwareRenderCache): HTMLElement => {
    if (cache.historyStatusElement?.isConnected) return cache.historyStatusElement;
    const container = context.requireUI('hardwareHistoryChart');
    const resolved = context.optionalUI('.history-chart-status', container);
    let element = resolved instanceof HTMLElement ? resolved : null;
    if (!element) {
        const created = context.createElement('p', {
            className: `history-chart-status ${HIDDEN}`
        });
        if (!isHTMLElement(created)) {
            throw new Error('History status element must be an HTML element');
        }
        element = created;
        container.appendChild(created);
    }
    cache.historyStatusElement = element;
    return element;
};

export { destroyWidgetManager, handleMetricsUpdate, initializeWidgetManager, renderNetworkCard, renderStorageCard, resetHistoryStatusElement, setHistoryStatus, updateGpuTelemetryIndicators, updateHeaderStats };
export type { HardwareRenderActionsContext, HardwareRenderCache };
