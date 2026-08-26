/* SoAI - Dashboard page status section [frontend/assets/ts/pages/dashboard/controllers/dashboardStatusSection.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { applyTextContent } from '@core/dom/textContent.ts';
import { i18n } from '@core/i18n/index.ts';
import { getMainStatusMonitor } from '@core/mainstatusmonitor/public.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { formatDuration } from '@core/primitives/duration.ts';
import { createMainStateIndicatorUI, updateMainStateIndicatorUI } from '@features/indicators/public.ts';
import type { DashboardHost } from '@core/edition/dashboardContribution.ts';
import type { StatusManagerContract } from '@pages/dashboard/contracts/statusManager.ts';
import { resolveDashboardStatusMetrics } from '@pages/dashboard/mappers/statusMetricsDomain.ts';

interface DashboardStatusRendererDependencies {
    host: DashboardHost;
    getMetrics: () => JsonValue;
    getPlugins: () => readonly JsonValue[];
    getModels: () => readonly JsonValue[];
    getStatusManager: () => StatusManagerContract | null;
}

interface DashboardStatusItem {
    label: string;
    value: string;
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

const STATUS_VALUE_COMPACT_THRESHOLD = 9;
const STATUS_VALUE_DENSE_THRESHOLD = 14;
const STATUS_VALUE_TIGHT_THRESHOLD = 20;

const resolveStatusValueSizeClass = (value: string): string => {
    const length = Array.from(value).length;
    if (length >= STATUS_VALUE_TIGHT_THRESHOLD) {
        return 'status-value--tight';
    }
    if (length >= STATUS_VALUE_DENSE_THRESHOLD) {
        return 'status-value--dense';
    }
    if (length >= STATUS_VALUE_COMPACT_THRESHOLD) {
        return 'status-value--compact';
    }
    return '';
};

const createDashboardStatusSectionRenderer = (dependencies: DashboardStatusRendererDependencies): (() => void) => {
    const host = dependencies.host;
    let viewElements: DashboardStatusViewElements | null = null;

    const buildItems = (): DashboardStatusItem[] => {
        const statusMetrics = resolveDashboardStatusMetrics(dependencies.getMetrics(), dependencies.getPlugins().length, dependencies.getModels().length);
        return [
            { label: i18n.t('dashboard.sections.status.installedPlugins'), value: formatCompactNumber(statusMetrics.installedPlugins) },
            { label: i18n.t('dashboard.sections.status.installedModels'), value: formatCompactNumber(statusMetrics.installedModels) },
            { label: i18n.t('dashboard.sections.status.completedRequests'), value: formatCompactNumber(statusMetrics.completedRequests) },
            { label: i18n.t('dashboard.sections.status.failedRequests'), value: formatCompactNumber(statusMetrics.failedRequests) },
            { label: i18n.t('dashboard.sections.status.totalTokens'), value: formatCompactNumber(statusMetrics.totalTokens) },
            { label: i18n.t('dashboard.sections.status.uptime'), value: formatDuration(statusMetrics.uptimeSeconds, 'uptime') }
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
                const valueClass = ['status-value', 'ui-mini-stat-strip__value', resolveStatusValueSizeClass(item.value)].filter(Boolean).join(' ');
                const valueNode = narrowHTMLElement(host.createElement('span', { className: valueClass }, item.value), 'status value');
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
            applyTextContent(itemElements.value, item.value);
            const valueClass = ['status-value', 'ui-mini-stat-strip__value', resolveStatusValueSizeClass(item.value)].filter(Boolean).join(' ');
            if (itemElements.value.className !== valueClass) {
                itemElements.value.className = valueClass;
            }
        });
        updateMainStateIndicatorUI(elements.mainState, currentMainState);
    };

    const syncStatusLineColor = (mainState: HTMLElement): void => {
        const statusLine = host.optionalHTMLElement('#status-status');
        if (statusLine) {
            statusLine.dataset['color'] = mainState.dataset['color'] ?? 'grey';
        }
    };

    return (): void => {
        const content = host.requireUI('status-content');
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
        syncStatusLineColor(viewElements.mainState);
    };
};

export { createDashboardStatusSectionRenderer };
export type { DashboardStatusRendererDependencies, StatusManagerContract };
