/* SoAI - Hardware feature history coordinator [frontend/assets/ts/features/hardware/widgets/historyCoordinator.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { fetchWidgetHistory, getHistoryWindow } from '@features/hardware/widgets/effects.ts';
import { serverEpochMs } from '@core/time/clock.ts';
import type { CPUDevice, GPUDevice, HardwareData, HardwareSnapshot, HistoryResponse, NetworkDevice, WidgetHistoryRequest, WidgetHistoryWindow } from '@features/hardware/widgets/internalContracts.ts';
import type { CPUWidget } from '@features/hardware/widgets/CPUWidget.ts';
import type { GPUWidget } from '@features/hardware/widgets/GPUWidget.ts';
import type { NetworkWidget } from '@features/hardware/widgets/NetworkWidget.ts';

type HardwarePayload = HardwareSnapshot | HardwareData;

interface HardwareHistoryWidgets {
    cpuWidgets: Map<number, CPUWidget>;
    gpuWidgets: Map<number, GPUWidget>;
    networkWidgets: Map<string, NetworkWidget>;
}

class HardwareWidgetHistoryCoordinator {
    #historyAbortController: AbortController | null = null;

    async fetchHistoricalData(cpuDevices: CPUDevice[], gpuDevices: GPUDevice[], networkDevices: NetworkDevice[], snapshot: HardwarePayload, widgets: HardwareHistoryWidgets): Promise<void> {
        this.abortHistoryFetch();
        const historyWindow = getHistoryWindow(snapshot);
        if (!historyWindow) {
            return;
        }
        const controller = new AbortController();
        this.#historyAbortController = controller;
        const endTsMs = Math.round(serverEpochMs());
        const startTsMs = endTsMs - historyWindow.durationMs - historyWindow.requestPaddingMs;
        const requests: Promise<void>[] = [];
        this.#queueCpuHistoryRequest(requests, cpuDevices, historyWindow, startTsMs, endTsMs, controller.signal, widgets.cpuWidgets);
        this.#queueGpuHistoryRequests(requests, gpuDevices, historyWindow, startTsMs, endTsMs, controller.signal, widgets.gpuWidgets);
        this.#queueNetworkHistoryRequests(requests, networkDevices, historyWindow, startTsMs, endTsMs, controller.signal, widgets.networkWidgets);
        try {
            await Promise.allSettled(requests);
        } finally {
            if (this.#historyAbortController === controller) {
                this.#historyAbortController = null;
            }
        }
    }

    abortHistoryFetch(): void {
        this.#historyAbortController?.abort();
        this.#historyAbortController = null;
    }

    #queueCpuHistoryRequest(requests: Promise<void>[], cpuDevices: CPUDevice[], window: WidgetHistoryWindow, startTsMs: number, endTsMs: number, signal: AbortSignal, cpuWidgets: Map<number, CPUWidget>): void {
        if (cpuDevices.length === 0) {
            return;
        }
        requests.push(
            this.#fetchHistory(this.#buildHistoryRequest('cpu', null, window, startTsMs, endTsMs, signal)).then((data) => {
                if (data && !signal.aborted) {
                    cpuWidgets.forEach((widget) => widget.processHistoricalData(data));
                }
            })
        );
    }

    #queueGpuHistoryRequests(requests: Promise<void>[], gpuDevices: GPUDevice[], window: WidgetHistoryWindow, startTsMs: number, endTsMs: number, signal: AbortSignal, gpuWidgets: Map<number, GPUWidget>): void {
        for (const gpu of gpuDevices) {
            requests.push(
                this.#fetchHistory(this.#buildHistoryRequest('gpu', gpu.index, window, startTsMs, endTsMs, signal)).then((data) => {
                    const widget = gpuWidgets.get(gpu.index);
                    if (data && widget && !signal.aborted) {
                        widget.processHistoricalData(data);
                    }
                })
            );
        }
    }

    #queueNetworkHistoryRequests(requests: Promise<void>[], networkDevices: NetworkDevice[], window: WidgetHistoryWindow, startTsMs: number, endTsMs: number, signal: AbortSignal, networkWidgets: Map<string, NetworkWidget>): void {
        for (const network of networkDevices) {
            requests.push(
                this.#fetchHistory(this.#buildHistoryRequest('network', null, window, startTsMs, endTsMs, signal, network.deviceId)).then((data) => {
                    const widget = networkWidgets.get(network.deviceId);
                    if (data && widget && !signal.aborted) {
                        widget.processHistoricalData(data);
                    }
                })
            );
        }
    }

    async #fetchHistory(request: WidgetHistoryRequest): Promise<HistoryResponse | null> {
        return await fetchWidgetHistory(request);
    }

    #buildHistoryRequest(component: string, gpuIndex: number | null, window: WidgetHistoryWindow, startTsMs: number, endTsMs: number, signal: AbortSignal, identifier?: string): WidgetHistoryRequest {
        const request: WidgetHistoryRequest = { component, gpuIndex, startTsMs: startTsMs, endTsMs: endTsMs, points: window.points, signal };
        if (identifier) {
            request.identifier = identifier;
        }
        return request;
    }
}

export { HardwareWidgetHistoryCoordinator };
