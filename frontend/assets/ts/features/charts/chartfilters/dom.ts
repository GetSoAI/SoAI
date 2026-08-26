/* SoAI - Charts feature chart filters DOM contracts [frontend/assets/ts/features/charts/chartfilters/dom.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { i18n } from '@core/i18n/index.ts';
import { uiHtml } from '@core/security/uiHtml.ts';
import { isOhlcChartType } from '@features/charts/chartTypeNormalization.ts';
import { FILTER_ICON_NAMES, resolveIconMarkup } from '@features/charts/chartfilters/constants.ts';
import { resolveChartTypeLabel } from '@features/charts/chartfilters/formatting.ts';
import type { ChartFiltersState, FilterOption, FilterType } from '@features/charts/chartfilters/types.ts';

interface WrapFilterControlOptions {
    type: FilterType | 'fullscreen';
    control: HTMLElement;
    showLabel: boolean;
    label: string | undefined;
}

const wrapFilterControl = ({ type, control, showLabel, label }: WrapFilterControlOptions): HTMLDivElement => {
    const wrapper = dom.create('div', {
        className: 'chart-filter',
        dataset: { filter: type },
        includeIdClass: false
    });
    if (!(wrapper instanceof HTMLDivElement)) {
        throw new Error('Chart filter wrapper must be an HTMLDivElement');
    }
    if (showLabel && label !== undefined) {
        wrapper.appendChild(
            dom.create('span', {
                className: 'chart-filter-label',
                textContent: label,
                includeIdClass: false
            })
        );
    }
    wrapper.appendChild(control);
    return wrapper;
};

const buildCompactSummaryText = (input: { state: Readonly<ChartFiltersState>; config: { showChartType: boolean; showCategory: boolean; showTimeRange: boolean }; categories: readonly FilterOption[]; formatTimeRange: (minutes: number) => string }): string => {
    const { state, config, categories, formatTimeRange } = input;
    const pieces: string[] = [];
    if (config.showChartType && state.chartType) {
        pieces.push(resolveChartTypeLabel(state.chartType));
    }
    if (config.showCategory && state.category) {
        const option = categories.find((entry) => entry.value === state.category);
        if (isOptionLabelVisible(option?.label)) {
            pieces.push(option.label);
        }
    }
    if (config.showTimeRange && state.timeRange) {
        pieces.push(formatTimeRange(state.timeRange));
    }
    return pieces.join(', ') || i18n.t('charts.filters.trigger');
};

const isOptionLabelVisible = (label: string | undefined): label is string => {
    return Boolean(label);
};

const createFilterTrigger = (): HTMLButtonElement => {
    const trigger = dom.create('button', {
        type: 'button',
        className: 'chart-filters-trigger ui-button ui-button--titlebar ui-variant-neutral',
        'aria-label': i18n.t('charts.filters.trigger'),
        'aria-expanded': 'false',
        html: uiHtml`${resolveIconMarkup(FILTER_ICON_NAMES.FILTER)}<span class="chart-filters-trigger-summary"></span>`,
        includeIdClass: false
    });
    if (!(trigger instanceof HTMLButtonElement)) {
        throw new Error('Chart filter trigger must be an HTMLButtonElement');
    }
    return trigger;
};

const createFilterPanel = (): HTMLDivElement => {
    const panel = dom.create('div', {
        className: 'chart-filters-panel',
        includeIdClass: false
    });
    if (!(panel instanceof HTMLDivElement)) {
        throw new Error('Chart filter panel must be an HTMLDivElement');
    }
    return panel;
};

const createFullscreenButton = (): HTMLButtonElement => {
    const button = dom.create('button', {
        type: 'button',
        className: 'ui-icon-button ui-icon-button--titlebar ui-variant-neutral chart-fullscreen-btn',
        'aria-label': i18n.t('charts.filters.fullscreen.label'),
        'aria-pressed': 'false',
        html: resolveIconMarkup(FILTER_ICON_NAMES.FULLSCREEN_ENTER),
        includeIdClass: false
    });
    if (!(button instanceof HTMLButtonElement)) {
        throw new Error('Chart fullscreen button must be an HTMLButtonElement');
    }
    return button;
};

const updateFilterVisibility = (scope: HTMLElement, filter: string, visible: boolean): void => {
    const wrapper = dom.resolve(`.chart-filter[data-filter="${filter}"]`, scope);
    if (wrapper instanceof HTMLElement) {
        wrapper.classList.toggle('chart-filter--hidden', !visible);
        wrapper.toggleAttribute('aria-hidden', !visible);
        dom.resolveAll('select, button, input', wrapper).forEach((control) => {
            if (control instanceof HTMLSelectElement || control instanceof HTMLButtonElement || control instanceof HTMLInputElement) {
                control.disabled = !visible;
            }
        });
    }
};

const updateChartTypeFilterVisibility = (scope: HTMLElement, chartType: string): void => {
    updateFilterVisibility(scope, 'candleInterval', isOhlcChartType(chartType));
};

export { buildCompactSummaryText, createFilterPanel, createFilterTrigger, createFullscreenButton, updateChartTypeFilterVisibility, wrapFilterControl };
