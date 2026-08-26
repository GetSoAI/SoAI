/* SoAI - Metrics advanced modal content renderer [frontend/assets/ts/features/metrics/modals/advancedMetricsContent.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { modalUiId, modalUiSelector } from '@core/modals/uiIds.ts';
import { getIconSync } from '@core/ui/icons/iconservice/public.ts';
import { createIconSlot } from '@core/ui/icons/view.ts';
import { buildAdvancedMetricsInventory, filterAdvancedMetricsInventory, type AdvancedMetricsInventory } from '@features/metrics/modals/advancedMetricsInventory.ts';
import { METRICS_ADVANCED_MODAL_ID } from '@features/metrics/modals/advancedMetricsConstants.ts';
import type { MetricsAdvancedModalHost } from '@features/metrics/modals/advancedMetricsHost.ts';

type AdvancedMetricsRenderResult = {
    inventory: AdvancedMetricsInventory;
};

type AdvancedMetricsRenderOptions = {
    placeholder: string;
    query: string;
};

const buildSectionTitles = (): Record<string, string> => {
    return {
        api: i18n.t('metrics.advanced.sections.api'),
        billing: i18n.t('metrics.advanced.sections.billing'),
        director: i18n.t('metrics.advanced.sections.director'),
        genesis: i18n.t('metrics.advanced.sections.genesis'),
        hardware: i18n.t('metrics.advanced.sections.hardware'),
        models: i18n.t('metrics.advanced.sections.models'),
        plugins: i18n.t('metrics.advanced.sections.plugins'),
        system: i18n.t('metrics.advanced.sections.system'),
        tasks: i18n.t('metrics.advanced.sections.tasks'),
        telemetry: i18n.t('metrics.advanced.sections.telemetry'),
        global: i18n.t('metrics.advanced.sections.global')
    };
};

const createNoDataElement = (message: string): HTMLElement => {
    const node = dom.create('div', { className: 'metrics-advanced-nodata', includeIdClass: false });
    node.textContent = message;
    return node;
};

const renderSection = (container: HTMLElement, section: { title: string; rows: { label: string; value: string; monoValue: boolean }[] }): void => {
    const sectionElement = dom.create('section', { className: 'metrics-advanced-section', includeIdClass: false });
    const titleElement = dom.create('div', { className: 'metrics-advanced-section-title', includeIdClass: false });
    titleElement.textContent = section.title;
    sectionElement.appendChild(titleElement);

    if (section.rows.length === 0) {
        sectionElement.appendChild(createNoDataElement(i18n.t('metrics.advanced.noSnapshot')));
        container.appendChild(sectionElement);
        return;
    }

    const grid = dom.create('div', { className: 'metrics-advanced-grid', includeIdClass: false });
    for (const row of section.rows) {
        const rowElement = dom.create('div', { className: 'metrics-advanced-row', includeIdClass: false });
        const labelElement = dom.create('div', { className: 'metrics-advanced-label', includeIdClass: false });
        labelElement.textContent = row.label;
        const valueClass = row.monoValue ? 'metrics-advanced-value metrics-advanced-value-mono' : 'metrics-advanced-value';
        const valueElement = dom.create('div', { className: valueClass, includeIdClass: false });
        valueElement.textContent = row.value;
        rowElement.appendChild(labelElement);
        rowElement.appendChild(valueElement);
        grid.appendChild(rowElement);
    }
    sectionElement.appendChild(grid);
    container.appendChild(sectionElement);
};

const resolveAdvancedMetricsSearchInput = (content: HTMLElement): HTMLInputElement | null => {
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const input = dom.resolve(modalUiSelector(modalId, 'search'), content);
    return input instanceof HTMLInputElement ? input : null;
};

const ensureAdvancedMetricsBody = (content: HTMLElement): HTMLElement => {
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const existing = dom.resolve(modalUiSelector(modalId, 'body'), content);
    if (existing instanceof HTMLElement) {
        return existing;
    }
    const bodyContainer = dom.create('div', {
        className: 'metrics-advanced-body',
        id: modalUiId(modalId, 'body'),
        includeIdClass: false
    });
    content.appendChild(bodyContainer);
    return bodyContainer;
};

const createAdvancedMetricsSearchInput = (content: HTMLElement, query: string): HTMLInputElement => {
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const existing = resolveAdvancedMetricsSearchInput(content);
    if (existing) {
        dom.setProperty(existing, 'value', query);
        return existing;
    }

    const searchRegion = dom.create('div', { className: 'metrics-advanced-search', includeIdClass: false });
    const searchContainer = dom.create('div', { className: 'searchbar-container searchbar-container--control wide u-stretch', includeIdClass: false });
    const searchInput = dom.create('input', {
        type: 'text',
        className: 'searchbar-input',
        id: modalUiId(modalId, 'search'),
        placeholder: i18n.t('metrics.advanced.searchPlaceholder'),
        autocomplete: 'off',
        'aria-label': i18n.t('metrics.advanced.searchPlaceholder'),
        includeIdClass: false
    });
    if (!(searchInput instanceof HTMLInputElement)) {
        throw new Error('Metrics advanced search input failed to initialize');
    }
    dom.setProperty(searchInput, 'value', query);

    const iconMarkup = getIconSync('search', { size: 16, strokeWidth: 1.5 });
    const searchIcon = createIconSlot(content.ownerDocument, iconMarkup, { className: 'searchbar-icon u-hide-mobile-portrait' });

    searchContainer.appendChild(searchInput);
    searchContainer.appendChild(searchIcon);
    searchRegion.appendChild(searchContainer);
    content.appendChild(searchRegion);
    return searchInput;
};

const renderMetricsAdvancedModalContent = (modal: HTMLElement, host: MetricsAdvancedModalHost, options: AdvancedMetricsRenderOptions, signal: AbortSignal): AdvancedMetricsRenderResult => {
    const modalId = METRICS_ADVANCED_MODAL_ID;
    const content = dom.resolve(modalUiSelector(modalId, 'content'), modal);
    if (!(content instanceof HTMLElement)) {
        throw new Error('Metrics advanced modal content container is missing');
    }
    const searchInput = createAdvancedMetricsSearchInput(content, options.query);

    const sectionTitles = buildSectionTitles();
    const otherTitle = i18n.t('metrics.advanced.sections.other');
    const telemetryTitle = i18n.t('metrics.advanced.sections.frontendTelemetry');

    const metricsSnapshot = host.getMetricsSnapshot();
    const telemetryStatusSnapshot = host.getTelemetryStatusSnapshot();

    const inventory = buildAdvancedMetricsInventory(metricsSnapshot, {
        placeholder: options.placeholder,
        sectionTitles,
        otherSectionTitle: otherTitle,
        telemetrySectionTitle: telemetryTitle,
        telemetryStatus: telemetryStatusSnapshot
    });

    let current = filterAdvancedMetricsInventory(inventory, options.query);

    const bodyContainer = ensureAdvancedMetricsBody(content);

    const render = (next: AdvancedMetricsInventory): void => {
        bodyContainer.textContent = '';
        const visibleSections = next.sections.filter((section) => section.rows.length > 0);
        if (visibleSections.length === 0) {
            bodyContainer.appendChild(createNoDataElement(i18n.t('metrics.advanced.noMatches')));
            return;
        }
        for (const section of visibleSections) {
            renderSection(bodyContainer, section);
        }
    };

    const applyQuery = (): void => {
        const query = searchInput.value ?? '';
        current = filterAdvancedMetricsInventory(inventory, query);
        render(current);
    };

    searchInput.addEventListener('input', applyQuery, { signal });
    if (signal.aborted) {
        return { inventory };
    }
    render(current);

    return { inventory: current };
};

export { renderMetricsAdvancedModalContent };
export type { AdvancedMetricsRenderResult };
