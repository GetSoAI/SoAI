/* SoAI - Charts feature state effects [frontend/assets/ts/features/charts/component/state/effects.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { dom } from '@core/dom/dom.ts';
import { getRequestAnimationFrame } from '@core/environment/public.ts';
import { isFunction } from '@core/typeGuards.ts';
import type { ChartThemeManagedPaletteInput, ColorPalette } from '@features/charts/chartTypes.ts';
import { CSS_COLOR_VAR_MAP, THEME_DEPENDENT_COLOR_KEYS, isTransparentColor } from '@features/charts/component/chartComponentStatics.ts';
import { getStyleSources, readCssVariable } from '@features/charts/component/state/adapters.ts';
import type { ExtractCssColorsHost, LayerBackgroundHost, ThemeChangeHost } from '@features/charts/component/state/types.ts';

const resolveCanvasBaseBackground = (element: HTMLElement, colors: ColorPalette): string => {
    const doc = element.ownerDocument;
    const win = doc.defaultView;
    if (!win || !isFunction(win.getComputedStyle)) {
        throw new Error('Chart requires window.getComputedStyle');
    }
    const styles = getStyleSources(element);
    const explicitCanvasBackground = readCssVariable(styles, '--chart-canvas-base-background');
    if (explicitCanvasBackground) {
        return isTransparentColor(explicitCanvasBackground) ? '' : explicitCanvasBackground;
    }
    const cssBackground = readCssVariable(styles, ['--surface-chart', '--surface-card', '--bg-primary', '--glass-surface-strong', '--bg-secondary']);
    if (cssBackground && !isTransparentColor(cssBackground)) {
        return cssBackground;
    }

    let node: HTMLElement | null = element;
    for (let depth = 0; depth < 6 && node; depth += 1, node = node.parentElement) {
        const nodeStyles = win.getComputedStyle(node);
        const nodeBackground = nodeStyles.backgroundColor || nodeStyles.background;
        if (nodeBackground && !isTransparentColor(nodeBackground)) return nodeBackground;
    }

    const documentElement = doc.documentElement;
    const documentBackground = win.getComputedStyle(documentElement).backgroundColor;
    if (documentBackground && !isTransparentColor(documentBackground)) return documentBackground;

    const bodyBackground = win.getComputedStyle(doc.body).backgroundColor;
    if (bodyBackground && !isTransparentColor(bodyBackground)) return bodyBackground;

    return colors.background ?? '';
};

const applyLayerBackgroundStyles = (chart: LayerBackgroundHost): void => {
    const element = chart.element;
    if (!element || !chart.canvasLayers || !isFunction(dom?.setStyle)) return;

    const background = resolveCanvasBaseBackground(element, chart.chartOptions.colors);
    Object.values(chart.canvasLayers).forEach((canvas) => {
        if (canvas) dom.setStyle(canvas, 'backgroundColor', canvas === chart.canvasLayers.static ? background : 'transparent');
    });
    chart.canvasBaseBackground = background;
};

const extractCSSColors = (chart: ExtractCssColorsHost): ChartThemeManagedPaletteInput | null => {
    const element = chart.element;
    if (!element || !chart.themeColorFlags) return null;

    const keys = THEME_DEPENDENT_COLOR_KEYS.filter((key) => chart.themeColorFlags[key]);
    if (!keys.length) return null;

    const styleSources = getStyleSources(element);
    if (!styleSources.length) return null;

    const extractedColors: Record<string, string> = {};
    keys.forEach((key) => {
        const cssVariable = CSS_COLOR_VAR_MAP[key];
        const value = cssVariable && readCssVariable(styleSources, cssVariable);
        if (value) extractedColors[key] = key === 'background' ? chart.normalizeBackgroundColor(value) : value;
    });

    if (!Object.keys(extractedColors).length) return null;
    const metadata = keys.reduce<Record<string, boolean>>((accumulator, key) => ({ ...accumulator, [key]: true }), {});
    extractedColors['__themeManaged'] = JSON.stringify(metadata);
    return extractedColors;
};

const setupThemeChangeListener = (chart: ThemeChangeHost): void => {
    if (!chart.themeColorFlags) return;

    const element = chart.element;
    if (!element) {
        throw new Error('Chart requires an element to bind theme events');
    }
    const win = element.ownerDocument.defaultView;
    if (!win) {
        throw new Error('Chart requires a Window to bind theme events');
    }

    const requestAnimationFrame = getRequestAnimationFrame();
    chart.themeChangeHandler = () =>
        requestAnimationFrame(() => {
            const extractedThemeColors = chart.extractCSSColors();
            if (extractedThemeColors && Object.keys(extractedThemeColors).length > 0) {
                chart.setColors(extractedThemeColors, { preserveThemeFlags: true });
            }
        });
    chart.addEventListener(win, 'themeChanged', chart.themeChangeHandler);
};

export { applyLayerBackgroundStyles, extractCSSColors, resolveCanvasBaseBackground, setupThemeChangeListener };
