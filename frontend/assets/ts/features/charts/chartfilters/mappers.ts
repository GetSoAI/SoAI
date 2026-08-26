/* SoAI - Charts feature chart filters mapping [frontend/assets/ts/features/charts/chartfilters/mappers.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { FILTER_TYPES, isFilterType } from '@features/charts/chartfilters/constants.ts';
import { resolveChartTypeLabel } from '@features/charts/chartfilters/formatting.ts';
import type { ChartFiltersElements, FilterOption, FilterOptionInput, FilterOptionsInput, FilterType, FilterValue } from '@features/charts/chartfilters/types.ts';

const resolveFilterElement = (container: HTMLElement, elements: ChartFiltersElements, type: FilterType | 'fullscreen' | string): HTMLElement | null => {
    if (type === 'fullscreen') {
        return elements.fullscreenBtn;
    }
    if (isFilterType(type)) {
        const control = elements.filters[type];
        if (control instanceof HTMLElement) {
            return control;
        }
        return null;
    }
    for (const element of dom.resolveAll('[data-filter]', container)) {
        if (element instanceof HTMLElement && element.dataset['filter'] === type) {
            return element;
        }
    }
    return null;
};

const normalizeFilterValue = (value: FilterValue): string => String(value);

const toFilterOption = (input: FilterOptionInput): FilterOption => {
    if (typeof input === 'object') {
        const option: FilterOption = { value: input.value };
        if (isString(input.label)) {
            option.label = input.label;
        }
        return option;
    }
    return { value: input };
};

const resolveFilterValue = (option: FilterOptionInput): FilterValue => toFilterOption(option).value;

const resolveFilterValues = (options: FilterOptionsInput): FilterValue[] => options.map(resolveFilterValue);

const resolveOptionText = (option: FilterOption, type: FilterType, formatValue: ((value: FilterValue) => string) | undefined): string => {
    if (formatValue !== undefined) {
        return formatValue(option.value);
    }
    if (isString(option.label)) {
        return option.label;
    }
    if (type === FILTER_TYPES.CHART_TYPE) {
        return resolveChartTypeLabel(option.value);
    }
    return String(option.value);
};

export { normalizeFilterValue, resolveFilterElement, resolveFilterValue, resolveFilterValues, resolveOptionText, toFilterOption };
