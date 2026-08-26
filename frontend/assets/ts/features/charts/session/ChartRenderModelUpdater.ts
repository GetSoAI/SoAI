/* SoAI - Chart render model derivation ownership [frontend/assets/ts/features/charts/session/ChartRenderModelUpdater.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { updateLegendData, updateScale, updateVisibleRange, updateVisibleRangeStats } from '@features/charts/component/data/visibleRange.ts';
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
    calculations: VisibleRangeCalculations;
}

class ChartRenderModelUpdater {
    readonly #configuration: ChartConfigurationState;
    readonly #viewport: ChartViewportState;
    readonly #interaction: ChartInteractionState;
    readonly #series: ChartSeriesStore;
    readonly #redraw: ChartRedrawQueue;
    readonly #calculations: VisibleRangeCalculations;

    constructor({ configuration, viewport, interaction, series, redraw, calculations }: ChartRenderModelDependencies) {
        this.#configuration = configuration;
        this.#viewport = viewport;
        this.#interaction = interaction;
        this.#series = series;
        this.#redraw = redraw;
        this.#calculations = calculations;
    }

    update(): void {
        updateVisibleRange(this, this.#calculations);
        updateVisibleRangeStats(this, this.#calculations);
        updateScale(this, this.#calculations);
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
    get baseBarPixelWidth() {
        return this.#viewport.baseBarPixelWidth;
    }
    get zoom() {
        return this.#viewport.zoom;
    }
    get pan() {
        return this.#viewport.pan;
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
