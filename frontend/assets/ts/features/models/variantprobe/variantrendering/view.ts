/* SoAI - Models feature variant result rendering [frontend/assets/ts/features/models/variantprobe/variantrendering/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml, type TrustedHtml } from '@core/security/public.ts';
import { CSS_CLASSES } from '@core/cssConstants.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import type { Sanitizer, SpeedTest, VariantProbeHost, VariantProbeRenderContext } from '@features/models/variantprobe/types.ts';
import { buildVariantCheckEntry } from '@features/models/variantprobe/view.ts';

const VARIANT_ENTRY_SELECTOR = '.variant-check-entry';

const applyVariantCheckerboard = (resultsElement: HTMLElement): void => checkerboardService.applyCheckerboard(resultsElement, VARIANT_ENTRY_SELECTOR);

const buildVariantLoadingMarkup = (message: string): TrustedHtml => uiHtml`<div class="search-loading"><div class="spinner"></div><span>${message}</span></div>`;

const buildVariantAdvisoryMarkup = (message: string): TrustedHtml => uiHtml`<div class="variant-check-advisory variant-check-advisory--warn">${message}</div>`;

const buildVariantErrorMarkup = (message: string | null): TrustedHtml => {
    const statusText = i18n.t('models.modal.addModel.variantCheck.error');
    return buildVariantAdvisoryMarkup(message ? `${statusText} ${message}` : statusText);
};

interface VariantRenderArguments {
    host: VariantProbeHost;
    sanitizer: Sanitizer;
    variants: ModelVariantResponse[];
    selectedIndex: number | null;
    speedTest?: SpeedTest;
    resultsElement: HTMLElement;
    statusElement: Element;
    filterStatusElement: Element;
    emptyMessage: string;
    filterStatusText: string;
    formatDecimal(value: number | null, fractionDigits?: number): string | null;
}

const renderVariantResults = (inputArguments: VariantRenderArguments): void => {
    const renderContext: VariantProbeRenderContext = {
        host: inputArguments.host,
        sanitizer: inputArguments.sanitizer,
        selectedIndex: inputArguments.selectedIndex,
        formatDecimal: inputArguments.formatDecimal,
        ...(inputArguments.speedTest ? { speedTest: inputArguments.speedTest } : {})
    };
    const renderedEntries = inputArguments.variants.map((variant, index) => buildVariantCheckEntry(variant, index, renderContext)).filter(Boolean);
    inputArguments.host.pageDom.updateText(inputArguments.statusElement, i18n.t('models.modal.addModel.variantCheck.complete', { count: renderedEntries.length }));
    inputArguments.host.pageDom.updateText(inputArguments.filterStatusElement, inputArguments.filterStatusText);

    if (renderedEntries.length === 0) {
        inputArguments.host.pageDom.updateHtml(inputArguments.resultsElement, buildVariantAdvisoryMarkup(inputArguments.emptyMessage));
        applyVariantCheckerboard(inputArguments.resultsElement);
        inputArguments.host.pageDom.removeClass(inputArguments.resultsElement, CSS_CLASSES.HIDDEN);
        return;
    }

    const entriesHtml = toTrustedUiHtml(renderedEntries.join(''));
    inputArguments.host.pageDom.updateHtml(inputArguments.resultsElement, entriesHtml);
    applyVariantCheckerboard(inputArguments.resultsElement);
    inputArguments.host.pageDom.removeClass(inputArguments.resultsElement, CSS_CLASSES.HIDDEN);
};

const renderVariantLoading = (inputArguments: { host: VariantProbeHost; resultsElement: HTMLElement; statusElement: Element; filterStatusElement: Element; message: string }): void => {
    inputArguments.host.pageDom.updateText(inputArguments.statusElement, inputArguments.message);
    inputArguments.host.pageDom.updateText(inputArguments.filterStatusElement, '');
    inputArguments.host.pageDom.updateHtml(inputArguments.resultsElement, buildVariantLoadingMarkup(inputArguments.message));
    applyVariantCheckerboard(inputArguments.resultsElement);
    inputArguments.host.pageDom.removeClass(inputArguments.resultsElement, CSS_CLASSES.HIDDEN);
};

const renderVariantError = (inputArguments: { host: VariantProbeHost; resultsElement: HTMLElement; statusElement: Element; filterStatusElement: Element; message: string }): void => {
    inputArguments.host.pageDom.updateText(inputArguments.statusElement, i18n.t('models.modal.addModel.variantCheck.error'));
    inputArguments.host.pageDom.updateText(inputArguments.filterStatusElement, '');
    inputArguments.host.pageDom.updateHtml(inputArguments.resultsElement, buildVariantErrorMarkup(inputArguments.message));
    applyVariantCheckerboard(inputArguments.resultsElement);
    inputArguments.host.pageDom.removeClass(inputArguments.resultsElement, CSS_CLASSES.HIDDEN);
};

export { buildVariantAdvisoryMarkup, buildVariantErrorMarkup, buildVariantLoadingMarkup, renderVariantError, renderVariantLoading, renderVariantResults };
