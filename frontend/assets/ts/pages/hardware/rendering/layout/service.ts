/* SoAI - Hardware page layout service [frontend/assets/ts/pages/hardware/rendering/layout/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import type { MovableSectionLayoutConfig } from '@core/routing/pages/movablesections/types.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { createOverflowNavButtonMarkup } from '@core/ui/controls/OverflowNav.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { renderIconSlot } from '@core/ui/icons/view.ts';
import { HARDWARE_ACTION_MEMORY_SWAP_TOGGLE } from '@pages/hardware/actions.ts';
import { HARDWARE_GRID_SETTINGS } from '@pages/hardware/rendering/layout/constants.ts';
import type { HardwareLayoutPermissions, HardwarePanelBlueprint, HardwarePanelId } from '@pages/hardware/rendering/layout/types.ts';

const HARDWARE_STANDARD_PANEL_SPAN = 4;
const HARDWARE_HISTORY_PANEL_SPAN = 4;
const HARDWARE_GPU_CONTROLS_PANEL_SPAN = 6;

const isHardwarePanelId = (value: string): value is HardwarePanelId => {
    switch (value) {
        case 'widgets':
        case 'history':
        case 'gpuControls':
        case 'processes':
        case 'network':
        case 'storage':
        case 'memorySwap':
            return true;
        default:
            return false;
    }
};

const resolveHardwareSectionTitle = (sectionId: HardwarePanelId): string => {
    switch (sectionId) {
        case 'widgets':
            return i18n.t('hardware.widgets.title');
        case 'history':
            return i18n.t('hardware.cards.history.title');
        case 'gpuControls':
            return i18n.t('hardware.cards.gpu.controlsPanelTitle');
        case 'processes':
            return i18n.t('hardware.cards.processes.title');
        case 'network':
            return i18n.t('hardware.cards.network.title');
        case 'storage':
            return i18n.t('hardware.cards.storage.title');
        case 'memorySwap':
            return i18n.t('hardware.cards.memorySwap.title');
    }
    const unhandledSectionId: never = sectionId;
    return unhandledSectionId;
};

const resolveOverflowNavLabel = (direction: 'left' | 'right'): string => {
    switch (direction) {
        case 'left':
            return i18n.t('tabs.scrollLeft');
        case 'right':
            return i18n.t('tabs.scrollRight');
    }
};

const createHardwareMovableLayoutConfig = (): MovableSectionLayoutConfig<HardwarePanelId> => ({
    logLabel: 'HardwareLayout',
    gridSelector: '#hardware-grid',
    sectionSelector: '.hardware-section',
    sectionClassName: 'card metrics-panel hardware-section movable-section',
    sectionIdAttribute: 'data-section-id',
    dragHandleSelector: '[data-section-handle]',
    invalidDragSelector: '.section-controls',
    settings: HARDWARE_GRID_SETTINGS,
    isSectionId: isHardwarePanelId,
    resolveTitle: resolveHardwareSectionTitle,
    resolveSubtitle: () => ''
});

const renderOverflowButton = (direction: 'left' | 'right', modifier: string): string =>
    createOverflowNavButtonMarkup({
        direction,
        className: `hardware-overflow-nav hardware-overflow-nav--${direction} ui-icon-button ${modifier}`,
        label: resolveOverflowNavLabel(direction),
        iconName: direction === 'left' ? 'chevron-left' : 'chevron-right',
        iconOptions: { size: 20, strokeWidth: 1.5 }
    });

const renderHardwareWidgetContent = (): TrustedHtml => {
    const left = renderOverflowButton('left', 'hardware-overflow-nav--widgets-control');
    const right = renderOverflowButton('right', 'hardware-overflow-nav--widgets-control');
    return uiHtml`<div class="hardware-overflow-row-wrapper hardware-overflow-row-wrapper--widgets">${toTrustedUiHtml(left)}<div class="hardware-widgets-container" id="hardwareWidgetsContainer" data-card-content></div>${toTrustedUiHtml(right)}</div>`;
};

const renderHardwareGpuContent = (): TrustedHtml => {
    const left = renderOverflowButton('left', 'hardware-overflow-nav--gpu-control');
    const right = renderOverflowButton('right', 'hardware-overflow-nav--gpu-control');
    return uiHtml`<div class="hardware-overflow-row-wrapper hardware-overflow-row-wrapper--gpu">${toTrustedUiHtml(left)}<div class="gpu-controls-container" id="gpu-controls-container" data-card-content><p class="hardware-placeholder-text">${i18n.t('hardware.cards.gpu.loading')}</p></div>${toTrustedUiHtml(right)}</div>`;
};

const renderHardwareProcessesContent = (): TrustedHtml => {
    const processNameLabel = i18n.t('hardware.cards.processes.tableHeaders.process');
    const processPidLabel = i18n.t('hardware.cards.processes.tableHeaders.pid');
    const processCpuLabel = i18n.t('hardware.cards.processes.tableHeaders.cpu');
    const processMemoryLabel = i18n.t('hardware.cards.processes.tableHeaders.memory');
    const processRuntimeLabel = i18n.t('hardware.cards.processes.tableHeaders.runtime');
    return uiHtml`<div class="metrics-card-content metrics-card-content--table data-table-wrapper hardware-process-table-wrapper has-scroll" data-card-content><table class="table table-hover table-compact" id="hardwareProcessTable"><thead><tr><th class="sortable" data-action="hardware.process.sort" data-sort="name" tabindex="0" role="columnheader" aria-sort="none" aria-label="${uiAttr(processNameLabel)}" data-tooltip="${uiAttr(processNameLabel)}">${processNameLabel} <span class="sort-indicator"></span></th><th class="sortable" data-action="hardware.process.sort" data-sort="pid" tabindex="0" role="columnheader" aria-sort="none" aria-label="${uiAttr(processPidLabel)}" data-tooltip="${uiAttr(processPidLabel)}">${processPidLabel} <span class="sort-indicator"></span></th><th class="sortable" data-action="hardware.process.sort" data-sort="cpu" tabindex="0" role="columnheader" aria-sort="none" aria-label="${uiAttr(processCpuLabel)}" data-tooltip="${uiAttr(processCpuLabel)}">${processCpuLabel} <span class="sort-indicator"></span></th><th class="sortable" data-action="hardware.process.sort" data-sort="memory" tabindex="0" role="columnheader" aria-sort="none" aria-label="${uiAttr(processMemoryLabel)}" data-tooltip="${uiAttr(processMemoryLabel)}">${processMemoryLabel} <span class="sort-indicator"></span></th><th class="sortable" data-action="hardware.process.sort" data-sort="runtime" tabindex="0" role="columnheader" aria-sort="none" aria-label="${uiAttr(processRuntimeLabel)}" data-tooltip="${uiAttr(processRuntimeLabel)}">${processRuntimeLabel} <span class="sort-indicator"></span></th></tr></thead><tbody id="hardwareProcessTableBody"><tr><td colspan="5" class="u-text-center u-text-muted">${i18n.t('hardware.processes.awaiting')}</td></tr></tbody></table></div>`;
};

const renderHardwareMemorySwapControls = (): TrustedHtml => {
    const label = i18n.t('hardware.cards.memorySwap.actions.showSwap');
    const icon = renderIconSlot(getIconSync('request-distribution-source', { size: 14, strokeWidth: 1.8 }));
    return uiHtml`<span class="u-text-muted" id="hardwareMemorySwapSummary">${i18n.t('hardware.common.detecting')}</span><button type="button" id="hardwareMemorySwapToggle" class="ui-icon-button ui-icon-button--titlebar ui-variant-neutral" data-action="${HARDWARE_ACTION_MEMORY_SWAP_TOGGLE}" aria-label="${uiAttr(label)}" data-tooltip="${uiAttr(label)}" aria-pressed="false">${icon}</button>`;
};

const renderHardwareMemorySwapContent = (): TrustedHtml => {
    return uiHtml`<div class="hardware-card-content hardware-memory-swap-content" id="hardwareMemorySwapContent" data-card-content><div class="hardware-memory-swap-placeholder"><span>${i18n.t('hardware.cards.memorySwap.states.awaitingSnapshot')}</span></div></div>`;
};

const createHardwarePanelBlueprints = (permissions: HardwareLayoutPermissions): Map<HardwarePanelId, HardwarePanelBlueprint> => {
    const widgetsRow = HARDWARE_STANDARD_PANEL_SPAN;
    const widgetsWidth = permissions.canViewProcesses ? 2 : 3;
    const storageColumn = permissions.canViewProcesses ? 2 : 1;
    const memorySwapRow = permissions.canViewProcesses ? widgetsRow : 0;
    const historyPanelRow = widgetsRow + HARDWARE_STANDARD_PANEL_SPAN;
    const gpuControlsPanelRow = historyPanelRow + HARDWARE_HISTORY_PANEL_SPAN;
    const blueprints = new Map<HardwarePanelId, HardwarePanelBlueprint>();
    blueprints.set('widgets', {
        rootId: 'hardware-widgets-section',
        className: 'hardware-widgets-section',
        layout: { x: 0, y: widgetsRow, width: widgetsWidth, height: HARDWARE_STANDARD_PANEL_SPAN },
        showSubtitle: false,
        content: renderHardwareWidgetContent()
    });
    blueprints.set('history', {
        rootId: 'hardwareChartCard',
        className: 'history-chart-card',
        layout: { x: 0, y: historyPanelRow, width: 3, height: HARDWARE_HISTORY_PANEL_SPAN },
        showSubtitle: false,
        controls: () => uiHtml`<div id="hardwareChartFilters"></div>`,
        content: uiHtml`<div class="history-chart-shell" data-card-content id="hardwareHistoryChart"></div>`
    });
    if (permissions.canTuneGpu) {
        blueprints.set('gpuControls', {
            rootId: 'gpu-control-section',
            className: 'gpu-control-section',
            layout: { x: 0, y: gpuControlsPanelRow, width: 3, height: HARDWARE_GPU_CONTROLS_PANEL_SPAN },
            showSubtitle: false,
            controls: () => uiHtml`<span class="u-text-muted">${i18n.t('hardware.cards.gpu.controlsPanelWarning')}</span>`,
            content: renderHardwareGpuContent()
        });
    }
    if (permissions.canViewProcesses) {
        blueprints.set('processes', {
            rootId: 'hardware-process-card',
            className: 'hardware-process-card',
            layout: { x: 1, y: 0, width: 1, height: HARDWARE_STANDARD_PANEL_SPAN },
            showSubtitle: false,
            controls: () => uiHtml`<span class="u-text-muted" id="hardwareProcessSummary">${i18n.t('hardware.processes.collecting')}</span>`,
            content: renderHardwareProcessesContent()
        });
    }
    blueprints.set('network', {
        rootId: 'hardware-network-card',
        className: 'hardware-network-card',
        layout: { x: 0, y: 0, width: 1, height: HARDWARE_STANDARD_PANEL_SPAN },
        showSubtitle: false,
        controls: () => uiHtml`<span class="u-text-muted" id="hardwareNetworkSummary">${i18n.t('hardware.common.detecting')}</span>`,
        content: uiHtml`<div class="hardware-card-content hardware-network-content" id="hardwareNetworkContent" data-card-content><div class="hardware-network-placeholder"><span>${i18n.t('hardware.cards.network.waiting')}</span></div></div>`
    });
    blueprints.set('storage', {
        rootId: 'hardware-storage-card',
        className: 'hardware-storage-card',
        layout: { x: storageColumn, y: 0, width: 1, height: HARDWARE_STANDARD_PANEL_SPAN },
        showSubtitle: false,
        controls: () => uiHtml`<span class="u-text-muted" id="hardwareStorageSummary">${i18n.t('hardware.common.detecting')}</span>`,
        content: uiHtml`<div class="hardware-card-content hardware-storage-content" id="hardwareStorageContent" data-card-content><div class="hardware-storage-placeholder"><span>${i18n.t('hardware.cards.storage.waiting')}</span></div></div>`
    });
    blueprints.set('memorySwap', {
        rootId: 'hardware-memory-swap-card',
        className: 'hardware-memory-swap-card',
        layout: { x: 2, y: memorySwapRow, width: 1, height: HARDWARE_STANDARD_PANEL_SPAN },
        showSubtitle: false,
        controls: () => renderHardwareMemorySwapControls(),
        content: renderHardwareMemorySwapContent()
    });
    return blueprints;
};

export { createHardwareMovableLayoutConfig, createHardwarePanelBlueprints, isHardwarePanelId };
