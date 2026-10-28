/* SoAI - Read the authored loading trail appearance [frontend/assets/ts/core/pageoutlet/spinner/appearance.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { parseMaxCssDurationMs } from '@core/animations/parseMaxCssDurationMs.ts';
import { resolveCanvasRenderPixelRatio } from '@core/layout/canvasGeometry.ts';
import { isSpinnerTrailAppearance, type SpinnerTrailAppearance, type SpinnerGradientStop } from '@core/visualization/protocol.ts';

const readSpinnerGradientStops = (gradient: string): SpinnerGradientStop[] => {
    if (!gradient.startsWith('conic-gradient(')) throw new Error('Page loading trail requires its authored conic gradient');
    const stops: SpinnerGradientStop[] = [];
    const pattern = /(rgba?\([^()]*\)|color\([^()]*\)|transparent)\s+([\d.]+)deg(?:\s+([\d.]+)deg)?/gu;
    for (const match of gradient.matchAll(pattern)) {
        const color = match[1];
        const position = match[2];
        if (!color || !position) throw new Error('Page loading trail contains an invalid gradient stop');
        stops.push({ color, position: Number(position) / 360 });
        if (match[3]) stops.push({ color, position: Number(match[3]) / 360 });
    }
    const remainder = gradient
        .replace(pattern, '')
        .replace(/^conic-gradient\((?:from [-\d.]+deg,?\s*)?/u, '')
        .replace(/[,\s)]/gu, '');
    if (remainder) throw new Error('Page loading trail contains an unsupported gradient stop');
    if (stops[0]?.position !== 0 || stops.at(-1)?.position !== 1) throw new Error('Page loading trail requires a complete gradient');
    return stops;
};

const resolveTrailInset = (raw: string, extent: number): number => {
    const value = Number.parseFloat(raw);
    if (!Number.isFinite(value) || (!raw.endsWith('%') && !raw.endsWith('px'))) throw new Error('Page loading trail requires a resolved inset');
    return raw.endsWith('%') ? (value * extent) / 100 : value;
};

const readSpinnerTrailAppearance = (spinner: HTMLElement, canvas: HTMLCanvasElement | null = null): SpinnerTrailAppearance => {
    const view = spinner.ownerDocument.defaultView;
    if (!view) throw new Error('Page loading trail requires a document window');
    const style = view.getComputedStyle(spinner);
    const surfaceStyle = canvas ? view.getComputedStyle(canvas) : style;
    const trailStyle = view.getComputedStyle(spinner, '::before');
    const width = Number.parseFloat(surfaceStyle.width);
    const height = Number.parseFloat(surfaceStyle.height);
    const spinnerWidth = Number.parseFloat(style.width);
    const spinnerHeight = Number.parseFloat(style.height);
    const trailWidth = spinnerWidth - resolveTrailInset(trailStyle.left, spinnerWidth) - resolveTrailInset(trailStyle.right, spinnerWidth);
    const trailHeight = spinnerHeight - resolveTrailInset(trailStyle.top, spinnerHeight) - resolveTrailInset(trailStyle.bottom, spinnerHeight);
    const duration = style.getPropertyValue('--soai-spinner-duration').trim();
    const pixelRatio = resolveCanvasRenderPixelRatio(spinner);
    const appearance = {
        width: Math.max(1, Math.ceil(width * pixelRatio)),
        height: Math.max(1, Math.ceil(height * pixelRatio)),
        trailWidth: Math.max(1, Math.ceil(trailWidth * pixelRatio)),
        trailHeight: Math.max(1, Math.ceil(trailHeight * pixelRatio)),
        duration: parseMaxCssDurationMs(duration),
        stops: readSpinnerGradientStops(trailStyle.backgroundImage)
    };
    if (!isSpinnerTrailAppearance(appearance)) throw new Error('Page loading trail has an invalid appearance');
    return appearance;
};

export { readSpinnerGradientStops, readSpinnerTrailAppearance };
