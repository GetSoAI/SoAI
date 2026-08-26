/* SoAI - Charts feature chart filters service [frontend/assets/ts/features/charts/chartfilters/service.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { ResourceTracker } from '@core/resourcetracker/service.ts';
import { isFunction, isInstanceOf } from '@core/typeGuards.ts';
import { createChartFiltersConfig, createChartFiltersState, readFilterValue, updateFilterState } from '@features/charts/chartfilters/state.ts';
import { createCompactModeState, disposeCompactMode, setupCompactMode, toggleFullscreen, updateCompactSummary, updateFullscreenIcon, type ChartFiltersCompactModeContext, type ChartFiltersCompactModeState, type ChartFiltersFullscreenContext } from '@features/charts/chartfilters/events.ts';
import { FILTER_TYPES } from '@features/charts/chartfilters/constants.ts';
import { updateChartTypeFilterVisibility } from '@features/charts/chartfilters/dom.ts';
import { syncFilterInput } from '@features/charts/chartfilters/actions.ts';
import { applyCandleIntervals, applyCategoryOptions, applyStatePatch, applySubcategoryOptions, applyTimeRangeOptions, registerFilterCallback } from '@features/charts/chartfilters/effects.ts';
import { formatTimeRangeMinutes, resolveChartFilterLabel } from '@features/charts/chartfilters/formatting.ts';
import { resolveFilterElement } from '@features/charts/chartfilters/mappers.ts';
import { renderChartFiltersView } from '@features/charts/chartfilters/view.ts';
import type { ChartFiltersCallbacks, ChartFiltersElements, ChartFiltersOptions, ChartFiltersState, ChartRuntimeContract, InternalChartFiltersConfig, FilterOption, FilterOptionsInput, FilterType, FilterValue } from '@features/charts/chartfilters/types.ts';

class ChartFilters {
    readonly #container: HTMLElement;
    readonly #chartRuntime: ChartRuntimeContract | null | undefined;
    readonly #config: InternalChartFiltersConfig;
    #state: ChartFiltersState;
    #callbacks: ChartFiltersCallbacks = {};
    #compactModeState: ChartFiltersCompactModeState = createCompactModeState();
    #disposed = false;
    #elements: ChartFiltersElements = {
        compactTrigger: null,
        compactPanel: null,
        fullscreenBtn: null,
        filters: {}
    };
    readonly #resources = new ResourceTracker();

    constructor(options: ChartFiltersOptions) {
        const { container, chartRuntime, config = {} } = options;
        if (!isInstanceOf(container, HTMLElement)) {
            throw new Error('ChartFilters requires a container element');
        }

        this.#container = container;
        this.#chartRuntime = chartRuntime;
        this.#config = createChartFiltersConfig(config);
        this.#state = createChartFiltersState(config);
    }

    readonly getFilterLabel = (type: FilterType): string => {
        return resolveChartFilterLabel(type, this.#config.filterLabels);
    };

    readonly #formatMinutes = (minutes: number): string => {
        return formatTimeRangeMinutes(minutes, this.#chartRuntime);
    };

    #compactModeContext(): ChartFiltersCompactModeContext {
        return {
            container: this.#container,
            state: this.#state,
            config: this.#config,
            elements: this.#elements,
            resources: this.#resources,
            getFilterLabel: this.getFilterLabel,
            formatTimeRange: this.#formatMinutes
        };
    }

    #fullscreenContext(): ChartFiltersFullscreenContext {
        return {
            container: this.#container,
            fullscreenTarget: this.#config.fullscreenTarget,
            button: this.#elements.fullscreenBtn
        };
    }

    #notify(type: FilterType, value: FilterValue): void {
        const callback = this.#callbacks[type];
        if (isFunction(callback)) {
            callback(value, type);
        }
        updateCompactSummary(this.#compactModeContext());
    }

    #applyFilterState(type: FilterType, value: FilterValue | null): void {
        updateFilterState(this.#state, type, value);
    }

    #resolveValue(type: FilterType): FilterValue | null {
        return readFilterValue(this.#state, type);
    }

    #syncFilter(type: FilterType): void {
        const control = this.#elements.filters[type];
        if (control) {
            const value = this.#resolveValue(type);
            syncFilterInput(type, control, value);
        }
        this.#syncChartTypeFilterVisibility();
    }

    #syncChartTypeFilterVisibility(): void {
        updateChartTypeFilterVisibility(this.#container, this.#state.chartType);
    }

    #resetRenderedResources(): void {
        disposeCompactMode(this.#compactModeContext(), this.#compactModeState);
        this.#resources.cleanup();
        this.#compactModeState = createCompactModeState();
    }

    #requireActive(): void {
        if (this.#disposed) {
            throw new Error('ChartFilters cannot be used after dispose');
        }
    }

    render(): Element {
        this.#requireActive();
        this.#resetRenderedResources();

        const onChange = (type: FilterType, value: FilterValue): void => {
            this.#applyFilterState(type, value);
        };

        const onSync = (type: FilterType, shouldNotify: boolean): void => {
            this.#syncFilter(type);
            if (shouldNotify) {
                const value = this.#resolveValue(type);
                if (value !== null) {
                    this.#notify(type, value);
                }
            }
        };

        this.#elements = renderChartFiltersView({
            container: this.#container,
            state: this.#state,
            config: this.#config,
            formatTimeRange: this.#formatMinutes,
            getFilterLabel: this.getFilterLabel,
            onChange,
            onSync,
            resources: this.#resources
        });

        this.#syncChartTypeFilterVisibility();

        if (this.#elements.fullscreenBtn) {
            const fullscreenContext = this.#fullscreenContext();
            this.#resources.addEventListener(this.#elements.fullscreenBtn, 'click', () => toggleFullscreen(fullscreenContext));
            this.#resources.addEventListener(dom.getDocument(), 'fullscreenchange', () => {
                updateFullscreenIcon(fullscreenContext);
            });
        }

        setupCompactMode(this.#compactModeContext(), this.#compactModeState);
        return this.#container;
    }

    setCategories(categories: FilterOption[]): this {
        this.#requireActive();
        applyCategoryOptions({
            config: this.#config,
            state: this.#state,
            elements: this.#elements,
            categories,
            syncFilter: (type) => this.#syncFilter(type)
        });
        return this;
    }

    setSubcategories(subcategories: FilterOption[]): this {
        this.#requireActive();
        applySubcategoryOptions({
            config: this.#config,
            state: this.#state,
            elements: this.#elements,
            subcategories,
            syncFilter: (type) => this.#syncFilter(type)
        });
        return this;
    }

    setTimeRangeOptions(options: FilterOptionsInput): this {
        this.#requireActive();
        applyTimeRangeOptions({
            config: this.#config,
            state: this.#state,
            elements: this.#elements,
            options,
            formatValue: (value) => this.#formatMinutes(value)
        });
        this.#renderMissingFilter(FILTER_TYPES.TIME_RANGE);
        return this;
    }

    setCandleIntervals(intervals: FilterOptionsInput): this {
        this.#requireActive();
        applyCandleIntervals({
            config: this.#config,
            state: this.#state,
            elements: this.#elements,
            intervals,
            formatValue: (value) => this.#formatMinutes(value)
        });
        this.#renderMissingFilter(FILTER_TYPES.CANDLE_INTERVAL);
        this.#syncChartTypeFilterVisibility();
        return this;
    }

    #renderMissingFilter(type: FilterType): void {
        const hasOptions = type === FILTER_TYPES.TIME_RANGE ? this.#config.timeRangeOptions.length > 0 : this.#config.candleIntervals.length > 0;
        if (!hasOptions || this.#elements.filters[type]) {
            return;
        }
        this.render();
    }

    getState(): ChartFiltersState {
        this.#requireActive();
        return { ...this.#state };
    }

    setState(nextState: Partial<ChartFiltersState>): this {
        this.#requireActive();
        if (typeof nextState !== 'object' || !nextState) {
            return this;
        }
        applyStatePatch({
            state: this.#state,
            nextState,
            syncFilter: (type) => this.#syncFilter(type)
        });
        this.#syncChartTypeFilterVisibility();
        return this;
    }

    setValue(type: FilterType, value: FilterValue | null, notify = false): this {
        this.#requireActive();
        this.#applyFilterState(type, value);
        this.#syncFilter(type);
        if (notify) {
            const current = this.#resolveValue(type);
            if (current !== null) {
                this.#notify(type, current);
            }
        }
        return this;
    }

    onFilterChange(type: FilterType, callback: (value: FilterValue) => void): this {
        this.#requireActive();
        registerFilterCallback(this.#callbacks, type, callback);
        return this;
    }

    getElement(type: FilterType | 'fullscreen' | string): HTMLElement | null {
        this.#requireActive();
        return resolveFilterElement(this.#container, this.#elements, type);
    }

    updateChartTypeVisibility(chartType: string): void {
        this.#requireActive();
        this.#applyFilterState(FILTER_TYPES.CHART_TYPE, chartType);
        this.#syncFilter(FILTER_TYPES.CHART_TYPE);
    }

    dispose(): void {
        if (this.#disposed) {
            return;
        }
        this.#disposed = true;
        disposeCompactMode(this.#compactModeContext(), this.#compactModeState);
        this.#resources.cleanup();
        this.#container.replaceChildren();
        this.#elements = {
            compactTrigger: null,
            compactPanel: null,
            fullscreenBtn: null,
            filters: {}
        };
        this.#callbacks = {};
    }
}

export { ChartFilters };
