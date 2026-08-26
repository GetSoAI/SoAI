/* SoAI - Chart series storage ownership [frontend/assets/ts/features/charts/session/ChartSeriesStore.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartOptions, Dataset, DatasetInput, OhlcValues } from '@features/charts/chartTypes.ts';
import type { OhlcData, RenderBuffers } from '@features/charts/component/chartComponentTypes.ts';
import { discardHeikin, downgradeToValue, ensureOhlcStorage, getCloseValue, getEffectiveDataLength, getOhlcForIndex, getRenderableOhlcBuffers, getValueBufferForRendering, hasOhlcData, invalidateHeikinFrom, isOhlcRenderingType, normalizeDataPoint, upgradeToOhlc } from '@features/charts/component/data/ohlc.ts';
import { findFirstIndexAtOrAfter, findLastIndexAtOrBefore, findTimestampSlot } from '@features/charts/component/data/timestampIndex.ts';
import { interpolate } from '@features/charts/component/data/interpolation.ts';
import type { ChartPointCandidate, NormalizedDataPoint } from '@features/charts/data/chartPointTypes.ts';
import { trimSeriesDatasets, updateCurrentSeriesBar } from '@features/charts/session/chartSeriesActions.ts';
import { addSeriesDataset, appendSeriesPoint, clearSeriesDatasets, prependSeries, replaceSeries } from '@features/charts/session/chartSeriesMutations.ts';
import type { ChartSeriesStorageRuntime, SeriesInsertResult, SeriesPrependResult, SeriesReplaceResult, SeriesResizeResult } from '@features/charts/session/chartSeriesRuntime.ts';
import type { ChartConfigurationState, ChartSeriesState } from '@features/charts/session/chartState.ts';

interface ChartSeriesStoreDependencies {
    configuration: ChartConfigurationState;
    series: ChartSeriesState;
}

const OHLC_BUFFER_FIELDS: readonly (keyof OhlcData)[] = ['open', 'high', 'low', 'close'];

class ChartSeriesStore {
    readonly #configuration: ChartConfigurationState;
    readonly #series: ChartSeriesState;

    constructor({ configuration, series }: ChartSeriesStoreDependencies) {
        this.#configuration = configuration;
        this.#series = series;
    }

    replace(points: ReadonlyArray<ChartPointCandidate> | null, options?: { assumeSorted?: boolean }): SeriesReplaceResult {
        return replaceSeries(this.#runtime(), points, options);
    }

    prepend(points: ReadonlyArray<ChartPointCandidate> | null): SeriesPrependResult {
        return prependSeries(this.#runtime(), points);
    }

    appendPoint(point: ChartPointCandidate): SeriesInsertResult {
        return appendSeriesPoint(this.#runtime(), point);
    }

    updateCurrentBar(point: ChartPointCandidate): SeriesInsertResult {
        return updateCurrentSeriesBar(this.#runtime(), point);
    }

    addDataset(definition: DatasetInput): void {
        addSeriesDataset(this.#runtime(), definition);
    }

    clearDatasets(): void {
        clearSeriesDatasets(this.#runtime());
    }

    applyChartType(type: string): void {
        if (type !== 'heikin-ashi') return;
        if (this.#series.dataStructure !== 'ohlc') this.upgradeToOhlc();
        this.invalidateHeikin(0);
    }

    resizeCapacity(capacity: number): SeriesResizeResult {
        const previousLength = this.#series.dataLength;
        const nextLength = Math.min(previousLength, capacity);
        const start = Math.max(0, previousLength - nextLength);
        const timestamps = new Float64Array(capacity);
        const values = new Float64Array(capacity);
        timestamps.set(this.#series.timestamps.subarray(start, start + nextLength));
        values.set(this.#series.values.subarray(start, start + nextLength));
        this.#series.timestamps = timestamps;
        this.#series.values = values;
        const renderCapacity = Math.max(8, capacity);
        this.#series.renderBuffers = { capacity: renderCapacity, x: new Float64Array(renderCapacity), y: new Float64Array(renderCapacity), value: new Float64Array(renderCapacity), valid: new Uint8Array(renderCapacity), index: new Uint32Array(renderCapacity) };
        trimSeriesDatasets(this.#runtime(), start, nextLength);
        if (this.hasOhlc()) {
            const previous = this.ensureOhlc();
            const next: OhlcData = { open: new Float64Array(capacity), high: new Float64Array(capacity), low: new Float64Array(capacity), close: new Float64Array(capacity) };
            for (const key of OHLC_BUFFER_FIELDS) next[key].set(previous[key].subarray(start, start + nextLength));
            this.#series.ohlc = next;
        } else if (this.#series.ohlc) {
            this.#series.ohlc = null;
            this.#series.dataStructure = 'value';
        }
        this.discardHeikin();
        this.#series.dataLength = nextLength;
        return { previousLength, nextLength, removedFromHead: previousLength - nextLength };
    }

    ensureRenderCapacity(minimum: number): { buffers: RenderBuffers; resized: boolean } {
        const required = Math.max(8, Math.ceil(minimum) || 8);
        if (this.#series.renderBuffers.capacity >= required) return { buffers: this.#series.renderBuffers, resized: false };
        const capacity = Math.max(required, Math.floor(this.#series.renderBuffers.capacity * 1.5), this.#configuration.options.maxDataPoints, 8);
        this.#series.renderBuffers = { capacity, x: new Float64Array(capacity), y: new Float64Array(capacity), value: new Float64Array(capacity), valid: new Uint8Array(capacity), index: new Uint32Array(capacity) };
        return { buffers: this.#series.renderBuffers, resized: true };
    }

    normalize(point: ChartPointCandidate): NormalizedDataPoint | null {
        return normalizeDataPoint(point);
    }
    findTimestamp(timestamp: number): { exact: boolean; index: number } {
        return findTimestampSlot(this.#series.timestamps, this.#series.dataLength, timestamp);
    }
    findFirstTimestamp(timestamp: number): number {
        return findFirstIndexAtOrAfter(this.#series.timestamps, this.#series.dataLength, timestamp);
    }
    findLastTimestamp(timestamp: number): number {
        return findLastIndexAtOrBefore(this.#series.timestamps, this.#series.dataLength, timestamp);
    }
    hasOhlc(): boolean {
        return hasOhlcData(this);
    }
    ensureOhlc(): OhlcData {
        return ensureOhlcStorage(this);
    }
    invalidateHeikin(index: number): void {
        invalidateHeikinFrom(this, index);
    }
    discardHeikin(): void {
        discardHeikin(this);
    }
    upgradeToOhlc(): void {
        upgradeToOhlc(this);
    }
    downgradeToValue(): void {
        downgradeToValue(this);
    }
    effectiveLength(): number {
        return getEffectiveDataLength(this);
    }
    closeValue(index: number): number | undefined {
        return getCloseValue(this, index);
    }
    ohlcAt(index: number, target: OhlcValues | null = null): OhlcValues {
        return getOhlcForIndex(this, index, target);
    }
    renderableOhlc(): OhlcData | null {
        return getRenderableOhlcBuffers(this);
    }
    renderableValues(): Float64Array {
        return getValueBufferForRendering(this);
    }
    isOhlcType(type?: string): boolean {
        return isOhlcRenderingType(this, type);
    }
    interpolate(rawIndex: number, start: number, end: number): { value: number | null; timestamp: number | null } {
        return interpolate({ timestamps: this.timestamps, getCloseValue: (index) => this.closeValue(index) }, rawIndex, start, end);
    }

    get chartOptions(): ChartOptions {
        return this.#configuration.options;
    }
    get dataLength(): number {
        return this.#series.dataLength;
    }
    get datasets(): Dataset[] {
        return this.#series.datasets;
    }
    get dataStructure(): string {
        return this.#series.dataStructure;
    }
    set dataStructure(value: string) {
        this.#series.dataStructure = value;
    }
    get sourceSeriesMode(): string {
        return this.#series.sourceSeriesMode;
    }
    set sourceSeriesMode(value: string) {
        this.#series.sourceSeriesMode = value;
    }
    get timestamps(): Float64Array {
        return this.#series.timestamps;
    }
    get values(): Float64Array {
        return this.#series.values;
    }
    get ohlcScratch(): OhlcValues {
        return this.#series.ohlcScratch;
    }
    get ohlc(): OhlcData | null {
        return this.#series.ohlc;
    }
    set ohlc(value: OhlcData | null) {
        this.#series.ohlc = value;
    }
    get heikin(): OhlcData | null {
        return this.#series.heikin;
    }
    set heikin(value: OhlcData | null) {
        this.#series.heikin = value;
    }
    get heikinDirtyIndex(): number {
        return this.#series.heikinDirtyIndex;
    }
    set heikinDirtyIndex(value: number) {
        this.#series.heikinDirtyIndex = value;
    }
    get heikinValidLength(): number {
        return this.#series.heikinValidLength;
    }
    set heikinValidLength(value: number) {
        this.#series.heikinValidLength = value;
    }

    #runtime(): ChartSeriesStorageRuntime {
        return {
            series: this.#series,
            maxDataPoints: this.#configuration.options.maxDataPoints,
            chartType: this.#configuration.options.chartType,
            data: { normalize: (point) => this.normalize(point), findTimestamp: (timestamp) => this.findTimestamp(timestamp), hasOhlc: () => this.hasOhlc(), ensureOhlc: () => this.ensureOhlc(), invalidateHeikin: (index) => this.invalidateHeikin(index), discardHeikin: () => this.discardHeikin(), upgradeToOhlc: () => this.upgradeToOhlc(), downgradeToValue: () => this.downgradeToValue() }
        };
    }
}

export { ChartSeriesStore };
export type { ChartSeriesStoreDependencies };
