/* SoAI - Audio visualizer canvas preparation and accent color resolution [frontend/assets/ts/core/media/audioVisualizerCanvas.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { measureLayoutBox } from '@core/layout/elementGeometry.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';

type CanvasSize = Readonly<{ width: number; height: number }>;
type CanvasRgb = Readonly<{ red: number; green: number; blue: number }>;
type PreparedCanvas = Readonly<{ context: CanvasRenderingContext2D; size: CanvasSize; color: CanvasRgb }>;

const EMPTY_HEIGHT = 120;
const FALLBACK_COLOR: CanvasRgb = Object.freeze({ red: 52, green: 211, blue: 153 });
const RGB_PATTERN = /\d+(?:\.\d+)?/g;

const resolveCanvasCssSize = (canvas: HTMLCanvasElement): CanvasSize => {
    const rect = measureLayoutBox(canvas);
    const width = Math.max(1, Math.round(rect.width));
    const height = Math.max(1, Math.round(rect.height || EMPTY_HEIGHT));
    return Object.freeze({ width, height });
};

const resizeCanvas = (canvas: HTMLCanvasElement): CanvasRenderingContext2D => {
    const context = canvas.getContext('2d');
    if (!context) {
        throw new Error('Audio visualizer requires a 2D canvas context');
    }
    const size = resolveCanvasCssSize(canvas);
    const pixelRatio = resolveCanvasRenderPixelRatio(canvas);
    const width = Math.max(1, Math.round(size.width * pixelRatio));
    const height = Math.max(1, Math.round(size.height * pixelRatio));
    if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
    }
    context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    return context;
};

const resolveAccentColor = (canvas: HTMLCanvasElement): CanvasRgb => {
    const raw = canvas.ownerDocument.defaultView?.getComputedStyle(canvas).getPropertyValue('color').trim() ?? '';
    const matches = raw.match(RGB_PATTERN);
    if (!matches || matches.length < 3) {
        return FALLBACK_COLOR;
    }
    const redChannel = Number(matches[0]);
    const greenChannel = Number(matches[1]);
    const blueChannel = Number(matches[2]);
    if (!Number.isFinite(redChannel) || !Number.isFinite(greenChannel) || !Number.isFinite(blueChannel)) {
        return FALLBACK_COLOR;
    }
    return Object.freeze({ red: redChannel, green: greenChannel, blue: blueChannel });
};

const configureCanvas = (canvas: HTMLCanvasElement): PreparedCanvas => {
    const context = resizeCanvas(canvas);
    const size = resolveCanvasCssSize(canvas);
    const color = resolveAccentColor(canvas);
    context.globalCompositeOperation = 'source-over';
    context.globalAlpha = 1;
    context.shadowBlur = 0;
    context.shadowColor = 'transparent';
    return Object.freeze({ context, size, color });
};

const prepareCanvas = (canvas: HTMLCanvasElement): PreparedCanvas => {
    const prepared = configureCanvas(canvas);
    const { context } = prepared;
    context.save();
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.restore();
    return prepared;
};

const prepareRetainedCanvas = (canvas: HTMLCanvasElement): PreparedCanvas => configureCanvas(canvas);

const rgba = (color: CanvasRgb, alpha: number): string => `rgba(${color.red}, ${color.green}, ${color.blue}, ${alpha})`;

const hsla = (hue: number, saturation: number, lightness: number, alpha: number): string => {
    const wrapped = ((hue % 360) + 360) % 360;
    return `hsla(${wrapped}, ${saturation}%, ${lightness}%, ${alpha})`;
};

const rgbToHue = (color: CanvasRgb): number => {
    const redChannel = color.red / 255;
    const greenChannel = color.green / 255;
    const blueChannel = color.blue / 255;
    const max = Math.max(redChannel, greenChannel, blueChannel);
    const delta = max - Math.min(redChannel, greenChannel, blueChannel);
    if (delta === 0) {
        return 0;
    }
    let hue = 0;
    if (max === redChannel) {
        hue = ((greenChannel - blueChannel) / delta) % 6;
    } else if (max === greenChannel) {
        hue = (blueChannel - redChannel) / delta + 2;
    } else {
        hue = (redChannel - greenChannel) / delta + 4;
    }
    hue *= 60;
    return hue < 0 ? hue + 360 : hue;
};

export { hsla, prepareCanvas, prepareRetainedCanvas, rgba, rgbToHue };
export type { CanvasRgb, CanvasSize, PreparedCanvas };
