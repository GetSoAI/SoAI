/* SoAI - Hardware page rendering [frontend/assets/ts/pages/hardware/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { i18n } from '@core/i18n/index.ts';
import { windowIdentity } from '@core/runtime/windowIdentity.ts';
import type { GenerateStandardHeaderOptions } from '@core/routing/pages/pagetypes/public.ts';

import { uiHtml } from '@core/security/uiHtml.ts';
import type { IconName } from '@core/ui/icons/iconRegistry.generated.ts';
import type { IconOptions } from '@core/ui/icons/iconservice/public.ts';
import { HARDWARE_GRID_SETTINGS } from '@pages/hardware/rendering/layout/constants.ts';

type GetIconSyncFunctionValue = (iconName: IconName, options?: IconOptions) => TrustedHtml;
type GenerateStandardHeaderFunctionValue = (options: GenerateStandardHeaderOptions) => TrustedHtml;

type HardwarePageViewDependencies = {
    getIconSync: GetIconSyncFunctionValue;
    generateStandardHeader: GenerateStandardHeaderFunctionValue;
};

const renderHardwarePageView = ({ getIconSync, generateStandardHeader }: HardwarePageViewDependencies): TrustedHtml => {
    const infoLabel = i18n.t('hardware.actions.infoLabel');
    const logsLabel = i18n.t('hardware.actions.logs');
    const exportLabel = i18n.t('common.export');
    const soaibenchLabel = i18n.t('hardware.modals.soaibenchRun.title');
    const logsIcon = getIconSync('logs', { size: 24, strokeWidth: 1.5 });
    const infoIcon = getIconSync('info', { size: 24, strokeWidth: 2 });
    const exportIcon = getIconSync('download', { size: 24, strokeWidth: 1.5 });
    const soaibenchIcon = getIconSync('device-gpu', { size: 24, strokeWidth: 1.5 });
    const headerMarkup = generateStandardHeader({
        title: i18n.t('hardware.title'),
        description: i18n.t('hardware.description'),
        detachedHeaderMode: 'show',
        actions: [
            {
                type: 'button',
                content: uiHtml`${logsIcon}<span>${logsLabel}</span>`,
                id: 'hardware-logs-btn',
                attributes: { 'data-action': 'hardware.logs', hidden: windowIdentity.isDetachedContext(), disabled: windowIdentity.isDetachedContext() },
                ariaLabel: i18n.t('hardware.actions.openLogs')
            },
            {
                type: 'button',
                content: uiHtml`${infoIcon}<span>${infoLabel}</span>`,
                id: 'hardware-sysinfo-btn',
                attributes: { 'data-action': 'hardware.systemInfo.open' },
                ariaLabel: i18n.t('hardware.actions.viewSystemInfo')
            },
            {
                type: 'button',
                content: uiHtml`${soaibenchIcon}<span>${soaibenchLabel}</span>`,
                id: 'hardware-soaibench-btn',
                attributes: { 'data-action': 'hardware.gpu.soaibench.select', hidden: true },
                ariaLabel: soaibenchLabel
            },
            {
                type: 'button',
                content: uiHtml`${exportIcon}<span>${exportLabel}</span>`,
                id: 'hardware-export-btn',
                attributes: { 'data-action': 'hardware.export' },
                ariaLabel: exportLabel
            }
        ],
        stats: [
            { id: 'hardware-stat-processes', label: i18n.t('hardware.summary.stats.processes') },
            { id: 'hardware-stat-cpu', label: i18n.t('hardware.summary.stats.cpuUsage') },
            { id: 'hardware-stat-total-ram', label: i18n.t('hardware.summary.stats.totalRam') },
            { id: 'hardware-stat-total-vram', label: i18n.t('hardware.summary.stats.totalVram') },
            { id: 'hardware-stat-total-memory', label: i18n.t('hardware.summary.stats.totalRamVram') },
            { id: 'hardware-stat-platform', label: i18n.t('hardware.summary.stats.platform') },
            { id: 'systemUptime', label: i18n.t('hardware.summary.stats.systemUptime') },
            { id: 'totalUptime', label: i18n.t('hardware.summary.stats.totalUptime') }
        ],
        contentLayout: 'analytics'
    });
    const historyTitle = i18n.t('hardware.modals.soaibenchHistory.title');
    const contentMarkup = uiHtml`<div class="hardware-content analytics-stack"><div id="hardware-gpu-resource-status" class="hardware-gpu-resource-status u-hidden" role="status" aria-live="polite"></div><div id="hardware-grid" class="hardware-grid movable-sections-grid" data-columns="${HARDWARE_GRID_SETTINGS.columns}"></div><section id="hardware-soaibench-history-panel" class="card metrics-panel hardware-section hardware-soaibench-history-page-panel" aria-label="${historyTitle}"><div class="section-header"><div class="section-header-main"><h2 class="section-title">${historyTitle}</h2></div></div><div class="section-content"><div class="metrics-card-content metrics-card-content--table data-table-wrapper hardware-soaibench-history-card-content hardware-soaibench-history-table-wrapper has-scroll" data-card-content><table id="hardware-soaibench-history-page-table" class="table table-hover table-compact hardware-soaibench-history-table"></table></div></div></section></div>`;
    const markup = headerMarkup.html.replace('<!-- Page content goes here -->', contentMarkup.html);
    return toTrustedUiHtml(markup);
};

export { renderHardwarePageView };
export type { HardwarePageViewDependencies };
