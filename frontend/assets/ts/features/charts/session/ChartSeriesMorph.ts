/* SoAI - Chart series resolution morph ownership [frontend/assets/ts/features/charts/session/ChartSeriesMorph.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { findFirstIndexAtOrAfter } from '@features/charts/component/data/timestampIndex.ts';
import type { ChartRedrawQueue } from '@features/charts/session/ChartRedrawQueue.ts';
import type { ChartSeriesStore } from '@features/charts/session/ChartSeriesStore.ts';
import { easeOutCubic, scaleChartAnimationDurationMs, SERIES_TRANSITION_MS } from '@core/animations/chartMotion.ts';

interface ChartSeriesSnapshot {
    timestamps: Float64Array;
    values: Float64Array;
}

interface ChartSeriesMorphDependencies {
    store: ChartSeriesStore;
    redraw: ChartRedrawQueue;
    element: HTMLElement;
}

const sampleSnapshot = (snapshot: ChartSeriesSnapshot, timestamps: Float64Array, length: number, target: Float64Array): void => {
    const last = snapshot.timestamps.length - 1;
    const firstTs = snapshot.timestamps[0] ?? Number.NaN;
    let cursor = 0;
    for (let index = 0; index < length; index++) {
        const timestamp = timestamps[index] ?? Number.NaN;
        if (!(timestamp >= firstTs)) {
            target[index] = Number.NaN;
            continue;
        }
        while (cursor < last && (snapshot.timestamps[cursor + 1] ?? Number.POSITIVE_INFINITY) <= timestamp) cursor++;
        const leftTs = snapshot.timestamps[cursor] ?? Number.NaN;
        const leftValue = snapshot.values[cursor] ?? Number.NaN;
        if (leftTs === timestamp || cursor === last) {
            target[index] = leftValue;
            continue;
        }
        const rightTs = snapshot.timestamps[cursor + 1] ?? Number.NaN;
        const rightValue = snapshot.values[cursor + 1] ?? Number.NaN;
        target[index] = leftValue + ((rightValue - leftValue) * (timestamp - leftTs)) / (rightTs - leftTs);
    }
};

class ChartSeriesMorph {
    readonly #store: ChartSeriesStore;
    readonly #redraw: ChartRedrawQueue;
    readonly #element: HTMLElement;
    #from = new Float64Array(0);
    #blend = new Float64Array(0);
    #length = 0;
    #anchorTs = Number.NaN;
    #startTime = 0;
    #durationMs = 0;
    #progress = 1;
    #blendProgress = Number.NaN;
    #blendOffset = -1;
    #blendLength = -1;
    #active = false;

    constructor({ store, redraw, element }: ChartSeriesMorphDependencies) {
        this.#store = store;
        this.#redraw = redraw;
        this.#element = element;
    }

    capture(): ChartSeriesSnapshot | null {
        const length = this.#store.dataLength;
        if (length < 2 || this.#store.hasOhlc()) return null;
        return { timestamps: this.#store.timestamps.slice(0, length), values: this.values().slice(0, length) };
    }

    begin(snapshot: ChartSeriesSnapshot | null, now: number): void {
        this.stop();
        const length = this.#store.dataLength;
        const durationMs = scaleChartAnimationDurationMs(SERIES_TRANSITION_MS, this.#element);
        if (!snapshot || length === 0 || durationMs <= 0 || this.#store.hasOhlc()) return;
        if (this.#from.length < length) this.#from = new Float64Array(length);
        sampleSnapshot(snapshot, this.#store.timestamps, length, this.#from);
        this.#length = length;
        this.#anchorTs = this.#store.timestamps[0] ?? Number.NaN;
        this.#startTime = now;
        this.#durationMs = durationMs;
        this.#progress = 0;
        this.#blendProgress = Number.NaN;
        this.#active = true;
        this.#redraw.request({ data: true });
    }

    stop(): void {
        if (!this.#active) return;
        this.#active = false;
        this.#redraw.request({ data: true });
    }

    advance(now: number): boolean {
        if (!this.#active) return false;
        const progress = scaleChartAnimationDurationMs(this.#durationMs, this.#element) === 0 ? 1 : (now - this.#startTime) / this.#durationMs;
        this.#progress = easeOutCubic(Math.min(1, Math.max(0, progress)));
        if (progress >= 1) this.#active = false;
        return true;
    }

    values(): Float64Array {
        const values = this.#store.renderableValues();
        if (!this.#active) return values;
        const length = this.#store.dataLength;
        const offset = findFirstIndexAtOrAfter(this.#store.timestamps, length, this.#anchorTs);
        if (offset === -1 || this.#store.timestamps[offset] !== this.#anchorTs) {
            this.#active = false;
            return values;
        }
        if (this.#blend.length !== values.length) this.#blend = new Float64Array(values.length);
        else if (this.#blendProgress === this.#progress && this.#blendOffset === offset && this.#blendLength === length) return this.#blend;
        for (let index = 0; index < length; index++) {
            const value = values[index] ?? Number.NaN;
            const sourceIndex = index - offset;
            const from = sourceIndex >= 0 && sourceIndex < this.#length ? (this.#from[sourceIndex] ?? Number.NaN) : Number.NaN;
            this.#blend[index] = Number.isFinite(from) && Number.isFinite(value) ? from + (value - from) * this.#progress : value;
        }
        this.#blendProgress = this.#progress;
        this.#blendOffset = offset;
        this.#blendLength = length;
        return this.#blend;
    }
}

export { ChartSeriesMorph };
export type { ChartSeriesMorphDependencies, ChartSeriesSnapshot };
