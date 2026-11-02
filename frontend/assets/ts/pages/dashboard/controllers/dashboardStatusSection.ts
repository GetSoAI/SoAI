/* SoAI - Dashboard page status section [frontend/assets/ts/pages/dashboard/controllers/dashboardStatusSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatLocalizedNumber, getListFormat, getResolvedLocalizationLocale } from '@core/localization/public.ts';
import type { ElementResizeRedrawWatcher } from '@core/layout/elementResizeRedraw.ts';
import { getMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import { formatDuration } from '@core/primitives/duration.ts';
import { createMainStateIndicatorUI, updateMainStateIndicatorUI } from '@features/indicators/public.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';
import type { StatusManagerContract } from '@pages/dashboard/contracts/statusManager.ts';
import { resolveDashboardStatusMetrics } from '@pages/dashboard/mappers/statusMetricsDomain.ts';

interface DashboardStatusRendererDependencies {
    host: DashboardHost;
    sizeWatcher: ElementResizeRedrawWatcher;
    getMetrics: () => JsonValue;
    getPlugins: () => readonly JsonValue[];
    getModels: () => readonly JsonValue[];
    getStatusManager: () => StatusManagerContract | null;
}

interface DashboardStatusItem {
    label: string;
    value: string;
    compactValue: string;
    uptime?: boolean;
}

interface DashboardStatusItemElements {
    label: HTMLElement;
    value: HTMLElement;
}

interface DashboardStatusViewElements {
    overview: HTMLElement;
    items: DashboardStatusItemElements[];
    mainState: HTMLElement;
}

const resolveStatusValueClass = (item: DashboardStatusItem): string => ['status-value', 'ui-mini-stat-strip__value', item.uptime ? 'status-value--uptime' : ''].filter(Boolean).join(' ');

const formatFullUptime = (seconds: number): string => {
    const totalMinutes = Math.floor(Math.max(0, seconds) / 60);
    const days = Math.floor(totalMinutes / 1440);
    const hours = Math.floor((totalMinutes % 1440) / 60);
    const minutes = totalMinutes % 60;
    const parts: string[] = [];
    if (days > 0) parts.push(i18n.plural('common.time.units.day.long', days, { count: formatLocalizedNumber(days) }));
    if (days > 0 || hours > 0) parts.push(i18n.plural('common.time.units.hour.long', hours, { count: formatLocalizedNumber(hours) }));
    parts.push(i18n.plural('common.time.units.minute.long', minutes, { count: formatLocalizedNumber(minutes) }));
    return getListFormat(getResolvedLocalizationLocale(), { style: 'long', type: 'unit' }).format(parts);
};

const fitStatusValue = (element: HTMLElement, item: DashboardStatusItem): void => {
    element.className = resolveStatusValueClass(item);
    applyTextContent(element, item.value);
    element.title = item.value;
    if (element.clientWidth <= 0 || element.scrollWidth <= element.clientWidth) return;
    applyTextContent(element, item.compactValue);
    for (const sizeClass of ['status-value--compact', 'status-value--dense', 'status-value--tight']) {
        if (element.scrollWidth <= element.clientWidth) break;
        element.className = `${resolveStatusValueClass(item)} ${sizeClass}`;
    }
};

const createDashboardStatusSectionRenderer = (dependencies: DashboardStatusRendererDependencies): (() => void) => {
    const host = dependencies.host;
    let viewElements: DashboardStatusViewElements | null = null;

    const buildItems = (): DashboardStatusItem[] => {
        const statusMetrics = resolveDashboardStatusMetrics(dependencies.getMetrics(), dependencies.getPlugins().length, dependencies.getModels().length);
        return [
            { label: i18n.t('dashboard.sections.status.installedPlugins'), value: formatLocalizedNumber(Math.round(statusMetrics.installedPlugins)), compactValue: formatLocalizedNumber(statusMetrics.installedPlugins, { notation: 'compact', maximumFractionDigits: 1 }) },
            { label: i18n.t('dashboard.sections.status.installedModels'), value: formatLocalizedNumber(Math.round(statusMetrics.installedModels)), compactValue: formatLocalizedNumber(statusMetrics.installedModels, { notation: 'compact', maximumFractionDigits: 1 }) },
            { label: i18n.t('dashboard.sections.status.completedRequests'), value: formatLocalizedNumber(Math.round(statusMetrics.completedRequests)), compactValue: formatLocalizedNumber(statusMetrics.completedRequests, { notation: 'compact', maximumFractionDigits: 1 }) },
            { label: i18n.t('dashboard.sections.status.failedRequests'), value: formatLocalizedNumber(Math.round(statusMetrics.failedRequests)), compactValue: formatLocalizedNumber(statusMetrics.failedRequests, { notation: 'compact', maximumFractionDigits: 1 }) },
            { label: i18n.t('dashboard.sections.status.totalTokens'), value: formatLocalizedNumber(Math.round(statusMetrics.totalTokens)), compactValue: formatLocalizedNumber(statusMetrics.totalTokens, { notation: 'compact', maximumFractionDigits: 1 }) },
            { label: i18n.t('dashboard.sections.status.uptime'), value: formatFullUptime(statusMetrics.uptimeSeconds), compactValue: formatDuration(statusMetrics.uptimeSeconds, 'uptime'), uptime: true }
        ];
    };

    const buildView = (items: readonly DashboardStatusItem[], currentMainState: string): DashboardStatusViewElements => {
        const overview = host.createElement('div', { className: 'status-overview' });
        const overviewElement = narrowHTMLElement(overview, 'status overview wrapper');
        const itemElements: DashboardStatusItemElements[] = [];
        for (let index = 0; index < items.length; index += 2) {
            const group = host.createElement('div', { className: 'status-stat-strip ui-mini-stat-strip' });
            const groupElement = narrowHTMLElement(group, 'status stat strip');
            const groupItems = items.slice(index, index + 2);
            groupItems.forEach((item, itemIndex): void => {
                const checkerboardClass = resolveCheckerboardClass(index + itemIndex, { columns: 2 });
                const row = host.createElement('div', { className: `status-item ui-mini-stat-strip__card ${checkerboardClass}` });
                const rowElement = narrowHTMLElement(row, 'status overview row');
                const valueClass = resolveStatusValueClass(item);
                const valueNode = narrowHTMLElement(host.createElement('span', { className: valueClass }, item.value), 'status value');
                valueNode.dir = 'auto';
                const labelNode = narrowHTMLElement(host.createElement('span', { className: 'status-label ui-mini-stat-strip__label' }, item.label), 'status label');
                rowElement.append(valueNode, labelNode);
                groupElement.appendChild(rowElement);
                itemElements.push({ label: labelNode, value: valueNode });
            });
            overviewElement.appendChild(groupElement);
        }
        const mainState = createMainStateIndicatorUI(currentMainState, { variant: 'dashboard' });
        mainState.id = 'status-main-state';
        overviewElement.appendChild(mainState);
        return { overview: overviewElement, items: itemElements, mainState };
    };

    const patchView = (elements: DashboardStatusViewElements, items: readonly DashboardStatusItem[], currentMainState: string): void => {
        if (elements.items.length !== items.length) {
            throw new Error('Dashboard status item count changed after initialization');
        }
        items.forEach((item, index): void => {
            const itemElements = elements.items[index];
            if (!itemElements) {
                throw new Error('Dashboard status item reference missing during update');
            }
            applyTextContent(itemElements.label, item.label);
        });
        updateMainStateIndicatorUI(elements.mainState, currentMainState);
    };

    const syncStatusLineColor = (mainState: HTMLElement): void => {
        const statusLine = host.optionalHTMLElement('#dashboard-status-status');
        if (statusLine) {
            statusLine.dataset['color'] = mainState.dataset['color'] ?? 'grey';
        }
    };

    return (): void => {
        const content = host.requireUI('dashboard-status-content');
        const contentElement = narrowHTMLElement(content, 'Dashboard status content');
        const currentMainState = getMainStatusMonitor().getCurrentState();
        const items = buildItems();
        if (!viewElements || !contentElement.contains(viewElements.overview)) {
            viewElements = buildView(items, currentMainState);
            host.replaceElementContent(contentElement, viewElements.overview, { escape: false });
            host.flushDOMUpdates();
        } else {
            patchView(viewElements, items, currentMainState);
        }
        const elements = viewElements;
        const fitValues = (): void => {
            elements.items.forEach((itemElements, index): void => {
                const item = items[index];
                if (item) fitStatusValue(itemElements.value, item);
            });
        };
        fitValues();
        dependencies.sizeWatcher.observe(elements.overview, fitValues);
        syncStatusLineColor(elements.mainState);
    };
};

export { createDashboardStatusSectionRenderer };
export type { DashboardStatusRendererDependencies, StatusManagerContract };
