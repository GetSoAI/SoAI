/* SoAI - Hardware feature widgets DOM contracts [frontend/assets/ts/features/hardware/widgets/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { invertCheckerboardClass, resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { getDocument } from '@core/environment/public.ts';
import { ensureError } from '@core/errors/coerce.ts';
import { isFiniteNumber } from '@core/typeGuards.ts';
import { WIDGET_SIZE, type WidgetSize } from '@features/hardware/widgets/constants.ts';
import { CPUWidget } from '@features/hardware/widgets/CPUWidget.ts';
import { GPUWidget } from '@features/hardware/widgets/GPUWidget.ts';
import { NetworkWidget } from '@features/hardware/widgets/NetworkWidget.ts';
import type { CPUDevice, GPUDevice, NetworkDevice } from '@features/hardware/widgets/internalContracts.ts';

interface InitializableWidget {
    initialize(): Promise<void>;
    destroy(): void;
}

const isValidWidgetSize = (value: number): boolean => isFiniteNumber(value);

const resolveWidgetSize = (size: WidgetSize): WidgetSize => (isValidWidgetSize(size['WIDTH']) && isValidWidgetSize(size['HEIGHT']) ? size : WIDGET_SIZE);

const createWidgetElement = (): HTMLElement => getDocument().createElement('div');

const initializeWidget = async <TWidget extends InitializableWidget>(widget: TWidget): Promise<TWidget> => {
    try {
        await widget.initialize();
    } catch (error) {
        widget.destroy();
        throw ensureError(error);
    }
    return widget;
};

const createCpuWidget = (cpu: CPUDevice, size: WidgetSize): Promise<CPUWidget> =>
    initializeWidget(
        new CPUWidget({
            container: createWidgetElement(),
            config: {
                id: `cpu-widget-${cpu.socketIndex}`,
                socketIndex: cpu.socketIndex,
                name: cpu.name,
                sockets: cpu.sockets,
                cores: cpu.cores,
                threads: cpu.threads,
                data: cpu.data
            },
            size: resolveWidgetSize(size)
        })
    );

const createGpuWidget = (gpu: GPUDevice, size: WidgetSize, widgetId: string): Promise<GPUWidget> =>
    initializeWidget(
        new GPUWidget({
            container: createWidgetElement(),
            config: {
                id: widgetId,
                index: gpu.index,
                name: gpu.name,
                data: gpu.data
            },
            size: resolveWidgetSize(size)
        })
    );

const createNetworkWidget = (network: NetworkDevice, size: WidgetSize, widgetId: string): Promise<NetworkWidget> =>
    initializeWidget(
        new NetworkWidget({
            container: createWidgetElement(),
            config: {
                id: widgetId,
                deviceId: network.deviceId,
                index: network.index,
                name: network.name,
                data: network.data
            },
            size: resolveWidgetSize(size)
        })
    );

const commitWidgetOrder = (container: HTMLElement, elements: ReadonlyArray<HTMLElement>): void => {
    const retained = new Set<Node>(elements);
    for (const child of Array.from(container.childNodes)) {
        if (!retained.has(child)) {
            child.remove();
        }
    }
    elements.forEach((element, index) => {
        const current = container.children.item(index);
        if (current !== element) {
            container.insertBefore(element, current);
        }
        const checkerboardClass = resolveCheckerboardClass(index);
        element.classList.toggle(checkerboardClass, true);
        element.classList.toggle(invertCheckerboardClass(checkerboardClass), false);
    });
};

export { commitWidgetOrder, createCpuWidget, createGpuWidget, createNetworkWidget };
