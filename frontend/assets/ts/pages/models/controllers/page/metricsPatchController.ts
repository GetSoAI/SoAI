/* SoAI - Models page metrics patch controller [frontend/assets/ts/pages/models/controllers/page/metricsPatchController.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { AnimationFrameRenderQueue } from '@core/animations/renderQueue.ts';
import { toTrustedUiHtml } from '@core/security/public.ts';
import type { ResourceItem } from '@core/data/ClientDataHub.ts';
import { dom } from '@core/dom/dom.ts';
import type { JsonObject } from '@core/types/jsonValues.ts';
import type { ModelData } from '@core/types/modelTypes.ts';
import { optionalModelCardMetricsElement, optionalModelCardStatusElement, optionalModelListFactsElement, optionalModelListStatusElement, queryModelPatchTargets } from '@pages/models/dom.ts';
import { buildMetrics, prepareCardData } from '@pages/models/rendering/cardrenderer/service.ts';
import { buildModelListMetrics } from '@pages/models/rendering/cardrenderer/listRowDetailsWidget.ts';
import type { ModelCardHost } from '@pages/models/rendering/cardrenderer/types.ts';
import { isModelData, normalizeModelRecordStrict } from '@pages/models/controllers/page/state.ts';
import type { PageCollections } from '@core/routing/pages/basepagecollections/PageCollections.ts';
import type { PageDom } from '@core/routing/pages/basepagecore/PageDom.ts';
import type { PageResources } from '@core/routing/pages/basepagecore/PageResources.ts';

interface ModelsMetricsPatchDependencies {
    collections: PageCollections;
    pageDom: PageDom;
    getContainer(): HTMLElement | null;
    getCurrentMetrics(): JsonObject | null;
    cardRenderer: {
        buildClassList(classes: string[] | null | undefined): string;
        buildListStatusContent(model: ModelData, statusLabel: string, statusBadgeClass: string): string;
    };
    updateMetricsBackedStats(): void;
}

interface ModelsMetricsPatchScheduler {
    requestAnimationFrame: (callback: FrameRequestCallback) => number;
    cancelAnimationFrame: (frameId: number) => void;
}

const createModelsMetricsPatchScheduler = (pageResources: PageResources): ModelsMetricsPatchScheduler => ({
    requestAnimationFrame: (callback): number => {
        return pageResources.tracker.requestAnimationFrame(callback);
    },
    cancelAnimationFrame: (frameId): void => {
        pageResources.tracker.cancelAnimationFrame(frameId);
    }
});

class ModelsMetricsPatchController {
    readonly #dependencies: ModelsMetricsPatchDependencies;
    readonly #cardHost: ModelCardHost;
    readonly #renderQueue: AnimationFrameRenderQueue<boolean>;
    #disposed = false;

    constructor(dependencies: ModelsMetricsPatchDependencies, cardHost: ModelCardHost, scheduler: ModelsMetricsPatchScheduler) {
        this.#dependencies = dependencies;
        this.#cardHost = cardHost;
        this.#renderQueue = new AnimationFrameRenderQueue<boolean>({
            label: 'ModelsMetricsPatchController',
            merge: () => true,
            render: () => this.#flush(),
            isDisposed: () => this.#disposed,
            requestAnimationFrame: (callback) => scheduler.requestAnimationFrame(() => callback()),
            cancelAnimationFrame: (frameId) => scheduler.cancelAnimationFrame(frameId)
        });
    }

    queue(): void {
        this.#renderQueue.schedule(true);
    }

    flush(): void {
        this.#flush();
    }

    #flush(): void {
        const collection = this.#dependencies.collections.runtime;
        const container = this.#dependencies.getContainer();
        if (!collection || !this.#dependencies.getCurrentMetrics() || !container || !container.isConnected) {
            return;
        }
        const mountedIdentifiers = new Set<string>();
        for (const element of dom.resolveAll('[data-collection-id]', container)) {
            if (!(element instanceof HTMLElement)) continue;
            const identifier = element.dataset['collectionId'];
            if (identifier) mountedIdentifiers.add(identifier);
        }
        for (const identifier of mountedIdentifiers) {
            const item = collection.find(identifier);
            if (item) this.#patchModel(container, this.#normalizeModelData(item));
        }
        this.#dependencies.updateMetricsBackedStats();
    }

    dispose(): void {
        this.#disposed = true;
        this.#renderQueue.dispose();
    }

    #patchModel(container: Element, model: ModelData): void {
        const cardData = prepareCardData(model, this.#cardHost);
        if (!cardData.cardId) {
            return;
        }
        for (const element of queryModelPatchTargets(container, String(cardData.cardId))) {
            if (element.getAttribute('data-render-mode') === 'list') {
                this.#patchListRow(element, model, cardData.providerName ?? '');
            } else {
                this.#patchCard(element, model, cardData.providerName ?? '');
            }
        }
    }

    #patchListRow(element: Element, model: ModelData, providerName: string): void {
        const metrics = buildMetrics(model, providerName, this.#cardHost);
        const factsElement = optionalModelListFactsElement(element);
        if (factsElement) {
            this.#updateHtmlIfChanged(factsElement, buildModelListMetrics(model, this.#cardHost));
        }
        const statusElement = optionalModelListStatusElement(element);
        if (statusElement) {
            this.#updateHtmlIfChanged(statusElement, this.#dependencies.cardRenderer.buildListStatusContent(model, metrics.statusLabel, metrics.statusBadgeClass));
        }
    }

    #patchCard(element: Element, model: ModelData, providerName: string): void {
        const metrics = buildMetrics(model, providerName, this.#cardHost);
        const metricsElement = optionalModelCardMetricsElement(element);
        if (metricsElement) {
            this.#updateHtmlIfChanged(metricsElement, metrics.metricsMarkup);
        }
        const statusElement = optionalModelCardStatusElement(element);
        if (statusElement) {
            const statusBadgeClass = this.#dependencies.cardRenderer.buildClassList([metrics.statusBadgeClass]);
            const metricStatusBadgeClass = statusBadgeClass ? `ui-metric-badge--${statusBadgeClass}` : '';
            const statusLabel = this.#cardHost.presentation.sanitizeText(metrics.statusLabel);
            this.#updateHtmlIfChanged(statusElement, `<div class="ui-metric-item"><div class="ui-metric-badge ui-metric-badge--status-full ${metricStatusBadgeClass}"><span class="ui-metric-value">${statusLabel}</span></div></div>`);
        }
    }

    #updateHtmlIfChanged(element: Element, markup: string): void {
        if (element.innerHTML === markup) {
            return;
        }
        const trustedMarkup = toTrustedUiHtml(markup);
        this.#dependencies.pageDom.updateHtml(element, trustedMarkup, { escape: false });
    }

    #normalizeModelData(item: ResourceItem): ModelData {
        const model = normalizeModelRecordStrict(item, 'ModelsMetricsPatchController.flush');
        if (!isModelData(model)) {
            throw new TypeError('ModelsMetricsPatchController.flush requires model data with id and name');
        }
        return model;
    }
}

export { ModelsMetricsPatchController, createModelsMetricsPatchScheduler };
