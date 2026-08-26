/* SoAI - Plugins feature GPU binding selector [frontend/assets/ts/features/plugins/modals/config/gpuBindingSelector.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { toTrustedUiHtml } from '@core/security/public.ts';
import { checkerboardService } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { toTrimmedLower } from '@core/normalize.ts';
import { uiAttr, uiHtml } from '@core/security/uiHtml.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createPluginGpuBindingConfigValue, PLUGIN_GPU_ALL_ID, PLUGIN_GPU_BINDING_KEY, type PluginGpuBindingEntry, type PluginGpuBindingSelectorState } from '@features/plugins/modals/config/gpuBindingTypes.ts';
import type { ConfigManagerHost, ConfigurationManager, SecurityService } from '@features/plugins/modals/config/types.ts';

interface PluginGpuBindingSelectorTargets {
    root: HTMLElement;
    searchInput: HTMLInputElement;
    searchButton: HTMLButtonElement;
    memoryCounter: HTMLElement;
    results: HTMLDivElement;
    store: HTMLSelectElement;
}

interface BindPluginGpuBindingSelectorListenersOptions {
    host: ConfigManagerHost;
    form: HTMLElement;
    security: SecurityService;
    state: PluginGpuBindingSelectorState | null;
    manager: ConfigurationManager;
    onValueChanged: (key: string) => void;
}

const PLUGIN_GPU_QUERY_ATTR = 'data-plugin-gpu-query';
const PLUGIN_GPU_CARD_SELECTOR = '.plugin-gpu-binding-card';

const selectedIdSet = (selectedIds: readonly string[]): Set<string> => new Set(selectedIds.length > 0 ? selectedIds : [PLUGIN_GPU_ALL_ID]);

const hasSpecificPluginGpuSelection = (selectedIds: Set<string>): boolean => Array.from(selectedIds).some((id) => id !== PLUGIN_GPU_ALL_ID);

const renderPluginGpuBindingCard = (entry: PluginGpuBindingEntry, selectedIds: Set<string>, security: SecurityService): string => {
    const isSelected = selectedIds.has(entry.id);
    const isAllUnavailable = entry.id === PLUGIN_GPU_ALL_ID && hasSpecificPluginGpuSelection(selectedIds);
    const selectedClass = isSelected ? ' is-selected' : '';
    const unavailableClass = isAllUnavailable ? ' is-unavailable' : '';
    const labelAttr = security.escapeAttribute(entry.label);
    const keyAttr = security.escapeAttribute(PLUGIN_GPU_BINDING_KEY);
    return `<button type="button" class="search-item search-item--card plugin-gpu-binding-card setting-change-surface${selectedClass}${unavailableClass}" data-config-key="${keyAttr}" data-plugin-gpu-id="${security.escapeAttribute(entry.id)}" aria-label="${labelAttr}" data-tooltip="${labelAttr}" aria-pressed="${isSelected ? 'true' : 'false'}" aria-disabled="${isAllUnavailable ? 'true' : 'false'}"><span class="search-item-content"><div class="search-item-header"><span class="search-item-title"><span class="search-item-model">${security.escapeHtml(entry.label)}</span></span><span class="search-item-badge plugin-gpu-binding-badge plugin-gpu-binding-badge--${entry.badgeTone}">${security.escapeHtml(entry.badge)}</span></div><div class="search-item-description">${security.escapeHtml(entry.description)}</div><div class="u-text-muted plugin-gpu-binding-detail">${security.escapeHtml(entry.detail)}</div></span></button>`;
};

const renderPluginGpuBindingCards = (entries: readonly PluginGpuBindingEntry[], selectedIds: Set<string>, query: string, security: SecurityService): string => {
    const normalizedQuery = toTrimmedLower(query);
    return entries
        .filter((entry) => entry.id === PLUGIN_GPU_ALL_ID || selectedIds.has(entry.id) || normalizedQuery.length === 0 || entry.haystack.includes(normalizedQuery))
        .map((entry) => renderPluginGpuBindingCard(entry, selectedIds, security))
        .join('');
};

const renderPluginGpuBindingStoreOptions = (state: PluginGpuBindingSelectorState, security: SecurityService): string => {
    const selectedIds = selectedIdSet(state.selectedIds);
    return state.entries.map((entry) => `<option value="${security.escapeAttribute(entry.id)}"${selectedIds.has(entry.id) ? ' selected' : ''}>${security.escapeHtml(entry.label)}</option>`).join('');
};

const calculatePluginGpuBindingMemoryGb = (entries: readonly PluginGpuBindingEntry[], selectedIds: Set<string>): number => {
    const selectedGpuEntries = entries.filter((entry) => entry.id !== PLUGIN_GPU_ALL_ID && selectedIds.has(entry.id));
    const countedEntries = selectedGpuEntries.length > 0 ? selectedGpuEntries : entries.filter((entry) => entry.id !== PLUGIN_GPU_ALL_ID);
    return countedEntries.reduce((total, entry) => total + entry.memoryTotalGb, 0);
};

const formatPluginGpuBindingMemory = (entries: readonly PluginGpuBindingEntry[], selectedIds: Set<string>): string => {
    const memoryTotalGb = calculatePluginGpuBindingMemoryGb(entries, selectedIds);
    const memory = i18n.formatNumber(memoryTotalGb, { maximumFractionDigits: 1 });
    return i18n.t('plugins.modal.config.gpuMemoryCounter', { memory });
};

const renderPluginGpuBindingSelector = (state: PluginGpuBindingSelectorState | null, security: SecurityService): string => {
    if (!state) {
        return '';
    }
    const selectedIds = selectedIdSet(state.selectedIds);
    const searchLabel = i18n.t('plugins.modal.config.gpuSearchButton');
    const searchIcon = getIconSync('search', { size: 16, strokeWidth: 1.5 });
    return uiHtml`
        <section class="plugin-gpu-binding-selector" data-plugin-gpu-binding-selector>
            <div class="plugin-gpu-binding-header">
                <label class="plugin-config-section-label plugin-gpu-binding-title">${i18n.t('plugins.modal.config.gpuBindingTitle')}</label>
                <span class="plugin-gpu-binding-memory-counter" data-plugin-gpu-memory-counter>${formatPluginGpuBindingMemory(state.entries, selectedIds)}</span>
            </div>
            <div class="form-row-split form-row-split--plugin-gpu-search">
                <div class="form-col-main">
                    <div class="searchbar-container searchbar-container--collection">
                        <input type="text" class="form-input searchbar-input plugin-gpu-binding-search" placeholder="${uiAttr(i18n.t('plugins.modal.config.gpuSearchPlaceholder'))}" autocomplete="off" aria-label="${uiAttr(searchLabel)}">
                        <span class="searchbar-icon">${searchIcon}</span>
                    </div>
                </div>
                <div class="form-col-secondary form-col-action">
                    <button class="ui-button plugin-gpu-binding-search-button" type="button" aria-label="${uiAttr(searchLabel)}" data-tooltip="${uiAttr(searchLabel)}">${searchLabel}</button>
                </div>
            </div>
            <div class="form-help plugin-gpu-binding-help">${i18n.t('plugins.modal.config.gpuBindingHelp')}</div>
            <div class="plugin-gpu-binding-results">${toTrustedUiHtml(renderPluginGpuBindingCards(state.entries, selectedIds, '', security))}</div>
            <select class="plugin-gpu-binding-store" multiple hidden aria-hidden="true">${toTrustedUiHtml(renderPluginGpuBindingStoreOptions(state, security))}</select>
        </section>
    `.html;
};

const requireTypedTarget = <T extends HTMLElement>(host: ConfigManagerHost, selector: string, context: Element, predicate: (element: HTMLElement) => element is T): T => {
    const element = host.requireHTMLElement(selector, context);
    if (!predicate(element)) {
        throw new TypeError(`Plugin GPU binding selector target ${selector} has unexpected element type`);
    }
    return element;
};

const isInput = (element: HTMLElement): element is HTMLInputElement => element instanceof HTMLInputElement;
const isButton = (element: HTMLElement): element is HTMLButtonElement => element instanceof HTMLButtonElement;
const isDiv = (element: HTMLElement): element is HTMLDivElement => element instanceof HTMLDivElement;
const isSelect = (element: HTMLElement): element is HTMLSelectElement => element instanceof HTMLSelectElement;

const resolvePluginGpuBindingTargets = (host: ConfigManagerHost, form: HTMLElement): PluginGpuBindingSelectorTargets => {
    const root = host.requireHTMLElement('[data-plugin-gpu-binding-selector]', form);
    return {
        root,
        searchInput: requireTypedTarget(host, '.plugin-gpu-binding-search', root, isInput),
        searchButton: requireTypedTarget(host, '.plugin-gpu-binding-search-button', root, isButton),
        memoryCounter: host.requireHTMLElement('[data-plugin-gpu-memory-counter]', root),
        results: requireTypedTarget(host, '.plugin-gpu-binding-results', root, isDiv),
        store: requireTypedTarget(host, '.plugin-gpu-binding-store', root, isSelect)
    };
};

const readSelectedPluginGpuIds = (store: HTMLSelectElement): Set<string> => {
    return new Set(
        Array.from(store.options)
            .filter((option) => option.selected)
            .map((option) => option.value)
    );
};

const ensurePluginGpuDefaultSelection = (store: HTMLSelectElement): void => {
    const selectedIds = readSelectedPluginGpuIds(store);
    if (selectedIds.size === 0) {
        const allOption = Array.from(store.options).find((option) => option.value === PLUGIN_GPU_ALL_ID);
        if (!allOption) {
            throw new Error('Plugin GPU binding All option is missing');
        }
        allOption.selected = true;
    }
};

const bindPluginGpuBindingSelectorListeners = (options: BindPluginGpuBindingSelectorListenersOptions): Array<() => void> => {
    if (!options.state) {
        return [];
    }
    const targets = resolvePluginGpuBindingTargets(options.host, options.form);
    if (targets.root.dataset['pluginGpuBindingBound']) {
        return [];
    }
    targets.root.dataset['pluginGpuBindingBound'] = 'true';
    checkerboardService.applyCheckerboard(targets.results, PLUGIN_GPU_CARD_SELECTOR);
    const entries = options.state.entries;
    const render = (): void => {
        ensurePluginGpuDefaultSelection(targets.store);
        const selectedIds = readSelectedPluginGpuIds(targets.store);
        const cardsMarkup = toTrustedUiHtml(renderPluginGpuBindingCards(entries, selectedIds, targets.root.getAttribute(PLUGIN_GPU_QUERY_ATTR) ?? '', options.security));
        options.host.updateText(targets.memoryCounter, formatPluginGpuBindingMemory(entries, selectedIds));
        options.host.updateHTML(targets.results, cardsMarkup);
        checkerboardService.applyCheckerboard(targets.results, PLUGIN_GPU_CARD_SELECTOR);
    };
    const commitSelection = (): void => {
        const selectedIds = readSelectedPluginGpuIds(targets.store);
        options.manager.updateValue(PLUGIN_GPU_BINDING_KEY, createPluginGpuBindingConfigValue(selectedIds));
        options.onValueChanged(PLUGIN_GPU_BINDING_KEY);
    };
    const handleCardClick = (event: Event): void => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const card = target.closest('[data-plugin-gpu-id]');
        if (!(card instanceof HTMLElement)) return;
        const id = card.dataset['pluginGpuId'];
        if (!id) {
            throw new Error('Plugin GPU binding card requires data-plugin-gpu-id');
        }
        if (card.getAttribute('aria-disabled') === 'true') {
            return;
        }
        for (const option of Array.from(targets.store.options)) {
            if (id === PLUGIN_GPU_ALL_ID) {
                option.selected = option.value === PLUGIN_GPU_ALL_ID;
            } else if (option.value === PLUGIN_GPU_ALL_ID) {
                option.selected = false;
            } else if (option.value === id) {
                option.selected = !option.selected;
            }
        }
        render();
        commitSelection();
    };
    const applySearch = (): void => {
        targets.root.setAttribute(PLUGIN_GPU_QUERY_ATTR, targets.searchInput.value);
        render();
    };
    return [options.host.on(targets.results, 'click', handleCardClick), options.host.on(targets.searchInput, 'input', applySearch), options.host.on(targets.searchButton, 'click', applySearch), () => checkerboardService.disconnect(checkerboardService.getContainerId(targets.results))];
};

export { bindPluginGpuBindingSelectorListeners, renderPluginGpuBindingSelector };
