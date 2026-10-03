/* SoAI - Charts feature state renderer [frontend/assets/ts/features/charts/rendering/stateRenderer.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { i18n } from '@core/i18n/index.ts';
import type { ChartRenderingScene } from '@features/charts/rendering/chartRenderingHost.ts';
import { drawChartFrame } from '@features/charts/rendering/frame.ts';

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

const renderChartDataState = (scene: ChartRenderingScene, context: CanvasRenderingContext2D, width: number, height: number): boolean => {
    if (scene.state.dataLength !== 0 || scene.state.datasets.length !== 0) {
        return false;
    }
    drawCenteredStateText(scene, context, width, height, i18n.t('charts.emptyState'));
    drawChartFrame(scene, context);
    return true;
};

export { renderChartDataState };
