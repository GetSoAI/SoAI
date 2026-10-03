/* SoAI - Charts feature chart filters actions [frontend/assets/ts/features/charts/chartfilters/actions.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { insertWithPresence, isPresenceExiting, removeWithPresence, resolveNextPresenceAnchor } from '@core/animations/presence/public.ts';
import { dom, resolveAll } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isString } from '@core/typeGuards.ts';
import { FILTER_TYPES, resolveFilterId } from '@features/charts/chartfilters/constants.ts';
import { normalizeFilterValue, resolveOptionText, toFilterOption } from '@features/charts/chartfilters/mappers.ts';
import type { FilterOption, FilterOptionsInput, FilterType, FilterValue, FilterValueChangeHandler, InternalChartFiltersConfig } from '@features/charts/chartfilters/types.ts';

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

const createFilterButton = (type: FilterType, option: FilterOption, selectedValue: string, formatValue: ((value: FilterValue) => string) | undefined): HTMLButtonElement => {
    const value = normalizeFilterValue(option.value);
    const button = dom.create('button', {
        type: 'button',
        className: `ui-button ui-button--titlebar ui-variant-neutral${value === selectedValue ? ' is-active' : ''}`,
        dataset: { value },
        textContent: resolveOptionText(option, type, formatValue),
        includeIdClass: false
    });
    if (!(button instanceof HTMLButtonElement)) {
        throw new Error('Filter control button must be an HTMLButtonElement');
    }
    return button;
};

const resolveFilterButtons = (control: HTMLDivElement): HTMLButtonElement[] => resolveAll('.ui-button', control).filter((button): button is HTMLButtonElement => button instanceof HTMLButtonElement);

const createFilterButtons = (type: FilterType, options: FilterOptionsInput, selected: FilterValue | null, formatValue: ((value: FilterValue) => string) | undefined, onChange: FilterValueChangeHandler, onSync: (type: FilterType) => void, resources: ResourceTracker): HTMLDivElement => {
    const selectedValue = selected === null ? '' : normalizeFilterValue(selected);
    const container = dom.create('div', {
        className: 'chart-filter-buttons',
        dataset: { filter: type },
        includeIdClass: false
    });
    if (!(container instanceof HTMLDivElement)) {
        throw new Error('Filter control buttons container must be an HTMLDivElement');
    }
    container.append(...options.map((rawOption) => createFilterButton(type, toFilterOption(rawOption), selectedValue, formatValue)));

    resources.addEventListener(container, 'click', (event) => {
        const target = event.target instanceof HTMLElement ? event.target.closest('.ui-button') : null;
        if (!(target instanceof HTMLButtonElement) || !container.contains(target) || isPresenceExiting(target)) {
            return;
        }
        const nextValue = target.dataset['value'];
        if (!isString(nextValue)) {
            return;
        }
        resolveFilterButtons(container).forEach((button) => {
            applyFilterButtonActiveState(button, false);
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
    const existingButtons = new Map(resolveFilterButtons(control).map((button) => [button.dataset['value'] ?? '', button]));
    const firstChild = control.firstChild;
    let anchor = firstChild instanceof HTMLElement && isPresenceExiting(firstChild) ? resolveNextPresenceAnchor(firstChild) : firstChild;
    for (const rawOption of options) {
        const option = toFilterOption(rawOption);
        const value = normalizeFilterValue(option.value);
        const button = existingButtons.get(value) ?? createFilterButton(type, option, selectedValue, formatValue);
        existingButtons.delete(value);
        if (!button.isConnected || isPresenceExiting(button)) {
            insertWithPresence(control, button, anchor);
        } else if (anchor !== button) {
            control.insertBefore(button, anchor);
        }
        const text = resolveOptionText(option, type, formatValue);
        if (button.textContent !== text) {
            button.textContent = text;
        }
        applyFilterButtonActiveState(button, value === selectedValue);
        anchor = resolveNextPresenceAnchor(button);
    }
    const focusedButton = Array.from(existingButtons.values()).find((button) => button.contains(button.ownerDocument.activeElement));
    existingButtons.forEach((button) => {
        if (!isPresenceExiting(button)) {
            removeWithPresence(button);
        }
    });
    if (focusedButton) {
        const replacement = resolveFilterButtons(control).find((button) => !isPresenceExiting(button) && button.classList.contains('is-active')) ?? resolveFilterButtons(control).find((button) => !isPresenceExiting(button));
        replacement?.focus();
    }
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
        resolveFilterButtons(control).forEach((button) => {
            applyFilterButtonActiveState(button, button.dataset['value'] === normalizeFilterValue(value ?? ''));
        });
        return;
    }
    if (control instanceof HTMLSelectElement) {
        control.value = normalizeFilterValue(value ?? '');
    }
};

export { buildFilterControl, refreshFilterControl, syncFilterInput };
