/* SoAI - Metrics page aggregate runtime ownership [frontend/assets/ts/pages/metrics/controllers/page/MetricsPageRuntime.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { PageHost } from '@core/routing/pages/basepagecore/PageHost.ts';
import type { StorageService } from '@core/storage/StorageService.ts';
import { toJsonCompatibleValue } from '@core/primitives/clone.ts';
import { ExportPreviewModal } from '@features/exportpreview/public.ts';
import type { MetricsAdvancedModalHost } from '@features/metrics/public.ts';
import { metricsLogger } from '@pages/metrics/contracts/MetricsPageSupport.ts';
import { fetchMetricsCandlestickHistory, trimMetricsCandlestickData } from '@pages/metrics/controllers/page/adapters.ts';
import { normalizeMetricsIntValue } from '@pages/metrics/controllers/page/constants.ts';
import type { MetricsRuntimeContext, MetricsRuntimeOperations, MetricsRuntimeOwners, MetricsRuntimeServices } from '@pages/metrics/controllers/page/contracts.ts';
import { syncMetricsChartControls } from '@pages/metrics/controllers/page/effects.ts';
import { MetricsLayoutController } from '@pages/metrics/controllers/page/metricsLayoutController.ts';
import { MetricsPageSession } from '@pages/metrics/controllers/page/MetricsPageSession.ts';
import { getMetricsCachedUiElement, resolveMetricsTableBodyContext } from '@pages/metrics/controllers/page/tables.ts';
import { createMetricsPageServices, MetricsDeferredController } from '@pages/metrics/services/runtime.ts';

class MetricsPageRuntime implements MetricsRuntimeContext {
    readonly state: MetricsPageSession;
    readonly owners: MetricsRuntimeOwners;
    readonly metricsServices: MetricsRuntimeServices;
    readonly operations: MetricsRuntimeOperations;
    readonly deferredController: MetricsDeferredController;
    readonly layoutController: MetricsLayoutController;
    readonly advancedModalHost: MetricsAdvancedModalHost;

    constructor(owners: MetricsRuntimeOwners & { storage: StorageService; pageHost: PageHost }) {
        this.owners = owners;
        this.state = new MetricsPageSession(owners.storage);
        const pageServices = createMetricsPageServices({ owners: { pageContext: owners.pageContext, pageElements: owners.pageElements } });
        const exportPreviewModal = new ExportPreviewModal({
            host: {
                modals: owners.services.modals,
                requireHTMLElement: (selector, context) => owners.pageDom.requireHTMLElement(selector, context),
                runWithBoundary: (boundaryKey, task) => owners.pageLifecycle.run(boundaryKey, task),
                addClassName: (target, className) => owners.pageDom.addClass(target, className),
                removeClassName: (target, className) => owners.pageDom.removeClass(target, className),
                updateText: (target, text) => owners.pageDom.updateText(target, text),
                showNotification: (message, type) => owners.feedback.show(message, type)
            }
        });
        this.metricsServices = { ...pageServices, exportPreviewModal };
        this.operations = {
            logger: (level, message, error) => metricsLogger(level, message, error),
            normalizeMetricsInt: (value, min = 1) => normalizeMetricsIntValue(value, min),
            getCachedUI: (id) => getMetricsCachedUiElement(this, id),
            resolveTableBodyContext: (tableId) => resolveMetricsTableBodyContext(this, tableId),
            getDomContext: () => owners.pageHost.getContext(),
            pointBudget: () => this.#resolvePointBudget(),
            requestAnimationFrame: (callback) => owners.pageResources.tracker.requestAnimationFrame(callback),
            cancelAnimationFrame: (frameId) => owners.pageResources.tracker.cancelAnimationFrame(frameId),
            syncChartControls: (options = {}) => syncMetricsChartControls(this, options),
            fetchCandlestickHistory: (options = {}) => fetchMetricsCandlestickHistory(this, options),
            trimCandlestickData: (force = false) => trimMetricsCandlestickData(this, force)
        };
        this.deferredController = new MetricsDeferredController(this);
        this.layoutController = new MetricsLayoutController({
            state: this.state,
            owners: { auth: owners.auth, services: owners.services },
            logger: (level, message, error) => metricsLogger(level, message, error),
            optionalUI: (selector, context) => owners.pageDom.optional(selector, context ?? undefined),
            optionalHTMLElement: (selector, context) => owners.pageDom.optionalHTMLElement(selector, context ?? undefined),
            requireHTMLElement: (selector, context) => owners.pageDom.requireHTMLElement(selector, context ?? undefined),
            replaceElementContent: (target, content, options) => owners.pageDom.replaceContent(target, content, options),
            flushDOMUpdates: () => owners.pageDom.flush(),
            on: (target, event, handler, options) => owners.pageResources.on(target, event, handler, options),
            updateStyle: (element, property, value) => owners.pageDom.updateStyle(element, property, value),
            updateStyles: (element, styles) => owners.pageDom.updateStyles(element, styles),
            applyGridPosition: (element, position) => owners.layout.applyGridPosition(element, position),
            createSection: (id, options) => owners.pageElements.createSection(id, options)
        });
        this.advancedModalHost = {
            getMetricsSnapshot: () => toJsonCompatibleValue(this.state.currentMetrics ?? null),
            getTelemetryStatusSnapshot: () => toJsonCompatibleValue(this.metricsServices.telemetry?.getStatus?.() ?? null)
        };
    }

    #resolvePointBudget(): number {
        if (this.state.currentHistoryPointBudget > 0) return this.state.currentHistoryPointBudget;
        return this.state.chartRuntime.resolvePointBudget({ chart: this.state.mainChart || undefined, maxHistoryPoints: this.state.maxHistoryPoints, historyApiPointCap: this.state.historyApiPointCap });
    }
}

export { MetricsPageRuntime };
