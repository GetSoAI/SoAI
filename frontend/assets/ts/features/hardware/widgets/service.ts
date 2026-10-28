/* SoAI - Hardware feature widgets service [frontend/assets/ts/features/hardware/widgets/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveHardwareObservation } from '@core/api/contracts/hardwareComponentObservationContracts.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFiniteNumber, isHTMLElement } from '@core/typeGuards.ts';
import { WIDGET_SIZE, type WidgetSize } from '@features/hardware/widgets/constants.ts';
import type { CPUWidget } from '@features/hardware/widgets/CPUWidget.ts';
import { commitWidgetOrder, createCpuWidget, createGpuWidget, createNetworkWidget } from '@features/hardware/widgets/dom.ts';
import type { GPUWidget } from '@features/hardware/widgets/GPUWidget.ts';
import { HardwareWidgetHistoryCoordinator } from '@features/hardware/widgets/historyCoordinator.ts';
import type { CPUDevice, GPUDevice, HardwareData, HardwareSnapshot, NetworkDevice } from '@features/hardware/widgets/internalContracts.ts';
import type { NetworkWidget } from '@features/hardware/widgets/NetworkWidget.ts';
import type { HardwareWidgetManagerOptions } from '@features/hardware/widgets/types.ts';
import { extractCpuDevices, extractGpuDevices, extractNetworkDevices, resolveGpuWidgetKey } from '@features/hardware/widgets/mappers.ts';

type HardwarePayload = HardwareSnapshot | HardwareData;

interface ManagedHardwareWidget {
    readonly container: HTMLElement;
    destroy(): void;
}

interface HardwareWidgetDevices {
    cpu: CPUDevice[];
    gpu: GPUDevice[];
    network: NetworkDevice[];
}

const extractWidgetDevices = (hardware: HardwarePayload): HardwareWidgetDevices => ({
    cpu: extractCpuDevices(hardware),
    gpu: extractGpuDevices(hardware),
    network: extractNetworkDevices(hardware)
});

const serializeTopologyKeys = <TKey>(keys: Iterable<TKey>): string =>
    JSON.stringify(
        [...new Set(keys)].sort((first, second) => {
            const firstKey = String(first);
            const secondKey = String(second);
            return firstKey < secondKey ? -1 : firstKey > secondKey ? 1 : 0;
        })
    );

class HardwareWidgetManager {
    readonly #container: HTMLElement;
    readonly #size: WidgetSize;
    #cpuWidgets: Map<number, CPUWidget> = new Map();
    #gpuWidgets: Map<string | number, GPUWidget> = new Map();
    #networkWidgets: Map<string, NetworkWidget> = new Map();
    readonly #historyCoordinator = new HardwareWidgetHistoryCoordinator();
    #initialized = false;
    #operationPromise: Promise<void> | null = null;
    #pendingSnapshot: HardwarePayload | null = null;
    #lifecycleVersion = 0;
    #networkWidgetSequence = 0;
    #gpuWidgetSequence = 0;

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
        await this.#runExclusive(snapshot, (lifecycleVersion) => this.#reconcileWidgets(snapshot, lifecycleVersion));
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
        const devices = extractWidgetDevices(snapshot);
        if (this.#hasTopologyChanged(devices)) {
            await this.#runExclusive(snapshot, (lifecycleVersion) => this.#reconcileWidgets(snapshot, lifecycleVersion));
            return;
        }
        this.#applyDevices(devices, snapshot);
    }

    destroy(): void {
        this.#lifecycleVersion += 1;
        this.#pendingSnapshot = null;
        this.#operationPromise = null;
        this.#historyCoordinator.abortHistoryFetch();
        this.#destroyWidgets();
        this.#initialized = false;
    }

    get container(): HTMLElement {
        return this.#container;
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

    async #reconcileWidgets(snapshot: HardwarePayload, lifecycleVersion: number): Promise<void> {
        const devices = extractWidgetDevices(snapshot);
        const created = new Set<ManagedHardwareWidget>();
        let cpuWidgets: Map<number, CPUWidget>;
        let gpuWidgets: Map<string | number, GPUWidget>;
        let networkWidgets: Map<string, NetworkWidget>;
        try {
            cpuWidgets = await this.#collectWidgets(
                devices.cpu,
                (cpu) => cpu.socketIndex,
                this.#cpuWidgets,
                (cpu) => createCpuWidget(cpu, this.#size),
                created
            );
            gpuWidgets = await this.#collectWidgets(devices.gpu, resolveGpuWidgetKey, this.#gpuWidgets, (gpu) => createGpuWidget(gpu, this.#size, this.#nextGpuWidgetId()), created);
            networkWidgets = await this.#collectWidgets(
                devices.network,
                (network) => network.deviceId,
                this.#networkWidgets,
                (network) => createNetworkWidget(network, this.#size, this.#nextNetworkWidgetId()),
                created
            );
        } catch (error) {
            created.forEach((widget) => widget.destroy());
            throw ensureError(error);
        }
        if (lifecycleVersion !== this.#lifecycleVersion) {
            created.forEach((widget) => widget.destroy());
            return;
        }
        this.#historyCoordinator.abortHistoryFetch();
        this.#retireRemovedWidgets(this.#cpuWidgets, cpuWidgets);
        this.#retireRemovedWidgets(this.#gpuWidgets, gpuWidgets);
        this.#retireRemovedWidgets(this.#networkWidgets, networkWidgets);
        this.#cpuWidgets = cpuWidgets;
        this.#gpuWidgets = gpuWidgets;
        this.#networkWidgets = networkWidgets;
        commitWidgetOrder(
            this.#container,
            [...cpuWidgets.values(), ...gpuWidgets.values(), ...networkWidgets.values()].map((widget) => widget.container)
        );
        this.#applyDevices(devices, snapshot);
        this.#initialized = true;
        await this.#historyCoordinator.fetchHistoricalData(devices.cpu, devices.gpu, devices.network, snapshot, {
            cpuWidgets: this.#cpuWidgets,
            gpuWidgets: this.#gpuWidgets,
            networkWidgets: this.#networkWidgets
        });
    }

    async #collectWidgets<TKey, TDevice, TWidget extends ManagedHardwareWidget>(devices: ReadonlyArray<TDevice>, resolveKey: (device: TDevice) => TKey, current: ReadonlyMap<TKey, TWidget>, create: (device: TDevice) => Promise<TWidget>, created: Set<ManagedHardwareWidget>): Promise<Map<TKey, TWidget>> {
        const active = new Set(devices.map(resolveKey));
        const next = new Map([...current].filter(([key]) => active.has(key)));
        for (const device of devices) {
            const key = resolveKey(device);
            if (next.has(key)) {
                continue;
            }
            const widget = await create(device);
            created.add(widget);
            next.set(key, widget);
        }
        return next;
    }

    #retireRemovedWidgets<TKey, TWidget extends ManagedHardwareWidget>(current: ReadonlyMap<TKey, TWidget>, next: ReadonlyMap<TKey, TWidget>): void {
        for (const [key, widget] of current) {
            if (!next.has(key)) {
                widget.destroy();
                widget.container.remove();
            }
        }
    }

    #applyDevices(devices: HardwareWidgetDevices, snapshot: HardwarePayload): void {
        for (const cpu of devices.cpu) {
            const widget = this.#cpuWidgets.get(cpu.socketIndex);
            if (widget) {
                const observation = resolveHardwareObservation(snapshot, 'cpus') ?? resolveHardwareObservation(snapshot, 'cpu');
                widget.updateMonitoring({ core: observation, power: observation, temperature: observation, ram: resolveHardwareObservation(snapshot, 'memory') }, snapshot.timestampMs, snapshot.capabilities?.monitoringIntervalMs ?? 1000);
                widget.updateConfig({ name: cpu.name, sockets: cpu.sockets, cores: cpu.cores, threads: cpu.threads });
                widget.updateData(cpu.data);
            }
        }
        for (const gpu of devices.gpu) {
            const widget = this.#gpuWidgets.get(resolveGpuWidgetKey(gpu));
            if (widget) {
                const observation = resolveHardwareObservation(snapshot, 'gpu', gpu.data.telemetryObservation);
                widget.updateMonitoring({ core: observation, power: observation, temperature: observation, vram: resolveHardwareObservation(snapshot, 'gpu', gpu.data.memoryTotalObservation) }, snapshot.timestampMs, snapshot.capabilities?.monitoringIntervalMs ?? 1000);
                widget.updateConfig({ index: gpu.index, name: gpu.name });
                widget.updateData(gpu.data);
            }
        }
        if (devices.network.length === 0) return;
        const networkIndices = new Map<string, number>();
        for (const deviceId of this.#networkWidgets.keys()) {
            networkIndices.set(deviceId, networkIndices.size);
        }
        for (const network of devices.network) {
            const widget = this.#networkWidgets.get(network.deviceId);
            if (widget) {
                const observation = resolveHardwareObservation(snapshot, 'network_speed');
                widget.updateMonitoring({ download: observation, upload: observation }, snapshot.timestampMs, snapshot.capabilities?.monitoringIntervalMs ?? 1000);
                widget.updateConfig({ index: networkIndices.get(network.deviceId), name: network.name });
                widget.updateData(network.data);
            }
        }
    }

    #destroyWidgets(): void {
        for (const widget of [...this.#cpuWidgets.values(), ...this.#gpuWidgets.values(), ...this.#networkWidgets.values()]) {
            widget.destroy();
            widget.container.remove();
        }
        this.#cpuWidgets.clear();
        this.#gpuWidgets.clear();
        this.#networkWidgets.clear();
    }

    async #replayPendingSnapshot(): Promise<void> {
        const pending = this.#pendingSnapshot;
        this.#pendingSnapshot = null;
        if (pending) {
            await this.handleSnapshotUpdate(pending);
        }
    }

    #hasTopologyChanged(devices: HardwareWidgetDevices): boolean {
        return serializeTopologyKeys(devices.cpu.map((cpu) => cpu.socketIndex)) !== serializeTopologyKeys(this.#cpuWidgets.keys()) || serializeTopologyKeys(devices.gpu.map(resolveGpuWidgetKey)) !== serializeTopologyKeys(this.#gpuWidgets.keys()) || serializeTopologyKeys(devices.network.map((network) => network.deviceId)) !== serializeTopologyKeys(this.#networkWidgets.keys());
    }

    #nextGpuWidgetId(): string {
        this.#gpuWidgetSequence += 1;
        return `gpu-widget-${this.#gpuWidgetSequence}`;
    }

    #nextNetworkWidgetId(): string {
        this.#networkWidgetSequence += 1;
        return `network-widget-${this.#networkWidgetSequence}`;
    }

    #resolveWidgetSize(size: WidgetSize | undefined): WidgetSize {
        if (!size) {
            return WIDGET_SIZE;
        }
        return isFiniteNumber(size.WIDTH) && isFiniteNumber(size.HEIGHT) ? size : WIDGET_SIZE;
    }
}

export { HardwareWidgetManager };
