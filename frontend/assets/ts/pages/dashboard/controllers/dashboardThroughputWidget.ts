/* SoAI - Dashboard page throughput widget [frontend/assets/ts/pages/dashboard/controllers/dashboardThroughputWidget.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { resolveCheckerboardClass } from '@core/dom/checkerboardAssignment.ts';
import { narrowHTMLElement } from '@core/dom/narrowElement.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatCompactNumber } from '@core/primitives/compactNumber.ts';
import { isFiniteNumber, isObject } from '@core/typeGuards.ts';
import type { JsonValue } from '@core/types/jsonValues.ts';
import { resolveMetricsActiveInferences, resolveMetricsCurrentTokenRate, type Metrics } from '@features/metrics/public.ts';
import { DashboardWidgetRefreshController } from '@pages/dashboard/controllers/dashboardWidgetRefreshController.ts';
import type { DashboardHost, DashboardTimerControl } from '@core/edition/dashboardContribution.ts';

interface DashboardThroughputControllerDependencies {
    host: DashboardHost;
    timers: DashboardTimerControl;
    getMetrics: () => JsonValue;
    isDestroyed: () => boolean;
}

type ThroughputMetricDatasetName = 'throughputActive' | 'throughputQueueDepth' | 'throughputPendingLoads';

const THROUGHPUT_TICK_INTERVAL_MS = 1000;
const THROUGHPUT_HALF_SATURATION_RATE = 120;

const toMetrics = (metrics: JsonValue): Metrics => (isObject(metrics) ? metrics : {});
class DashboardThroughputController {
    readonly #host: DashboardHost;
    readonly #getMetrics: () => JsonValue;
    readonly #isDestroyed: () => boolean;
    readonly #ticker: DashboardWidgetRefreshController;

    constructor(dependencies: DashboardThroughputControllerDependencies) {
        this.#host = dependencies.host;
        this.#getMetrics = dependencies.getMetrics;
        this.#isDestroyed = dependencies.isDestroyed;
        this.#ticker = new DashboardWidgetRefreshController({ timers: dependencies.timers, intervalMs: THROUGHPUT_TICK_INTERVAL_MS, onTick: (): void => this.#tick() });
    }

    renderSection(): void {
        if (this.#isDestroyed()) {
            return;
        }
        const content = this.#host.requireUI('throughput-content');
        this.#host.replaceElementContent(content, this.#buildMarkup(), { escape: false });
        this.#host.flushDOMUpdates();
        this.#paint();
        this.#ticker.start();
    }

    destroy(): void {
        this.#ticker.stop();
    }

    update(): void {
        if (this.#isDestroyed()) {
            return;
        }
        const metrics = this.#readMetrics();
        this.#paint();
        if (resolveMetricsCurrentTokenRate(metrics) <= 0) {
            this.#ticker.stop();
        }
    }

    #readMetrics(): Metrics {
        return toMetrics(this.#getMetrics());
    }

    #tick(): void {
        if (this.#isDestroyed()) {
            return;
        }
        if (resolveMetricsCurrentTokenRate(this.#readMetrics()) <= 0) {
            this.#paint();
            this.#ticker.stop();
        }
    }

    #buildMarkup(): HTMLElement {
        const wrapper = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput' }), 'dashboard throughput wrapper');
        const shell = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-ring-shell' }), 'dashboard throughput ring shell');
        const ring = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-ring', dataset: { throughputRing: 'true' } }), 'dashboard throughput ring');
        const arc = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-ring-arc' }), 'dashboard throughput ring arc');
        const face = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-ring-face' }), 'dashboard throughput ring face');
        const center = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-center' }), 'dashboard throughput center');
        const value = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-value', dataset: { throughputValue: 'true' } }, '0'), 'dashboard throughput value');
        const unit = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-unit' }, i18n.t('dashboard.sections.throughput.unit')), 'dashboard throughput unit');
        center.append(value, unit);
        ring.append(arc, face, center);
        shell.appendChild(ring);
        wrapper.append(shell, this.#buildStats());
        return wrapper;
    }

    #buildStats(): HTMLElement {
        const stats = narrowHTMLElement(this.#host.createElement('div', { className: 'dashboard-throughput-stats' }), 'dashboard throughput stats');
        stats.append(this.#buildMetricRow(`dashboard-throughput-active ${resolveCheckerboardClass(0)}`, 'dashboard-throughput-active-label', 'dashboard-throughput-active-value', i18n.t('dashboard.sections.throughput.active'), 'throughputActive'), this.#buildMetricRow(`dashboard-throughput-detail ${resolveCheckerboardClass(1)}`, 'dashboard-throughput-detail-label', 'dashboard-throughput-detail-value', i18n.t('metrics.cards.systemPerformance.stats.queueDepth'), 'throughputQueueDepth'), this.#buildMetricRow(`dashboard-throughput-detail ${resolveCheckerboardClass(2)}`, 'dashboard-throughput-detail-label', 'dashboard-throughput-detail-value', i18n.t('metrics.cards.systemPerformance.stats.pendingLoads'), 'throughputPendingLoads'));
        return stats;
    }

    #buildMetricRow(rowClassName: string, labelClassName: string, valueClassName: string, labelText: string, datasetName: ThroughputMetricDatasetName): HTMLElement {
        const row = narrowHTMLElement(this.#host.createElement('div', { className: rowClassName }), 'dashboard throughput metric row');
        const label = narrowHTMLElement(this.#host.createElement('div', { className: labelClassName }, labelText), 'dashboard throughput metric label');
        const value = narrowHTMLElement(this.#host.createElement('div', { className: valueClassName, dataset: { [datasetName]: 'true' } }, '0'), 'dashboard throughput metric value');
        row.append(label, value);
        return row;
    }

    #readActive(metrics: Metrics): number {
        return resolveMetricsActiveInferences(metrics);
    }

    #readQueueDepth(metrics: Metrics): number {
        const queueSize = metrics.director?.gauges?.queueSize;
        return isFiniteNumber(queueSize) ? queueSize : 0;
    }

    #readPendingLoads(metrics: Metrics): number {
        const pendingLoads = metrics.director?.gauges?.pendingLoads;
        return isFiniteNumber(pendingLoads) ? pendingLoads : 0;
    }

    #paint(): void {
        const content = this.#host.optionalUI('throughput-content');
        if (!content) {
            return;
        }
        const metrics = this.#readMetrics();
        const currentRate = resolveMetricsCurrentTokenRate(metrics);
        const valueNode = this.#host.optionalHTMLElement('[data-throughput-value]', content);
        const ring = this.#host.optionalHTMLElement('[data-throughput-ring]', content);
        const activeNode = this.#host.optionalHTMLElement('[data-throughput-active]', content);
        const queueDepthNode = this.#host.optionalHTMLElement('[data-throughput-queue-depth]', content);
        const pendingLoadsNode = this.#host.optionalHTMLElement('[data-throughput-pending-loads]', content);
        const rounded = Math.round(currentRate);
        if (valueNode) {
            valueNode.textContent = formatCompactNumber(rounded);
        }
        if (activeNode) {
            activeNode.textContent = formatCompactNumber(this.#readActive(metrics));
        }
        if (queueDepthNode) {
            queueDepthNode.textContent = formatCompactNumber(this.#readQueueDepth(metrics));
        }
        if (pendingLoadsNode) {
            pendingLoadsNode.textContent = formatCompactNumber(this.#readPendingLoads(metrics));
        }
        if (ring) {
            const intensity = currentRate / (currentRate + THROUGHPUT_HALF_SATURATION_RATE);
            ring.style.setProperty('--throughput-arc', `${(intensity * 100).toFixed(2)}%`);
            ring.style.setProperty('--throughput-intensity', intensity.toFixed(3));
        }
    }
}

export { DashboardThroughputController };
export type { DashboardThroughputControllerDependencies };
