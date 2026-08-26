/* SoAI - Audio frequency spectrum bars renderer [frontend/assets/ts/core/media/audioBarsRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hsla, rgbToHue, type CanvasRgb, type CanvasSize } from '@core/media/audioVisualizerCanvas.ts';

const BAR_COUNT = 56;
const GAP_RATIO = 0.32;
const TOP_PADDING_RATIO = 0.06;
const HUE_SPREAD = 260;
const HUE_DRIFT = 0.008;
const CORNER_RADIUS = 3;

type BarLayout = Readonly<{ baseline: number; maxHeight: number; slot: number; barWidth: number }>;

const resolveLayout = (size: CanvasSize): BarLayout => {
    const slot = size.width / BAR_COUNT;
    return Object.freeze({
        baseline: size.height,
        maxHeight: size.height * (1 - TOP_PADDING_RATIO),
        slot,
        barWidth: slot * (1 - GAP_RATIO)
    });
};

const buildBandEdges = (binCount: number): readonly number[] => {
    const minBin = 1;
    const maxBin = Math.max(minBin + 1, binCount - 1);
    const edges: number[] = [minBin];
    for (let index = 1; index <= BAR_COUNT; index += 1) {
        const computed = Math.round(minBin * Math.pow(maxBin / minBin, index / BAR_COUNT));
        const previous = edges[index - 1] ?? minBin;
        edges.push(computed > previous ? computed : previous + 1);
    }
    return edges;
};

const bandMagnitude = (buffer: Uint8Array<ArrayBuffer>, edges: readonly number[], barIndex: number): number => {
    const lowBin = edges[barIndex] ?? 1;
    const highBin = edges[barIndex + 1] ?? lowBin + 1;
    const maxBin = Math.floor(buffer.length / 2) - 1;
    let total = 0;
    let count = 0;
    for (let bin = lowBin; bin < highBin && bin <= maxBin; bin += 1) {
        total += buffer[bin] ?? 0;
        count += 1;
    }
    const average = count > 0 ? total / count / 255 : 0;
    return Math.pow(average, 0.85);
};

const fillRoundedBar = (context: CanvasRenderingContext2D, xCoordinate: number, top: number, width: number, baseline: number): void => {
    const radius = Math.min(CORNER_RADIUS, width / 2, (baseline - top) / 2);
    context.beginPath();
    context.moveTo(xCoordinate, baseline);
    context.lineTo(xCoordinate, top + radius);
    context.quadraticCurveTo(xCoordinate, top, xCoordinate + radius, top);
    context.lineTo(xCoordinate + width - radius, top);
    context.quadraticCurveTo(xCoordinate + width, top, xCoordinate + width, top + radius);
    context.lineTo(xCoordinate + width, baseline);
    context.closePath();
    context.fill();
};

const drawBars = (context: CanvasRenderingContext2D, size: CanvasSize, baseHue: number, time: number, magnitudeFor: (index: number) => number): void => {
    const layout = resolveLayout(size);
    const offset = (layout.slot - layout.barWidth) / 2;
    for (let index = 0; index < BAR_COUNT; index += 1) {
        const magnitude = magnitudeFor(index);
        const height = Math.max(2, magnitude * layout.maxHeight);
        const top = layout.baseline - height;
        const xCoordinate = index * layout.slot + offset;
        const hue = baseHue + (index / BAR_COUNT) * HUE_SPREAD + time * HUE_DRIFT;
        const gradient = context.createLinearGradient(0, top, 0, layout.baseline);
        gradient.addColorStop(0, hsla(hue, 78, 60, 0.95));
        gradient.addColorStop(1, hsla(hue, 80, 46, 0.85));
        context.fillStyle = gradient;
        fillRoundedBar(context, xCoordinate, top, layout.barWidth, layout.baseline);
    }
};

const drawBarsActive = (context: CanvasRenderingContext2D, size: CanvasSize, color: CanvasRgb, buffer: Uint8Array<ArrayBuffer>, time: number): void => {
    const edges = buildBandEdges(Math.max(2, Math.floor(buffer.length / 2)));
    drawBars(context, size, rgbToHue(color), time, (index) => bandMagnitude(buffer, edges, index));
};

export { drawBarsActive };
