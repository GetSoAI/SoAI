/* SoAI - Charts feature chart filters rendering [frontend/assets/ts/features/charts/chartfilters/view.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { isString } from '@core/typeGuards.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import { buildFilterControl } from '@features/charts/chartfilters/actions.ts';
import { createFilterPanel, createFilterTrigger, createFullscreenButton, wrapFilterControl } from '@features/charts/chartfilters/dom.ts';
import { resolveFilterValue, resolveFilterValues } from '@features/charts/chartfilters/mappers.ts';
import { resolveInitialSelection } from '@features/charts/chartfilters/state.ts';
import type { ChartFiltersElements, InternalChartFiltersConfig, FilterOptionsInput, FilterType, FilterValue } from '@features/charts/chartfilters/types.ts';

type FilterChangeHandler = (type: FilterType, value: FilterValue) => void;
type SyncChangeHandler = (type: FilterType, shouldNotify: boolean) => void;

interface RenderChartFiltersViewOptions {
    container: HTMLElement;
    state: Readonly<{
        chartType: string;
        category: string | null;
        subcategory: string | null;
        timeRange: number | null;
        candleInterval: number | null;
    }>;
    config: InternalChartFiltersConfig;
    formatTimeRange: (minutes: number) => string;
    getFilterLabel: (type: FilterType) => string;
    onChange: FilterChangeHandler;
    onSync: SyncChangeHandler;
    resources: ResourceTracker;
}

interface FilterSectionRenderOptions {
    panel: HTMLDivElement;
    type: FilterType;
    options: FilterOptionsInput;
    selected: FilterValue | null;
    useButtonGroup: boolean;
    label: string;
    config: InternalChartFiltersConfig;
    formatTimeRange: (minutes: number) => string;
    onChange: FilterChangeHandler;
    onSync: SyncChangeHandler;
    resources: ResourceTracker;
    elements: ChartFiltersElements;
}

const appendFilterSection = ({ panel, type, options, selected, useButtonGroup, label, config, formatTimeRange, onChange, onSync, resources, elements }: FilterSectionRenderOptions): void => {
    const control = buildFilterControl({
        type,
        options,
        selected,
        useButtonGroup,
        config,
        formatValue: type === FILTER_TYPES.TIME_RANGE || type === FILTER_TYPES.CANDLE_INTERVAL ? (value) => formatTimeRange(Number(value)) : undefined,
        onChange,
        onSync: (syncType) => onSync(syncType, true),
        resources
    });
    elements.filters[type] = control;
    panel.appendChild(
        wrapFilterControl({
            type,
            control,
            showLabel: true,
            label
        })
    );
};

const resolveSelectedOptionValue = (current: FilterValue | null, options: FilterOptionsInput): FilterValue | null => {
    const selectedValue = resolveInitialSelection(current, resolveFilterValues(options));
    return selectedValue === '' ? null : selectedValue;
};

const renderChartFiltersView = ({ container, state, config, formatTimeRange, getFilterLabel, onChange, onSync, resources }: RenderChartFiltersViewOptions): ChartFiltersElements => {
    const fragment = dom.createFragment();
    const trigger = createFilterTrigger();
    const compactPanel = createFilterPanel();

    const elements: ChartFiltersElements = {
        compactTrigger: trigger,
        compactPanel,
        fullscreenBtn: null,
        filters: {}
    };

    fragment.appendChild(trigger);
    if (config.showChartType) {
        const chartTypeControl = buildFilterControl({
            type: FILTER_TYPES.CHART_TYPE,
            options: config.chartTypes,
            selected: state.chartType,
            useButtonGroup: false,
            config,
            onChange,
            onSync: (syncType) => onSync(syncType, true),
            resources
        });
        elements.filters[FILTER_TYPES.CHART_TYPE] = chartTypeControl;
        compactPanel.appendChild(
            wrapFilterControl({
                type: FILTER_TYPES.CHART_TYPE,
                control: chartTypeControl,
                showLabel: false,
                label: ''
            })
        );
    }

    if (config.showCategory && config.categories.length > 0) {
        const currentValue = resolveSelectedOptionValue(state.category, config.categories);
        appendFilterSection({
            panel: compactPanel,
            type: FILTER_TYPES.CATEGORY,
            options: config.categories,
            selected: currentValue,
            useButtonGroup: false,
            label: getFilterLabel(FILTER_TYPES.CATEGORY),
            config,
            formatTimeRange,
            onChange,
            onSync,
            resources,
            elements
        });
    }

    if (config.showSubcategory && config.subcategories.length > 0) {
        const firstValue = config.subcategories[0] ? resolveFilterValue(config.subcategories[0]) : '';
        const selectedValue = resolveSelectedOptionValue(state.subcategory, config.subcategories);
        const safeSelected = isString(selectedValue) && selectedValue.length > 0 ? selectedValue : firstValue;
        appendFilterSection({
            panel: compactPanel,
            type: FILTER_TYPES.SUBCATEGORY,
            options: config.subcategories,
            selected: safeSelected === '' ? null : safeSelected,
            useButtonGroup: false,
            label: getFilterLabel(FILTER_TYPES.SUBCATEGORY),
            config,
            formatTimeRange,
            onChange,
            onSync,
            resources,
            elements
        });
    }

    if (config.showCandleInterval && config.candleIntervals.length > 0) {
        const selectedValue = resolveSelectedOptionValue(state.candleInterval, config.candleIntervals);
        appendFilterSection({
            panel: compactPanel,
            type: FILTER_TYPES.CANDLE_INTERVAL,
            options: config.candleIntervals,
            selected: selectedValue,
            useButtonGroup: false,
            label: getFilterLabel(FILTER_TYPES.CANDLE_INTERVAL),
            config,
            formatTimeRange,
            onChange,
            onSync,
            resources,
            elements
        });
    }

    if (config.showTimeRange && config.timeRangeOptions.length > 0) {
        const selectedValue = resolveSelectedOptionValue(state.timeRange, config.timeRangeOptions);
        appendFilterSection({
            panel: compactPanel,
            type: FILTER_TYPES.TIME_RANGE,
            options: config.timeRangeOptions,
            selected: selectedValue,
            useButtonGroup: true,
            label: getFilterLabel(FILTER_TYPES.TIME_RANGE),
            config,
            formatTimeRange,
            onChange,
            onSync,
            resources,
            elements
        });
    }

    fragment.appendChild(compactPanel);

    if (config.showFullscreen) {
        const fullscreenBtn = createFullscreenButton();
        const fullscreenHost = dom.create('div', {
            className: 'chart-filter chart-filter-fullscreen',
            dataset: { filter: 'fullscreen' },
            includeIdClass: false
        });
        fullscreenHost.appendChild(fullscreenBtn);
        elements.fullscreenBtn = fullscreenBtn;
        fragment.appendChild(fullscreenHost);
    }

    container.replaceChildren(fragment);
    container.classList.add('chart-filters-bar');
    return elements;
};

export { renderChartFiltersView };
