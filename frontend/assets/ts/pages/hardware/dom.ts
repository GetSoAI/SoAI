/* SoAI - Hardware page DOM contracts [frontend/assets/ts/pages/hardware/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { narrowButton, narrowTable } from '@core/dom/narrowElement.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import { isHTMLElement } from '@core/typeGuards.ts';

type HardwareUi = {
    root: HTMLElement;
    logsButton: HTMLButtonElement;
    exportButton: HTMLButtonElement;
    systemInfoButton: HTMLButtonElement;

    widgetsContainer: HTMLElement;
    chartFiltersHost: HTMLElement;
    gpuControlsContainer: HTMLElement | null;

    processTable: HTMLTableElement | null;
    processTableBody: HTMLElement | null;
    processSummary: HTMLElement | null;

    networkContent: HTMLElement;
    networkSummary: HTMLElement;
    storageContent: HTMLElement;
    storageSummary: HTMLElement;
    memorySwapContent: HTMLElement;
    memorySwapSummary: HTMLElement;
};

const requireHardwareUi = (pageDom: PageDom, root: Element): HardwareUi => {
    if (!isHTMLElement(root)) {
        throw new Error('Hardware page requires a host container');
    }

    return {
        root,
        logsButton: narrowButton(pageDom.requireHTMLElement('#hardware-logs-btn', root), 'Hardware logs button'),
        exportButton: narrowButton(pageDom.requireHTMLElement('#hardware-export-btn', root), 'Hardware export button'),
        systemInfoButton: narrowButton(pageDom.requireHTMLElement('#hardware-sysinfo-btn', root), 'Hardware system info button'),

        widgetsContainer: pageDom.requireHTMLElement('#hardwareWidgetsContainer', root),
        chartFiltersHost: pageDom.requireHTMLElement('#hardwareChartFilters', root),
        gpuControlsContainer: pageDom.optionalHTMLElement('#gpu-controls-container', root),

        processTable: optionalHardwareTable(pageDom, '#hardwareProcessTable', root),
        processTableBody: pageDom.optionalHTMLElement('#hardwareProcessTableBody', root),
        processSummary: pageDom.optionalHTMLElement('#hardwareProcessSummary', root),

        networkContent: pageDom.requireHTMLElement('#hardwareNetworkContent', root),
        networkSummary: pageDom.requireHTMLElement('#hardwareNetworkSummary', root),
        storageContent: pageDom.requireHTMLElement('#hardwareStorageContent', root),
        storageSummary: pageDom.requireHTMLElement('#hardwareStorageSummary', root),
        memorySwapContent: pageDom.requireHTMLElement('#hardwareMemorySwapContent', root),
        memorySwapSummary: pageDom.requireHTMLElement('#hardwareMemorySwapSummary', root)
    };
};

const optionalHardwareTable = (pageDom: PageDom, selector: string, root: Element): HTMLTableElement | null => {
    const candidate = pageDom.optionalHTMLElement(selector, root);
    return candidate ? narrowTable(candidate, 'Hardware process table') : null;
};

export { optionalHardwareTable, requireHardwareUi };
export type { HardwareUi };
