/* SoAI - Chart render model derivation ownership [frontend/assets/ts/features/charts/session/ChartRenderModelUpdater.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { updateLegendData, updateVisibleRange, updateVisibleRangeStats } from '@features/charts/component/data/visibleRange.ts';
import { updateScale } from '@features/charts/component/data/verticalScale.ts';
import type { ChartConfigurationState, ChartInteractionState, ChartViewportState } from '@features/charts/session/chartState.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';

type VisibleRangeCalculations = Parameters<typeof updateVisibleRange>[1];

interface ChartRenderModelDependencies {
    configuration: ChartConfigurationState;
    viewport: ChartViewportState;
    interaction: ChartInteractionState;
    series: ChartSeriesStore;
    redraw: ChartRedrawQueue;
    element: HTMLElement;
    calculations: VisibleRangeCalculations;
    hover: { refreshCrosshair(): void };
}

class ChartRenderModelUpdater {
    readonly #configuration: ChartConfigurationState;
    readonly #viewport: ChartViewportState;
    readonly #interaction: ChartInteractionState;
    readonly #series: ChartSeriesStore;
    readonly #redraw: ChartRedrawQueue;
    readonly #element: HTMLElement;
    readonly #calculations: VisibleRangeCalculations;
    readonly #hover: ChartRenderModelDependencies['hover'];

    constructor({ configuration, viewport, interaction, series, redraw, element, calculations, hover }: ChartRenderModelDependencies) {
        this.#configuration = configuration;
        this.#viewport = viewport;
        this.#interaction = interaction;
        this.#series = series;
        this.#redraw = redraw;
        this.#element = element;
        this.#calculations = calculations;
        this.#hover = hover;
    }

    update(): void {
        updateVisibleRange(this, this.#calculations);
        updateVisibleRangeStats(this, this.#calculations);
        updateScale(this, this.#calculations);
        this.#hover.refreshCrosshair();
        updateLegendData(this, this.#calculations);
    }

    get chartOptions() {
        return this.#configuration.options;
    }
    get dataLength() {
        return this.#series.dataLength;
    }
    get datasets() {
        return this.#series.datasets;
    }
    get timestamps() {
        return this.#series.timestamps;
    }
    get values() {
        return this.#series.values;
    }
    get crosshair() {
        return this.#interaction.crosshair;
    }
    get legendData() {
        return this.#redraw.legend;
    }
    set legendData(value) {
        this.#redraw.legend = value;
    }
    get visibleRange() {
        return this.#viewport.visibleRange;
    }
    set visibleRange(value) {
        this.#viewport.visibleRange = value;
    }
    get visibleRangeStats() {
        return this.#viewport.visibleRangeStats;
    }
    set visibleRangeStats(value) {
        this.#viewport.visibleRangeStats = value;
    }
    get scale() {
        return this.#viewport.scale;
    }
    get axisCache() {
        return this.#redraw.axis;
    }
    set axisCache(value) {
        this.#redraw.axis = value;
    }
    get scaleGlide() {
        return this.#viewport.scaleGlide;
    }
    get yAxisMinRange() {
        return this.#viewport.yAxisMinRange;
    }
    get element() {
        return this.#element;
    }
    get lastEmittedTimeRange() {
        return this.#viewport.lastEmittedTimeRange;
    }
    set lastEmittedTimeRange(value) {
        this.#viewport.lastEmittedTimeRange = value;
    }
    get ohlcScratch() {
        return this.#series.ohlcScratch;
    }
}

export { ChartRenderModelUpdater };
export type { ChartRenderModelDependencies };
