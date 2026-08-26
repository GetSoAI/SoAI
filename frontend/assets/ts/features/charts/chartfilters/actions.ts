/* SoAI - Charts feature chart filters actions [frontend/assets/ts/features/charts/chartfilters/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom, resolveAll } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isString } from '@core/typeGuards.ts';
import { FILTER_TYPES, resolveFilterId } from '@features/charts/chartfilters/constants.ts';
import { normalizeFilterValue, resolveOptionText, toFilterOption } from '@features/charts/chartfilters/mappers.ts';
import type { FilterOptionsInput, FilterType, FilterValue, FilterValueChangeHandler, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

interface BuildFilterControlOptions {
    type: FilterType;
    options: FilterOptionsInput;
    selected: FilterValue | null;
    useButtonGroup: boolean;
    formatValue?: ((value: FilterValue) => string) | undefined;
    config: InternalChartFiltersConfig;
    onChange: FilterValueChangeHandler;
    onSync: (type: FilterType) => void;
    resources: ResourceTracker;
}

interface RefreshFilterControlOptions {
    type: FilterType;
    control: HTMLSelectElement | HTMLDivElement;
    options: FilterOptionsInput;
    selected: FilterValue | null;
    formatValue?: ((value: FilterValue) => string) | undefined;
}

const applyFilterButtonActiveState = (button: HTMLButtonElement, isActive: boolean): void => {
    button.classList.toggle('is-active', isActive);
    button.classList.toggle('ui-variant-neutral', true);
    button.classList.toggle('ui-variant-primary', false);
};

const createFilterButtons = (type: FilterType, options: FilterOptionsInput, selected: FilterValue | null, formatValue: ((value: FilterValue) => string) | undefined, onChange: FilterValueChangeHandler, onSync: (type: FilterType) => void, resources: ResourceTracker): HTMLDivElement => {
    const selectedValue = selected === null ? '' : normalizeFilterValue(selected);
    const buttons = options.map((rawOption) => {
        const option = toFilterOption(rawOption);
        const value = normalizeFilterValue(option.value);
        const isActive = value === selectedValue;
        return dom.create('button', {
            type: 'button',
            className: `ui-button ui-button--titlebar ui-variant-neutral${isActive ? ' is-active' : ''}`,
            dataset: { value },
            textContent: resolveOptionText(option, type, formatValue),
            includeIdClass: false
        });
    });

    const container = dom.create('div', {
        className: 'chart-filter-buttons',
        dataset: { filter: type },
        includeIdClass: false
    });
    if (!(container instanceof HTMLDivElement)) {
        throw new Error('Filter control buttons container must be an HTMLDivElement');
    }
    container.append(...buttons);

    resources.addEventListener(container, 'click', (event) => {
        const target = event.target instanceof HTMLElement ? event.target.closest('.ui-button') : null;
        if (!(target instanceof HTMLButtonElement)) {
            return;
        }
        if (!container.contains(target)) {
            return;
        }
        const nextValue = target.dataset['value'];
        if (!isString(nextValue)) {
            return;
        }
        resolveAll('.ui-button', container).forEach((button) => {
            if (button instanceof HTMLButtonElement) {
                applyFilterButtonActiveState(button, false);
            }
        });
        applyFilterButtonActiveState(target, true);
        onChange(type, nextValue);
        onSync(type);
    });

    return container;
};

const createFilterSelect = (type: FilterType, options: FilterOptionsInput, selected: FilterValue | null, config: InternalChartFiltersConfig, formatValue: ((value: FilterValue) => string) | undefined, onChange: FilterValueChangeHandler, onSync: (type: FilterType) => void, resources: ResourceTracker): HTMLSelectElement => {
    const id = resolveFilterId(config.filterIds, type, `chart-filter-${type}`);
    const select = dom.create('select', {
        className: 'chart-filter-select chart-filter-select--titlebar',
        dataset: { filter: type },
        ...(isString(id) ? { id } : {}),
        includeIdClass: false
    });
    if (!(select instanceof HTMLSelectElement)) {
        throw new Error('Filter control must be an HTMLSelectElement');
    }

    const selectedValue = normalizeFilterValue(selected ?? '');
    const optionNodes = options.map((rawOption) => {
        const option = toFilterOption(rawOption);
        const value = normalizeFilterValue(option.value);
        return dom.create('option', {
            value,
            textContent: resolveOptionText(option, type, formatValue),
            selected: value === selectedValue,
            includeIdClass: false
        });
    });
    select.append(...optionNodes);

    resources.addEventListener(select, 'change', () => {
        onChange(type, select.value);
        onSync(type);
    });

    return select;
};

const buildFilterControl = ({ type, options, selected, useButtonGroup, formatValue, config, onChange, onSync, resources }: BuildFilterControlOptions): HTMLSelectElement | HTMLDivElement => {
    if (useButtonGroup) {
        return createFilterButtons(type, options, selected, formatValue, onChange, onSync, resources);
    }
    return createFilterSelect(type, options, selected, config, formatValue, onChange, onSync, resources);
};

const refreshFilterButtons = (type: FilterType, control: HTMLDivElement, options: FilterOptionsInput, selected: FilterValue | null, formatValue: ((value: FilterValue) => string) | undefined): void => {
    const selectedValue = selected === null ? '' : normalizeFilterValue(selected);
    const controls = options.map((rawOption) => {
        const option = toFilterOption(rawOption);
        const value = normalizeFilterValue(option.value);
        const isActive = value === selectedValue;
        return dom.create('button', {
            type: 'button',
            className: `ui-button ui-button--titlebar ui-variant-neutral${isActive ? ' is-active' : ''}`,
            dataset: { value },
            textContent: resolveOptionText(option, type, formatValue),
            includeIdClass: false
        });
    });
    control.replaceChildren(...controls);
};

const refreshFilterSelect = (type: FilterType, control: HTMLSelectElement, options: FilterOptionsInput, selected: FilterValue | null, formatValue: ((value: FilterValue) => string) | undefined): void => {
    const selectedValue = selected === null ? '' : normalizeFilterValue(selected);
    const optionNodes = options.map((rawOption) => {
        const option = toFilterOption(rawOption);
        const value = normalizeFilterValue(option.value);
        return dom.create('option', {
            value,
            textContent: resolveOptionText(option, type, formatValue),
            selected: value === selectedValue,
            includeIdClass: false
        });
    });
    control.replaceChildren(...optionNodes);
};

const refreshFilterControl = ({ type, control, options, selected, formatValue }: RefreshFilterControlOptions): void => {
    if (type === FILTER_TYPES.TIME_RANGE && control instanceof HTMLDivElement) {
        refreshFilterButtons(type, control, options, selected, formatValue);
        return;
    }
    if (control instanceof HTMLSelectElement) {
        refreshFilterSelect(type, control, options, selected, formatValue);
    }
};

const syncFilterInput = (type: FilterType, control: HTMLSelectElement | HTMLDivElement, value: FilterValue | null): void => {
    if (control instanceof HTMLDivElement) {
        if (type !== FILTER_TYPES.TIME_RANGE) {
            throw new Error(`Chart filter ${type} does not support button synchronization`);
        }
        const buttons = resolveAll('.ui-button', control).filter((button): button is HTMLButtonElement => button instanceof HTMLButtonElement);
        buttons.forEach((button) => {
            applyFilterButtonActiveState(button, button.dataset['value'] === normalizeFilterValue(value ?? ''));
        });
        return;
    }
    if (control instanceof HTMLSelectElement) {
        control.value = normalizeFilterValue(value ?? '');
    }
};

export { buildFilterControl, refreshFilterControl, syncFilterInput };
