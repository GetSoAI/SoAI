/* SoAI - Charts feature state renderer [frontend/assets/ts/features/charts/rendering/stateRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import { monotonicMs } from '@core/time/clock.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawChartFrame } from '@features/charts/rendering/frame.ts';

const { floor } = Math;

const resolveStateTextColor = (scene: ChartRenderingScene): string => {
    const theme = scene.geometry.getThemeStyles();
    return theme?.legendTextColor || scene.state.chartOptions.colors.textSecondary || scene.state.chartOptions.colors.text || scene.state.chartOptions.colors.background || '';
};

const drawCenteredStateText = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, width: number, height: number, text: string): void => {
    Object.assign(context, {
        fillStyle: resolveStateTextColor(scene),
        font: '14px sans-serif',
        textAlign: 'center',
        textBaseline: 'middle'
    });
    context.fillText(text, width / 2, height / 2);
};

const scheduleLoadingRedraw = (scene: ChartRenderingScene): void => {
    scene.surface.scheduleLoadingRedraw();
};

const renderChartDataState = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, width: number, height: number): boolean => {
    if (scene.state.dataLength !== 0 || scene.state.datasets.length !== 0) {
        return false;
    }
    const text = scene.surface.isHistoricalDataLoading ? `${i18n.t('charts.loadingState')}${'.'.repeat((floor(monotonicMs() / 400) % 3) + 1)}` : i18n.t('charts.emptyState');
    drawCenteredStateText(scene, context, width, height, text);
    if (scene.surface.isHistoricalDataLoading) {
        scheduleLoadingRedraw(scene);
    }
    drawChartFrame(scene, context);
    return true;
};

export { renderChartDataState };
