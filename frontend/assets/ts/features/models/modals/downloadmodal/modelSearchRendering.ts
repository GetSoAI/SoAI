/* SoAI - Models feature model search rendering [frontend/assets/ts/features/models/modals/downloadmodal/modelSearchRendering.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { optionalNonNegativeIntegerDataAttribute } from '@core/dom/attributes.ts';
import { i18n } from '@core/i18n/index.ts';
import { toString, toTrimmedString } from '@core/normalize.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { scrollElementIntoView } from '@core/scroll.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { SanitizerApi } from '@core/pagecontext/contracts.ts';
import type { DownloadModalHost } from '@features/models/modals/downloadmodal/downloadModalTypes.ts';
import type { ModelSearchResult, ModelSearchResults } from '@features/models/modals/downloadmodal/modelSearchTypes.ts';

type Sanitizer = Pick<SanitizerApi, 'attribute' | 'html'>;
const MODEL_SEARCH_CARD_SELECTOR = '.search-item--card';

const applyModelSearchCheckerboard = (container: Element): void => checkerboardService.applyCheckerboard(container, MODEL_SEARCH_CARD_SELECTOR);

const requireContainer = (host: DownloadModalHost, modalId: string, modalRoot: Element): Element => {
    return host.session.requireUI(modalUiSelector(modalId, 'model-search-results'), modalRoot);
};

export const renderModelSearchLoading = (inputArguments: { host: DownloadModalHost; sanitizer: Sanitizer; modalId: string; modalRoot: Element }): void => {
    const container = requireContainer(inputArguments.host, inputArguments.modalId, inputArguments.modalRoot);
    inputArguments.host.view.updateHTML(container, uiHtml`<div class="search-loading"><div class="spinner"></div><span>${i18n.t('models.modal.addModel.searchLoading')}</span></div>`);
    applyModelSearchCheckerboard(container);
    inputArguments.host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
    const loadingElement = inputArguments.host.view.optionalUI('.search-loading', container);
    if (loadingElement) {
        scrollElementIntoView(loadingElement, { behavior: 'smooth', block: 'start' });
    }
};

export const renderModelSearchEmpty = (inputArguments: { host: DownloadModalHost; sanitizer: Sanitizer; modalId: string; modalRoot: Element }): void => {
    const container = requireContainer(inputArguments.host, inputArguments.modalId, inputArguments.modalRoot);
    const iconMarkup = inputArguments.host.session.getIconSync('search', { size: 32, strokeWidth: 1.5 });
    const iconSlot = uiHtml`<div class="no-results-icon">${iconMarkup}</div>`;
    inputArguments.host.view.updateHTML(container, uiHtml`<div class="no-results">${iconSlot}<h3>${i18n.t('models.modal.addModel.searchNoResults')}</h3></div>`);
    applyModelSearchCheckerboard(container);
    inputArguments.host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
};

export const renderModelSearchError = (inputArguments: { host: DownloadModalHost; sanitizer: Sanitizer; message: string | null; modalId: string; modalRoot: Element }): void => {
    const container = requireContainer(inputArguments.host, inputArguments.modalId, inputArguments.modalRoot);
    const detail = inputArguments.message || i18n.t('models.modal.addModel.searchError');
    inputArguments.host.view.updateHTML(container, uiHtml`<div class="form-disclaimer form-disclaimer-error">${detail}</div>`);
    applyModelSearchCheckerboard(container);
    inputArguments.host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
};

const buildModelSearchEntry = (inputArguments: { sanitizer: Sanitizer; entry: ModelSearchResult; index: number }): string => {
    const entryObject = inputArguments.entry;
    const name = toTrimmedString(entryObject['name']) || toTrimmedString(entryObject['id']) || i18n.t('models.types.unknown');
    const summary = toTrimmedString(entryObject['summary']) || i18n.t('models.modal.addModel.searchResultSummaryFallback');
    const sourceValue = toTrimmedString(entryObject['source']);
    const metas: string[] = [];
    if (sourceValue) {
        const sourceLabel = toTrimmedString(i18n.t('models.modal.addModel.searchResultSource', { source: sourceValue }));
        if (sourceLabel) metas.push(sourceLabel);
    }
    const variants = entryObject['variants'];
    const vCount = Array.isArray(variants) ? variants.length : 0;
    const vLabel = toTrimmedString(i18n.t('models.modal.addModel.searchResultVariants', { count: vCount }));
    if (vLabel) metas.push(vLabel);
    const metaHtml = metas.length ? `<div class="u-text-muted">${inputArguments.sanitizer.html(metas.join(' | '))}</div>` : '';
    let titleHtml: string;
    if (name.includes('/')) {
        const parts = name.split('/');
        const model = parts.slice(1).join('/');
        const firstPart = parts[0] || '';
        const trimmedFirst = toTrimmedString(firstPart);
        titleHtml = `<span class="search-item-author">${inputArguments.sanitizer.html(trimmedFirst || firstPart)}</span><span class="search-item-separator">/</span><span class="search-item-model">${inputArguments.sanitizer.html(toTrimmedString(model) || model)}</span>`;
    } else {
        titleHtml = `<span class="search-item-model">${inputArguments.sanitizer.html(name)}</span>`;
    }
    const descHtml = summary ? `<div class="search-item-description">${inputArguments.sanitizer.html(summary)}</div>` : '';
    const type = toTrimmedString(entryObject['type']);
    const badgeHtml = type ? `<span class="search-item-badge">${inputArguments.sanitizer.html(type)}</span>` : '';
    const indexAttr = inputArguments.sanitizer.attribute(toString(inputArguments.index));
    const labelAttr = inputArguments.sanitizer.attribute(summary);
    return `<button type="button" class="search-item search-item--card" data-result-index="${indexAttr}" data-tooltip="${labelAttr}" aria-label="${labelAttr}"><span class="search-item-content"><div class="search-item-header"><span class="search-item-title">${titleHtml}</span>${badgeHtml}</div>${descHtml}${metaHtml}</span></button>`;
};

export const highlightModelSearchSelection = (inputArguments: { host: DownloadModalHost; selectedIndex: number | null; modalId: string; modalRoot: Element }): void => {
    const container = requireContainer(inputArguments.host, inputArguments.modalId, inputArguments.modalRoot);
    const selectedIndex = inputArguments.selectedIndex;
    inputArguments.host.view.queryUI('.search-item', container).forEach((item) => {
        const itemIndex = optionalNonNegativeIntegerDataAttribute(item, 'result-index', 'Model search item');
        inputArguments.host.view.toggleClassName(item, 'search-item-hover', itemIndex === selectedIndex);
    });
};

export const renderModelSearchResults = (inputArguments: { host: DownloadModalHost; sanitizer: Sanitizer; results: ModelSearchResults; selectedIndex: number | null; modalId: string; modalRoot: Element }): void => {
    const container = requireContainer(inputArguments.host, inputArguments.modalId, inputArguments.modalRoot);
    const entries = inputArguments.results;
    if (!entries.length) {
        renderModelSearchEmpty({ host: inputArguments.host, sanitizer: inputArguments.sanitizer, modalId: inputArguments.modalId, modalRoot: inputArguments.modalRoot });
        return;
    }
    const html = entries
        .map((entry, index) => buildModelSearchEntry({ sanitizer: inputArguments.sanitizer, entry, index }))
        .filter(Boolean)
        .join('');
    const searchResultsMarkup = toTrustedUiHtml(html);
    inputArguments.host.view.updateHTML(container, searchResultsMarkup);
    applyModelSearchCheckerboard(container);
    inputArguments.host.view.removeClassName(container, CSS_CLASSES.HIDDEN);
    highlightModelSearchSelection({ host: inputArguments.host, selectedIndex: inputArguments.selectedIndex, modalId: inputArguments.modalId, modalRoot: inputArguments.modalRoot });
};
