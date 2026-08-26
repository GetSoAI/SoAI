/* SoAI - Models page DOM contracts [frontend/assets/ts/pages/models/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { buildModelsFilters, buildModelsHeader, buildModelsSections } from '@pages/models/adapters/adapters.ts';
import { GRID_ID } from '@pages/models/contracts/constants.ts';
import type { ModelsLayoutViewHost, ModelsUiRefs } from '@pages/models/types.ts';
import type { PageDomOwnerHost } from '@core/routing/pages/basepagecore/PageDom.ts';

const MODEL_LIST_FACTS_SELECTOR = '.models-list-metrics-facts';
const MODEL_LIST_STATUS_SELECTOR = '.models-list-status';
const MODEL_CARD_METRICS_SELECTOR = '.model-metrics-display';
const MODEL_CARD_STATUS_SELECTOR = '.model-metrics-status';

type ModelsLayoutDom = {
    header: ReturnType<typeof buildModelsHeader>;
    sections: ReturnType<typeof buildModelsSections>;
    filters: ReturnType<typeof buildModelsFilters>;
};

const buildModelPatchTargetSelector = (cardId: string): string => {
    return `[data-model="${CSS.escape(cardId)}"]`;
};

export const requireModelsUi = (dependencies: PageDomOwnerHost): ModelsUiRefs => {
    const root = dependencies.pageDom.requireHTMLElement('[data-section="models"]');
    const grid = dependencies.pageDom.requireHTMLElement(`#${GRID_ID}`, root);
    const listBody = dependencies.pageDom.requireHTMLElement('#models-list-body', root);
    const viewModeToggleButton = dependencies.pageDom.requireHTMLElement('#models-view-mode-toggle', root);
    if (!(viewModeToggleButton instanceof HTMLButtonElement)) {
        throw new TypeError('Models view mode toggle must be a button');
    }
    return { root, grid, listBody, viewModeToggleButton };
};

export const optionalModelsRoot = (dependencies: PageDomOwnerHost): HTMLElement | null => {
    return dependencies.pageDom.optionalHTMLElement('[data-section="models"]');
};

export const requireModelsRoot = (dependencies: PageDomOwnerHost): HTMLElement => {
    return dependencies.pageDom.requireHTMLElement('[data-section="models"]');
};

export const queryModelPatchTargets = (container: Element, cardId: string): Element[] => {
    return dom.resolveAll(buildModelPatchTargetSelector(cardId), container);
};

export const optionalModelListFactsElement = (container: Element): Element | null => {
    return dom.resolve(MODEL_LIST_FACTS_SELECTOR, container);
};

export const optionalModelListStatusElement = (container: Element): Element | null => {
    return dom.resolve(MODEL_LIST_STATUS_SELECTOR, container);
};

export const optionalModelCardMetricsElement = (container: Element): Element | null => {
    return dom.resolve(MODEL_CARD_METRICS_SELECTOR, container);
};

export const optionalModelCardStatusElement = (container: Element): Element | null => {
    return dom.resolve(MODEL_CARD_STATUS_SELECTOR, container);
};

export const buildModelsLayoutDom = (page: ModelsLayoutViewHost): ModelsLayoutDom => {
    return {
        header: buildModelsHeader(page),
        sections: buildModelsSections(page),
        filters: buildModelsFilters()
    };
};
