/* SoAI - Hardware feature widgets service [frontend/assets/ts/features/hardware/widgets/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { isFiniteNumber, isHTMLElement } from '@core/typeGuards.ts';
import { getCpuDevices, getGpuDevices } from '@features/hardware/models/mappers.ts';
import { WIDGET_SIZE, type WidgetSize } from '@features/hardware/widgets/constants.ts';
import { CPUWidget } from '@features/hardware/widgets/CPUWidget.ts';
import { clearWidgetContainer, renderHardwareWidgets } from '@features/hardware/widgets/dom.ts';
import { GPUWidget } from '@features/hardware/widgets/GPUWidget.ts';
import { HardwareWidgetHistoryCoordinator } from '@features/hardware/widgets/historyCoordinator.ts';
import type { HardwareData, HardwareSnapshot } from '@features/hardware/widgets/internalContracts.ts';
import { NetworkWidget } from '@features/hardware/widgets/NetworkWidget.ts';
import type { HardwareWidgetManagerOptions } from '@features/hardware/widgets/types.ts';
import { extractCpuDevices, extractGpuDevices, extractNetworkDevices, formatCpuData, formatGpuData, readFiniteNonNegativeInt, readNonEmptyString, resolveCpuName, resolveCpuSocketsCount, resolveCpuSocketIndex } from '@features/hardware/widgets/mappers.ts';

type HardwarePayload = HardwareSnapshot | HardwareData;

class HardwareWidgetManager {
    readonly #container: HTMLElement;
    readonly #size: WidgetSize;
    #cpuWidgets: Map<number, CPUWidget> = new Map();
    #gpuWidgets: Map<number, GPUWidget> = new Map();
    #networkWidgets: Map<string, NetworkWidget> = new Map();
    readonly #historyCoordinator = new HardwareWidgetHistoryCoordinator();
    #initialized = false;
    #operationPromise: Promise<void> | null = null;
    #pendingSnapshot: HardwarePayload | null = null;
    #lifecycleVersion = 0;

    constructor(options: HardwareWidgetManagerOptions) {
        if (!isHTMLElement(options.container)) {
            throw new Error('HardwareWidgetManager requires a valid container element');
        }
        this.#container = options.container;
        this.#size = this.#resolveWidgetSize(options.size);
    }

    async initialize(snapshot: HardwarePayload): Promise<void> {
        if (this.#initialized) {
            await this.handleSnapshotUpdate(snapshot);
            return;
        }
        await this.#runExclusive(snapshot, (lifecycleVersion) => this.#initializeWidgets(snapshot, lifecycleVersion));
    }

    async handleSnapshotUpdate(snapshot: HardwarePayload): Promise<void> {
        if (!this.#initialized) {
            return;
        }
        if (this.#operationPromise) {
            this.#pendingSnapshot = snapshot;
            await this.#operationPromise;
            return;
        }
        const hardware = this.#resolveHardwareSnapshot(snapshot);
        if (this.#requiresTopologyRebuild(hardware)) {
            await this.#runExclusive(snapshot, (lifecycleVersion) => this.#initializeWidgets(snapshot, lifecycleVersion));
            return;
        }
        this.#updateExistingWidgets(hardware);
    }

    destroy(): void {
        this.#lifecycleVersion += 1;
        this.#pendingSnapshot = null;
        this.#operationPromise = null;
        this.#historyCoordinator.abortHistoryFetch();
        this.#destroyWidgets();
        this.#initialized = false;
    }

    get widgetCount(): number {
        return this.#cpuWidgets.size + this.#gpuWidgets.size + this.#networkWidgets.size;
    }

    get cpuWidgetCount(): number {
        return this.#cpuWidgets.size;
    }

    get gpuWidgetCount(): number {
        return this.#gpuWidgets.size;
    }

    get networkWidgetCount(): number {
        return this.#networkWidgets.size;
    }

    async #runExclusive(snapshot: HardwarePayload, operation: (lifecycleVersion: number) => Promise<void>): Promise<void> {
        if (this.#operationPromise) {
            this.#pendingSnapshot = snapshot;
            await this.#operationPromise;
            return;
        }
        const lifecycleVersion = this.#lifecycleVersion;
        this.#pendingSnapshot = null;
        const operationPromise = operation(lifecycleVersion);
        this.#operationPromise = operationPromise;
        let operationCompleted = false;
        try {
            await operationPromise;
            operationCompleted = true;
        } finally {
            if (!operationCompleted && this.#operationPromise === operationPromise) {
                this.#pendingSnapshot = null;
            }
            if (this.#operationPromise === operationPromise) {
                this.#operationPromise = null;
            }
        }
        if (lifecycleVersion === this.#lifecycleVersion) {
            await this.#replayPendingSnapshot();
        }
    }

    async #initializeWidgets(snapshot: HardwarePayload, lifecycleVersion: number): Promise<void> {
        this.#historyCoordinator.abortHistoryFetch();
        this.#destroyWidgets();
        const hardware = this.#resolveHardwareSnapshot(snapshot);
        const cpuDevices = extractCpuDevices(hardware);
        const gpuDevices = extractGpuDevices(hardware);
        const networkDevices = extractNetworkDevices(hardware);
        const rendered = await renderHardwareWidgets({
            container: this.#container,
            size: this.#size,
            cpuDevices,
            gpuDevices,
            networkDevices,
            shouldCommit: () => lifecycleVersion === this.#lifecycleVersion
        });
        if (lifecycleVersion !== this.#lifecycleVersion) {
            return;
        }
        this.#cpuWidgets = rendered.cpuWidgets;
        this.#gpuWidgets = rendered.gpuWidgets;
        this.#networkWidgets = rendered.networkWidgets;
        this.#initialized = true;
        await this.#historyCoordinator.fetchHistoricalData(cpuDevices, gpuDevices, networkDevices, snapshot, {
            cpuWidgets: this.#cpuWidgets,
            gpuWidgets: this.#gpuWidgets,
            networkWidgets: this.#networkWidgets
        });
    }

    #updateExistingWidgets(hardware: HardwarePayload): void {
        const normalizedMemoryData = hardware.memory ?? {};
        const cpuArray = getCpuDevices(hardware);
        const sockets = resolveCpuSocketsCount(cpuArray);
        for (const [index, cpu] of cpuArray.entries()) {
            const socketIndex = resolveCpuSocketIndex(cpu, index);
            const widget = this.#cpuWidgets.get(socketIndex);
            if (widget) {
                widget.updateConfig({
                    name: resolveCpuName(cpu),
                    sockets,
                    cores: readFiniteNonNegativeInt(cpu.physicalCores) ?? 0,
                    threads: readFiniteNonNegativeInt(cpu.logicalCores) ?? 0
                });
                widget.updateData(formatCpuData(cpu, normalizedMemoryData));
            }
        }
        for (const [index, gpuData] of getGpuDevices(hardware).entries()) {
            const resolvedIndex = isFiniteNumber(gpuData.index) ? Math.max(0, Math.floor(gpuData.index)) : index;
            const widget = this.#gpuWidgets.get(resolvedIndex);
            if (widget) {
                widget.updateConfig({ name: readNonEmptyString(gpuData.name) ?? i18n.t('hardware.components.gpu') });
                widget.updateData(formatGpuData(gpuData));
            }
        }
        for (const network of extractNetworkDevices(hardware)) {
            const widget = this.#networkWidgets.get(network.deviceId);
            if (widget) {
                widget.updateConfig({ index: network.index, name: network.name });
                widget.updateData(network.data);
            }
        }
    }

    #destroyWidgets(): void {
        this.#cpuWidgets.forEach((widget) => widget.destroy());
        this.#gpuWidgets.forEach((widget) => widget.destroy());
        this.#networkWidgets.forEach((widget) => widget.destroy());
        this.#cpuWidgets.clear();
        this.#gpuWidgets.clear();
        this.#networkWidgets.clear();
        clearWidgetContainer(this.#container);
    }

    #resolveHardwareSnapshot(snapshot: HardwarePayload): HardwarePayload {
        return snapshot;
    }

    async #replayPendingSnapshot(): Promise<void> {
        const pending = this.#pendingSnapshot;
        this.#pendingSnapshot = null;
        if (pending) {
            await this.handleSnapshotUpdate(pending);
        }
    }

    #requiresTopologyRebuild(hardware: HardwarePayload): boolean {
        return this.#cpuKeys(hardware) !== [...this.#cpuWidgets.keys()].join('|') || this.#gpuKeys(hardware) !== [...this.#gpuWidgets.keys()].join('|') || this.#networkKeys(hardware) !== [...this.#networkWidgets.keys()].join('|');
    }

    #cpuKeys(hardware: HardwarePayload): string {
        return extractCpuDevices(hardware)
            .map((device) => device.socketIndex)
            .join('|');
    }

    #gpuKeys(hardware: HardwarePayload): string {
        return extractGpuDevices(hardware)
            .map((device) => device.index)
            .join('|');
    }

    #networkKeys(hardware: HardwarePayload): string {
        return extractNetworkDevices(hardware)
            .map((device) => device.deviceId)
            .join('|');
    }

    #resolveWidgetSize(size: WidgetSize | undefined): WidgetSize {
        if (!size) {
            return WIDGET_SIZE;
        }
        return isFiniteNumber(size.WIDTH) && isFiniteNumber(size.HEIGHT) ? size : WIDGET_SIZE;
    }
}

export { HardwareWidgetManager };
