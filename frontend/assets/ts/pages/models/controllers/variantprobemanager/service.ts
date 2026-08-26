/* SoAI - Models page variant probe manager service [frontend/assets/ts/pages/models/controllers/variantprobemanager/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { CSS_CLASSES } from '@core/cssConstants.ts';
import type { ModelVariantResponse } from '@core/api/contracts/modelVariantContracts.ts';
import { readTrimmedInputValue, readTrimmedSelectValue } from '@core/dom/formValues.ts';
import { i18n } from '@core/i18n/index.ts';
import { formatInvariantNumber } from '@core/localization/public.ts';
import { toTrimmedString } from '@core/normalize.ts';
import { isNumber } from '@core/typeGuards.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import type { Sanitizer } from '@pages/models/contracts/modelsPageTypes.ts';
import { buildVariantProbeErrorMessage } from '@pages/models/controllers/variantprobemanager/varianterrors/mappers.ts';
import { filterVariants } from '@pages/models/controllers/variantprobemanager/variantfiltering/service.ts';
import { highlightVariantProbeSelection, selectVariantProbeEntry, type VariantProbeSelectionContext } from '@pages/models/controllers/variantprobemanager/variantProbeSelectionManager.ts';
import type { VariantProbeDependencies, VariantProbeHost } from '@pages/models/controllers/variantprobemanager/types.ts';
import { renderVariantError, renderVariantLoading, renderVariantResults } from '@pages/models/controllers/variantprobemanager/variantrendering/view.ts';
import { resolveVariantEmptyMessage, resolveVariantFilterStatusText } from '@pages/models/controllers/variantprobemanager/variantresulttext/mappers.ts';

class VariantProbeManager {
    readonly #host: VariantProbeHost;
    readonly #sanitizer: Sanitizer;
    readonly #speedTest: VariantProbeDependencies['speedTest'];
    readonly #modalId: string;
    readonly #modalRoot: Element;
    allResults: ModelVariantResponse[];
    results: ModelVariantResponse[];
    selectedIndex: number | null;
    selectedVariant: ModelVariantResponse | null;
    filterEnabled: boolean;
    busy: boolean;
    token: symbol | null;

    constructor({ host, speedTest, modalId, modalRoot }: VariantProbeDependencies & { modalId: string; modalRoot: Element }) {
        if (!host) throw new Error('VariantProbeManager requires a host instance');
        if (!host.sanitizer) throw new Error('VariantProbeManager requires a sanitizer');
        if (!toTrimmedString(modalId)) throw new Error('VariantProbeManager requires a modalId');
        if (!(modalRoot instanceof Element)) throw new Error('VariantProbeManager requires a modalRoot');
        this.#host = host;
        this.#sanitizer = host.sanitizer;
        this.#speedTest = speedTest;
        this.#modalId = modalId;
        this.#modalRoot = modalRoot;
        this.allResults = [];
        this.results = [];
        this.selectedIndex = null;
        this.selectedVariant = null;
        this.filterEnabled = false;
        this.busy = false;
        this.token = null;
    }

    #requireUiElement(token: string): Element {
        const results = this.#host.pageDom.query(modalUiSelector(this.#modalId, token), this.#modalRoot);
        const first = results.length > 0 ? results[0] : null;
        if (first) return first;
        throw new Error(`Variant probe requires ${token} element`);
    }

    #requireHTMLElement(token: string): HTMLElement {
        const element = this.#requireUiElement(token);
        if (element instanceof HTMLElement) return element;
        throw new TypeError(`Variant probe requires ${token} to resolve to an HTMLElement`);
    }

    #requireSelect(token: string): HTMLSelectElement {
        const element = this.#requireUiElement(token);
        if (element instanceof HTMLSelectElement) return element;
        throw new TypeError(`Variant probe requires ${token} to resolve to an HTMLSelectElement`);
    }

    #requireInput(token: string): HTMLInputElement {
        const element = this.#requireUiElement(token);
        if (element instanceof HTMLInputElement) return element;
        throw new TypeError(`Variant probe requires ${token} to resolve to an HTMLInputElement`);
    }

    reset(): void {
        this.token = null;
        this.busy = false;
        this.allResults = [];
        this.results = [];
        this.selectedIndex = null;
        this.selectedVariant = null;
        this.resetVariantFilter();
        this.#host.pageDom.updateText(this.#requireUiElement('model-variant-status'), '');
        this.#host.pageDom.updateText(this.#requireUiElement('model-variant-filter-status'), '');
        const resultsElement = this.#requireHTMLElement('model-variant-results');
        this.#host.pageDom.addClass(resultsElement, CSS_CLASSES.HIDDEN);
        this.#host.pageDom.updateHtml(resultsElement, '');
    }

    resetVariantFilter(): void {
        this.filterEnabled = false;
        const group = this.#requireHTMLElement('variant-search-group');
        const input = this.#requireInput('variant-search-input');
        const button = this.#requireHTMLElement('variant-search-button');
        this.#host.pageDom.addClass(group, CSS_CLASSES.HIDDEN);
        this.#host.setUIValue(input, '', { attribute: 'value' });
        this.#host.pageDom.updateProperty(button, 'disabled', true);
    }

    enableVariantFilter(): void {
        this.filterEnabled = true;
        const group = this.#requireHTMLElement('variant-search-group');
        this.#host.pageDom.removeClass(group, CSS_CLASSES.HIDDEN);
        this.updateVariantFilterButtonState();
    }

    updateVariantFilterButtonState(): void {
        const button = this.#requireHTMLElement('variant-search-button');
        this.#host.pageDom.updateProperty(button, 'disabled', !this.filterEnabled || this.busy || this.allResults.length === 0);
    }

    applyVariantFilter(): void {
        if (!this.filterEnabled || this.busy || this.allResults.length === 0) {
            return;
        }
        this.renderFilteredResults();
    }

    updateButtonState(): void {
        const button = this.#requireHTMLElement('model-variant-check');
        const plugin = readTrimmedSelectValue(this.#requireSelect('download-plugin-select'));
        const modelId = readTrimmedInputValue(this.#requireInput('model-id'));
        this.#host.pageDom.updateProperty(button, 'disabled', !(Boolean(plugin && modelId) && !this.busy));
    }

    prepareForProbe(): symbol {
        this.reset();
        this.busy = true;
        this.token = Symbol('variantProbe');
        this.updateButtonState();
        return this.token;
    }

    showCheckingStatus(): void {
        const checkingText = i18n.t('models.modal.addModel.variantCheck.checking');
        renderVariantLoading({
            host: this.#host,
            resultsElement: this.#requireHTMLElement('model-variant-results'),
            statusElement: this.#requireUiElement('model-variant-status'),
            filterStatusElement: this.#requireUiElement('model-variant-filter-status'),
            message: checkingText
        });
    }

    isTokenActive(candidate: symbol): boolean {
        return this.token === candidate;
    }

    handleSuccess(token: symbol, variants: ModelVariantResponse[]): void {
        if (!this.isTokenActive(token)) return;
        this.token = null;
        this.busy = false;
        this.updateButtonState();
        this.renderResults(variants);
        this.updateVariantFilterButtonState();
    }

    handleFailure(token: symbol, message: string): void {
        if (!this.isTokenActive(token)) return;
        this.token = null;
        this.busy = false;
        this.updateButtonState();
        this.renderError(message);
        this.updateVariantFilterButtonState();
    }

    buildErrorMessage(error: Error): string | null {
        return buildVariantProbeErrorMessage(error);
    }

    renderResults(variants: ModelVariantResponse[]): void {
        this.allResults = variants.slice();
        this.results = this.resolveVisibleResults();
        this.selectedIndex = null;
        this.selectedVariant = null;
        this.renderVisibleResults();
    }

    renderFilteredResults(): void {
        this.results = this.resolveVisibleResults();
        if (this.selectedVariant !== null) {
            const selectedIndex = this.results.indexOf(this.selectedVariant);
            this.selectedIndex = selectedIndex >= 0 ? selectedIndex : null;
            if (this.selectedIndex === null) {
                this.selectedVariant = null;
            }
        }
        this.renderVisibleResults();
    }

    resolveVisibleResults(): ModelVariantResponse[] {
        if (!this.filterEnabled) {
            return this.allResults.slice();
        }
        return filterVariants(this.allResults, this.#requireInput('variant-search-input').value);
    }

    renderVisibleResults(): void {
        const resultsElement = this.#requireHTMLElement('model-variant-results');
        const query = this.filterEnabled ? this.#requireInput('variant-search-input').value : '';
        const textInput = { allCount: this.allResults.length, visibleCount: this.results.length, filterEnabled: this.filterEnabled, query };
        renderVariantResults({
            host: this.#host,
            sanitizer: this.#sanitizer,
            variants: this.results,
            selectedIndex: this.selectedIndex,
            resultsElement,
            statusElement: this.#requireUiElement('model-variant-status'),
            filterStatusElement: this.#requireUiElement('model-variant-filter-status'),
            emptyMessage: resolveVariantEmptyMessage(textInput),
            filterStatusText: resolveVariantFilterStatusText(textInput),
            formatDecimal: (value: number | null, fractionDigits?: number) => this.formatDecimal(value, fractionDigits),
            ...(this.#speedTest ? { speedTest: this.#speedTest } : {})
        });
        this.highlightSelection();
    }

    renderError(message: string): void {
        this.allResults = [];
        this.results = [];
        this.selectedIndex = null;
        this.selectedVariant = null;
        renderVariantError({
            host: this.#host,
            resultsElement: this.#requireHTMLElement('model-variant-results'),
            statusElement: this.#requireUiElement('model-variant-status'),
            filterStatusElement: this.#requireUiElement('model-variant-filter-status'),
            message
        });
    }

    handleEntryClick(event: Event | null, element: Element | null): boolean {
        event?.preventDefault();
        return this.selectEntry(element);
    }

    handleEntryKeydown(event: KeyboardEvent | null, element: Element | null): boolean {
        if (event && (event.key === 'Enter' || event.key === ' ')) {
            event.preventDefault();
            return this.selectEntry(element);
        }
        return false;
    }

    selectEntry(element: Element | null): boolean {
        const selected = selectVariantProbeEntry(element, this.#selectionContext());
        if (!selected) return false;
        this.selectedIndex = selected.selectedIndex;
        this.selectedVariant = selected.selectedVariant;
        this.highlightSelection();
        return true;
    }

    highlightSelection(): void {
        highlightVariantProbeSelection(this.#selectionContext(), this.selectedIndex);
    }

    #selectionContext(): VariantProbeSelectionContext {
        return {
            host: this.#host,
            requireInput: (token) => this.#requireInput(token),
            requireUiElement: (token) => this.#requireUiElement(token),
            results: this.results
        };
    }

    formatDecimal(value: number | null, fractionDigits: number = 2): string | null {
        if (!isNumber(value) || !Number.isFinite(value)) return null;
        return formatInvariantNumber(value, { maximumFractionDigits: fractionDigits, minimumFractionDigits: 0 });
    }
}

export { VariantProbeManager };
