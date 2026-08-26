/* SoAI - Charts feature viewport state [frontend/assets/ts/features/charts/viewportState.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

interface ChartViewportStateHost {
    initialChartViewportFitted: boolean;
}

const resetChartViewportState = (host: ChartViewportStateHost): void => {
    host.initialChartViewportFitted = false;
};

const resolveChartViewportReset = (host: ChartViewportStateHost, resetView: boolean): boolean => {
    return resetView || !host.initialChartViewportFitted;
};

const markChartViewportFitted = (host: ChartViewportStateHost): void => {
    host.initialChartViewportFitted = true;
};

export { markChartViewportFitted, resetChartViewportState, resolveChartViewportReset };
export type { ChartViewportStateHost };
