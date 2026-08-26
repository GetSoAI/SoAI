/* SoAI - Charts feature state contracts [frontend/assets/ts/features/charts/component/state/types.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import type { ChartColorInput, ChartOptions, ChartThemeManagedPaletteInput, VisiblePointsCache } from '@features/charts/chartTypes.ts';
import type { CanvasLayers, RenderBuffers, ThemeColorFlags, ZoomState } from '@features/charts/component/chartComponentTypes.ts';

export interface ChartStorageService {
    getChartColorMode: () => string | null | undefined;
    getChartStaticColor: () => string | null | undefined;
}

export interface ZoomBoundsHost {
    zoom: ZoomState;
    chartOptions: ChartOptions;
    baseBarPixelWidth: number;
    getEffectiveDataLength: () => number;
    getChartDimensions: () => { chartWidth: number };
}

export interface DynamicPrimaryColorHost {
    chartOptions: ChartOptions;
}

export interface ScaleBoundsHost {
    yAxisMinRange: number;
}

export interface RenderBuffersHost {
    chartOptions: ChartOptions;
    renderBuffers: RenderBuffers | null;
    visiblePointsCache: VisiblePointsCache | null;
}

export interface LayerBackgroundHost {
    element: HTMLElement | null;
    canvasLayers: CanvasLayers;
    canvasBaseBackground: string | null;
    chartOptions: ChartOptions;
}

export interface ThemeChangeHost {
    element: HTMLElement | null;
    themeColorFlags: ThemeColorFlags;
    addEventListener: (target: EventTarget, type: string, handler: EventListener, options?: AddEventListenerOptions) => () => void;
    extractCSSColors: () => ChartThemeManagedPaletteInput | null;
    setColors: (colors: ChartThemeManagedPaletteInput | null | undefined, options?: { preserveThemeFlags?: boolean | undefined }) => void;
    themeChangeHandler: (() => void) | null;
}

export interface ExtractCssColorsHost {
    element: HTMLElement | null;
    themeColorFlags: ThemeColorFlags;
    normalizeBackgroundColor: (candidateValue: ChartColorInput, isDarkOverride?: boolean | null) => string;
}
