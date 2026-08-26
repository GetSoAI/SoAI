/* SoAI - Hardware page memory and swap contracts [frontend/assets/ts/pages/hardware/widgets/memoryswap/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ElementOptions } from '@core/dom/dom.ts';
import type { HardwarePageSnapshot } from '@pages/hardware/types.ts';
import type { ProcessRecord } from '@pages/hardware/widgets/processes/types.ts';

type MemorySwapMode = 'ram' | 'swap';

type MemorySwapUsage = {
    type: MemorySwapMode;
    label: string;
    percent: number;
    usedText: string;
    totalText: string;
    available: boolean;
};

type MemorySwapProcessUsage = {
    pid: number;
    name: string;
    valueMb: number;
    valueText: string;
    percentOfMax: number;
};

type MemorySwapRenderModel = {
    summary: string;
    mode: MemorySwapMode;
    ramUsage: MemorySwapUsage;
    swapUsage: MemorySwapUsage;
    processes: MemorySwapProcessUsage[];
    processMetricLabel: string;
    processStatus: string | null;
};

type MemorySwapPanelSurfaces = {
    shell: HTMLElement;
    gauges: HTMLElement;
    processes: HTMLElement;
};

type MemorySwapPanelHost = {
    optionalHTMLElement: (selector: string, parent?: Element | null) => HTMLElement | null;
    updateText: (element: Element, text: string) => void;
    createElement: (tagName: string, attrs?: ElementOptions) => HTMLElement;
    setStyle: (element: Element, property: string, value: string) => void;
};

type MemorySwapPanelInput = {
    snapshot: HardwarePageSnapshot | null;
    mode: MemorySwapMode;
    processes: readonly ProcessRecord[];
    processDataReady: boolean;
    canViewProcesses: boolean;
};

export type { MemorySwapMode, MemorySwapPanelHost, MemorySwapPanelInput, MemorySwapPanelSurfaces, MemorySwapProcessUsage, MemorySwapRenderModel, MemorySwapUsage };
