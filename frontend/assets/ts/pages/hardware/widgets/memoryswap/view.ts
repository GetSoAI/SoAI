/* SoAI - Hardware page memory and swap rendering [frontend/assets/ts/pages/hardware/widgets/memoryswap/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { buildFragment } from '@core/dom/renderCache.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatPercent } from '@core/primitives/percent.ts';
import { setTooltipText } from '@core/ui/tooltips/tooltipAttributes.ts';
import type { MemorySwapMode, MemorySwapPanelHost, MemorySwapPanelSurfaces, MemorySwapProcessUsage, MemorySwapRenderModel, MemorySwapUsage } from '@pages/hardware/widgets/memoryswap/types.ts';

const createMemorySwapPanel = (host: MemorySwapPanelHost, container: HTMLElement): MemorySwapPanelSurfaces => {
    const shell = host.createElement('div', { className: 'hardware-memory-swap-shell' });
    const gauges = host.createElement('div', { className: 'hardware-memory-swap-gauges' });
    const processes = host.createElement('div', { className: 'hardware-memory-swap-processes' });
    shell.append(gauges, processes);
    container.replaceChildren(shell);
    return { shell, gauges, processes };
};

const renderMemorySwapPanel = (host: MemorySwapPanelHost, surfaces: MemorySwapPanelSurfaces, model: MemorySwapRenderModel): void => {
    surfaces.shell.classList.toggle('hardware-memory-swap-shell--ram', model.mode === 'ram');
    surfaces.shell.classList.toggle('hardware-memory-swap-shell--swap', model.mode === 'swap');
    surfaces.gauges.replaceChildren(createGauge(host, model.ramUsage, model.mode), createGauge(host, model.swapUsage, model.mode));
    renderProcessSection(host, surfaces.processes, model);
};

const createGauge = (host: MemorySwapPanelHost, usage: MemorySwapUsage, mode: MemorySwapMode): HTMLElement => {
    const activeClass = usage.type === mode ? ' is-active' : '';
    const gauge = host.createElement('div', {
        className: `hardware-memory-swap-gauge hardware-memory-swap-gauge--${usage.type}${usage.available ? '' : ' is-unavailable'}${activeClass}`
    });
    const ringShell = host.createElement('div', { className: 'hardware-memory-swap-ring-shell' });
    const ring = host.createElement('div', { className: 'hardware-memory-swap-ring' });
    host.setStyle(ring, '--memory-swap-arc', usage.available ? formatPercent(usage.percent * 0.75, 3) : '0%');
    const arc = host.createElement('span', { className: 'hardware-memory-swap-ring-arc' });
    const face = host.createElement('span', { className: 'hardware-memory-swap-ring-face' });
    const center = host.createElement('div', { className: 'hardware-memory-swap-gauge-center' });
    const label = host.createElement('span', { className: 'hardware-memory-swap-gauge-label' });
    const value = host.createElement('span', { className: 'hardware-memory-swap-gauge-value' });
    host.updateText(label, usage.label);
    host.updateText(value, usage.available ? formatPercent(usage.percent) : i18n.t('hardware.cards.memorySwap.unavailableShort'));
    center.append(label, value);
    ring.append(arc, face, center);
    ringShell.append(ring);

    const stats = host.createElement('div', { className: 'hardware-memory-swap-stat-row' });
    stats.append(createStat(host, i18n.t('hardware.cards.memorySwap.labels.used'), usage.usedText), createStat(host, i18n.t('hardware.cards.memorySwap.labels.total'), usage.totalText));
    gauge.append(ringShell, stats);
    return gauge;
};

const createStat = (host: MemorySwapPanelHost, labelText: string, valueText: string): HTMLElement => {
    const item = host.createElement('div', { className: 'hardware-memory-swap-stat' });
    const label = host.createElement('span', { className: 'hardware-memory-swap-stat-label' });
    const value = host.createElement('span', { className: 'hardware-memory-swap-stat-value' });
    host.updateText(label, labelText);
    host.updateText(value, valueText);
    item.append(label, value);
    return item;
};

const renderProcessSection = (host: MemorySwapPanelHost, section: HTMLElement, model: MemorySwapRenderModel): void => {
    const header = host.createElement('div', { className: 'hardware-memory-swap-processes-header' });
    const title = host.createElement('span', { className: 'hardware-memory-swap-processes-title' });
    const metric = host.createElement('span', { className: 'hardware-memory-swap-processes-metric' });
    host.updateText(title, i18n.t('hardware.cards.memorySwap.processes.title'));
    host.updateText(metric, model.processMetricLabel);
    header.append(title, metric);
    if (model.processStatus) {
        const status = host.createElement('div', { className: 'hardware-memory-swap-status u-text-muted' });
        host.updateText(status, model.processStatus);
        section.replaceChildren(header, status);
        return;
    }
    const list = host.createElement('div', { className: 'hardware-memory-swap-process-list' });
    list.append(
        buildFragment(
            model.processes.map((row) => {
                return createProcessRow(host, row);
            })
        )
    );
    section.replaceChildren(header, list);
};

const createProcessRow = (host: MemorySwapPanelHost, row: MemorySwapProcessUsage): HTMLElement => {
    const element = host.createElement('div', { className: 'hardware-memory-swap-process-row' });
    const meta = host.createElement('div', { className: 'hardware-memory-swap-process-meta' });
    const name = host.createElement('span', { className: 'hardware-memory-swap-process-name' });
    const value = host.createElement('span', { className: 'hardware-memory-swap-process-value' });
    host.updateText(name, row.name);
    setTooltipText(name, row.name);
    host.updateText(value, row.valueText);
    meta.append(name, value);
    const bar = host.createElement('div', { className: 'hardware-memory-swap-process-bar' });
    const fill = host.createElement('div', { className: 'hardware-memory-swap-process-fill' });
    host.setStyle(fill, 'width', formatPercent(row.percentOfMax, 3));
    bar.append(fill);
    element.append(meta, bar);
    return element;
};

export { createMemorySwapPanel, renderMemorySwapPanel };
