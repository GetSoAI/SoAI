/* SoAI - Hardware feature widgets DOM contracts [frontend/assets/ts/features/hardware/widgets/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { dom } from '@core/dom/dom.ts';
import { getDocument } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { WIDGET_SIZE, type WidgetSize } from '@features/hardware/widgets/constants.ts';
import { CPUWidget } from '@features/hardware/widgets/CPUWidget.ts';
import { GPUWidget } from '@features/hardware/widgets/GPUWidget.ts';
import { NetworkWidget } from '@features/hardware/widgets/NetworkWidget.ts';
import type { CPUDevice, GPUDevice, NetworkDevice } from '@features/hardware/widgets/internalContracts.ts';

interface RenderHardwareWidgetsParameters {
    container: HTMLElement;
    size: WidgetSize;
    cpuDevices: ReadonlyArray<CPUDevice>;
    gpuDevices: ReadonlyArray<GPUDevice>;
    networkDevices: ReadonlyArray<NetworkDevice>;
    shouldCommit: () => boolean;
}

interface HardwareWidgetRenderResult {
    cpuWidgets: Map<number, CPUWidget>;
    gpuWidgets: Map<number, GPUWidget>;
    networkWidgets: Map<string, NetworkWidget>;
}

const isValidWidgetSize = (value: number): boolean => isFiniteNumber(value);

const clearWidgetContainer = (container: HTMLElement): void => {
    dom.setText(container, '');
};

const resolveWidgetSize = (size: WidgetSize): WidgetSize => (isValidWidgetSize(size['WIDTH']) && isValidWidgetSize(size['HEIGHT']) ? size : WIDGET_SIZE);

const cleanupRenderedWidgets = (rendered: HardwareWidgetRenderResult): void => {
    rendered.cpuWidgets.forEach((widget) => widget.destroy());
    rendered.gpuWidgets.forEach((widget) => widget.destroy());
    rendered.networkWidgets.forEach((widget) => widget.destroy());
};

const renderHardwareWidgets = async (parameters: RenderHardwareWidgetsParameters): Promise<HardwareWidgetRenderResult> => {
    const { container, size, cpuDevices, gpuDevices, networkDevices, shouldCommit } = parameters;
    const hostDocument = getDocument();
    const resolvedSize = resolveWidgetSize(size);
    const fragment = hostDocument.createDocumentFragment();
    const cpuWidgets = new Map<number, CPUWidget>();
    const gpuWidgets = new Map<number, GPUWidget>();
    const networkWidgets = new Map<string, NetworkWidget>();
    let widgetIndex = 0;

    try {
        for (const cpu of cpuDevices) {
            const widgetContainer = hostDocument.createElement('div');
            widgetContainer.classList.add(resolveCheckerboardClass(widgetIndex));
            widgetIndex += 1;
            fragment.append(widgetContainer);

            const widget = new CPUWidget({
                container: widgetContainer,
                config: {
                    id: `cpu-widget-${cpu.socketIndex}`,
                    socketIndex: cpu.socketIndex,
                    name: cpu.name,
                    sockets: cpu.sockets,
                    cores: cpu.cores,
                    threads: cpu.threads,
                    data: cpu.data
                },
                size: resolvedSize
            });

            await widget.initialize();
            cpuWidgets.set(cpu.socketIndex, widget);
        }

        for (const gpu of gpuDevices) {
            const widgetContainer = hostDocument.createElement('div');
            widgetContainer.classList.add(resolveCheckerboardClass(widgetIndex));
            widgetIndex += 1;
            fragment.append(widgetContainer);

            const widget = new GPUWidget({
                container: widgetContainer,
                config: {
                    id: `gpu-widget-${gpu.index}`,
                    index: gpu.index,
                    name: gpu.name,
                    data: gpu.data
                },
                size: resolvedSize
            });

            await widget.initialize();
            gpuWidgets.set(gpu.index, widget);
        }

        for (const network of networkDevices) {
            const widgetContainer = hostDocument.createElement('div');
            widgetContainer.classList.add(resolveCheckerboardClass(widgetIndex));
            widgetIndex += 1;
            fragment.append(widgetContainer);

            const widget = new NetworkWidget({
                container: widgetContainer,
                config: {
                    id: `network-widget-${network.index}`,
                    deviceId: network.deviceId,
                    index: network.index,
                    name: network.name,
                    data: network.data
                },
                size: resolvedSize
            });

            await widget.initialize();
            networkWidgets.set(network.deviceId, widget);
        }
    } catch (error) {
        cleanupRenderedWidgets({ cpuWidgets, gpuWidgets, networkWidgets });
        throw ensureError(error);
    }

    if (!shouldCommit()) {
        cleanupRenderedWidgets({ cpuWidgets, gpuWidgets, networkWidgets });
        return { cpuWidgets: new Map(), gpuWidgets: new Map(), networkWidgets: new Map() };
    }

    clearWidgetContainer(container);
    container.append(fragment);

    return { cpuWidgets, gpuWidgets, networkWidgets };
};

export { clearWidgetContainer, renderHardwareWidgets };
