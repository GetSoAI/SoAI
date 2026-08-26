/* SoAI - Models feature constituent picker DOM contracts [frontend/assets/ts/features/models/modals/virtualmodelsmodal/constituentpicker/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiSelector } from '@core/modals/uiIds.ts';
import { toTrimmedStringOrNull } from '@core/normalize.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import type { ModelRecord } from '@core/types/modelTypes.ts';
import type { VirtualModelsHost } from '@features/models/modals/virtualmodelsmodal/virtualModelsManagerTypes.ts';

interface ConstituentPickerDependencies {
    host: VirtualModelsHost;
    modalId: string;
    token: string;
    modalRoot: Element;
    requireAllModels: () => ModelRecord[];
}

interface ConstituentEntry {
    universalId: string;
    label: string;
    typeLabel: string;
    pluginLabel: string;
    haystack: string;
}

const ATTR_QUERY = 'data-search-query';
const CONSTITUENT_CARD_SELECTOR = '.search-item--card';

const resolveTarget = <T extends Element>(host: VirtualModelsHost, modalId: string, token: string, suffix: string, modalRoot: Element, predicate: (element: Element) => element is T): T => {
    const selector = suffix ? modalUiSelector(modalId, `${token}-${suffix}`) : modalUiSelector(modalId, token);
    const element = host.view.requireHTMLElement(selector, modalRoot);
    if (!predicate(element)) {
        throw new TypeError(`Constituent picker target ${selector} has unexpected element type`);
    }
    return element;
};

const isHTMLSelectElement = (element: Element): element is HTMLSelectElement => element instanceof HTMLSelectElement;
const isHTMLInputElement = (element: Element): element is HTMLInputElement => element instanceof HTMLInputElement;
const isHTMLButtonElement = (element: Element): element is HTMLButtonElement => element instanceof HTMLButtonElement;
const isHTMLDivElement = (element: Element): element is HTMLDivElement => element instanceof HTMLDivElement;

const buildEntries = (models: ModelRecord[]): ConstituentEntry[] => {
    const entries: ConstituentEntry[] = [];
    for (const model of models) {
        if (model.type === 'virtual') continue;
        const universalId = toTrimmedStringOrNull(model.universalId) || '';
        if (!universalId) continue;
        const label = model.displayName || model.alias || model.name || model.id || universalId;
        const typeLabel = toTrimmedStringOrNull(model.type) || '';
        const pluginLabel = toTrimmedStringOrNull(model['plugin']) || '';
        const haystack = `${label} ${universalId} ${typeLabel} ${pluginLabel}`.toLowerCase();
        entries.push({ universalId, label, typeLabel, pluginLabel, haystack });
    }
    return entries;
};

const buildCard = (entry: ConstituentEntry, isSelected: boolean, host: VirtualModelsHost): string => {
    const sanitizer = host.view.sanitizer;
    const labelSafe = sanitizer.html(entry.label);
    const labelAttribute = sanitizer.attribute(entry.label);
    const idSafe = sanitizer.html(entry.universalId);
    const badge = entry.typeLabel ? `<span class="search-item-badge">${sanitizer.html(entry.typeLabel)}</span>` : '';
    const pluginLine = entry.pluginLabel ? `<div class="u-text-muted">${sanitizer.html(entry.pluginLabel)}</div>` : '';
    const titleHtml = entry.label.includes('/')
        ? (() => {
              const parts = entry.label.split('/');
              const author = parts[0] || '';
              const rest = parts.slice(1).join('/');
              return `<span class="search-item-author">${sanitizer.html(author)}</span><span class="search-item-separator">/</span><span class="search-item-model">${sanitizer.html(rest)}</span>`;
          })()
        : `<span class="search-item-model">${labelSafe}</span>`;
    const stateClass = isSelected ? ' is-selected' : '';
    return `<button type="button" class="search-item search-item--card${stateClass}" data-constituent-id="${sanitizer.attribute(entry.universalId)}" aria-label="${labelAttribute}" data-tooltip="${labelAttribute}" aria-pressed="${isSelected ? 'true' : 'false'}"><span class="search-item-content"><div class="search-item-header"><span class="search-item-title">${titleHtml}</span>${badge}</div><div class="search-item-description">${idSafe}</div>${pluginLine}</span></button>`;
};

const renderCards = (dependencies: ConstituentPickerDependencies, store: HTMLSelectElement, results: HTMLDivElement, query: string): void => {
    const allEntries = buildEntries(dependencies.requireAllModels());
    const selectedIds = new Set(
        Array.from(store.options)
            .filter((option) => option.selected)
            .map((option) => option.value)
    );
    const normalizedQuery = query.trim().toLowerCase();
    const filtered = allEntries.filter((entry) => selectedIds.has(entry.universalId) || !normalizedQuery || entry.haystack.includes(normalizedQuery));
    if (!filtered.length) {
        const emptyMessage = uiHtml`<div class="constituent-empty">${i18n.t('models.modal.virtualModels.searchEmpty')}</div>`;
        dependencies.host.view.updateHTML(results, emptyMessage);
        checkerboardService.applyCheckerboard(results, CONSTITUENT_CARD_SELECTOR);
        return;
    }
    const html = filtered.map((entry) => buildCard(entry, selectedIds.has(entry.universalId), dependencies.host)).join('');
    const cardsMarkup = toTrustedUiHtml(html);
    dependencies.host.view.updateHTML(results, cardsMarkup);
    checkerboardService.applyCheckerboard(results, CONSTITUENT_CARD_SELECTOR);
};

const ensureStoreOptions = (dependencies: ConstituentPickerDependencies, store: HTMLSelectElement, preserveIds?: string[]): void => {
    const allEntries = buildEntries(dependencies.requireAllModels());
    const previousSelected = preserveIds
        ? new Set(preserveIds)
        : new Set(
              Array.from(store.options)
                  .filter((option) => option.selected)
                  .map((option) => option.value)
          );
    while (store.firstChild) {
        store.removeChild(store.firstChild);
    }
    for (const entry of allEntries) {
        const option = store.ownerDocument.createElement('option');
        option.value = entry.universalId;
        option.textContent = entry.label;
        if (previousSelected.has(entry.universalId)) {
            option.selected = true;
        }
        store.appendChild(option);
    }
};

const renderConstituentPicker = (dependencies: ConstituentPickerDependencies, selectedIds?: string[]): void => {
    const store = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, '', dependencies.modalRoot, isHTMLSelectElement);
    const results = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, 'results', dependencies.modalRoot, isHTMLDivElement);
    ensureStoreOptions(dependencies, store, selectedIds);
    const picker = results.closest('[data-constituent-picker]');
    if (picker instanceof HTMLElement) {
        picker.removeAttribute(ATTR_QUERY);
    }
    const searchInput = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, 'search', dependencies.modalRoot, isHTMLInputElement);
    searchInput.value = '';
    renderCards(dependencies, store, results, '');
};

const attachConstituentPicker = (dependencies: ConstituentPickerDependencies): void => {
    const results = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, 'results', dependencies.modalRoot, isHTMLDivElement);
    const store = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, '', dependencies.modalRoot, isHTMLSelectElement);
    const searchInput = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, 'search', dependencies.modalRoot, isHTMLInputElement);
    const searchButton = resolveTarget(dependencies.host, dependencies.modalId, dependencies.token, 'search-button', dependencies.modalRoot, isHTMLButtonElement);
    const picker = results.closest('[data-constituent-picker]');
    if (!(picker instanceof HTMLElement)) {
        throw new Error('Constituent picker root is missing');
    }
    if (picker.dataset['constituentPickerBound']) return;
    picker.dataset['constituentPickerBound'] = 'true';
    const rerender = (): void => renderCards(dependencies, store, results, picker.getAttribute(ATTR_QUERY) || '');
    dependencies.host.data.on(results, 'click', (event: Event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const card = target.closest('[data-constituent-id]');
        if (!(card instanceof HTMLElement)) return;
        const id = card.getAttribute('data-constituent-id');
        if (!id) {
            throw new Error('Constituent picker card requires data-constituent-id');
        }
        const option = Array.from(store.options).find((candidate) => candidate.value === id);
        if (!option) {
            throw new Error(`Constituent picker option missing for ${id}`);
        }
        option.selected = !option.selected;
        store.dispatchEvent(new Event('change', { bubbles: true }));
        rerender();
    });
    dependencies.host.data.on(searchInput, 'input', () => {
        picker.setAttribute(ATTR_QUERY, searchInput.value);
        rerender();
    });
    dependencies.host.data.on(searchButton, 'click', () => {
        picker.setAttribute(ATTR_QUERY, searchInput.value);
        rerender();
    });
};

export { attachConstituentPicker, renderConstituentPicker };
export type { ConstituentPickerDependencies };
