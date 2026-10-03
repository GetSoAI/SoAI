/* SoAI - Charts feature keyboard [frontend/assets/ts/features/charts/interaction/keyboard.ts] */
// SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

import { hideCrosshair } from '@features/charts/crosshair.ts';
import type { ChartInteractionScene } from '@features/charts/interaction/chartInteractionScene.ts';

const KEYBOARD_ZOOM_FACTOR = 1.18;
const KEYBOARD_PAN_RATIO = 0.12;

const handleKeyboardNavigation = (chart: ChartInteractionScene, event: KeyboardEvent): void => {
    let handled = true;
    const { left, chartWidth } = chart.viewport.getChartDimensions();
    const centerX = left + chartWidth / 2;
    switch (event.key) {
        case 'ArrowLeft':
            chart.viewport.panByPixels(chartWidth * KEYBOARD_PAN_RATIO);
            break;
        case 'ArrowRight':
            chart.viewport.panByPixels(-chartWidth * KEYBOARD_PAN_RATIO);
            break;
        case '+':
        case '=':
            chart.viewport.zoomBy(centerX, 1 / KEYBOARD_ZOOM_FACTOR, true);
            break;
        case '-':
            chart.viewport.zoomBy(centerX, KEYBOARD_ZOOM_FACTOR, true);
            break;
        case '0':
            chart.viewport.resetZoom();
            break;
        case 'End':
            chart.viewport.alignToLatest();
            break;
        case 'Escape':
            hideCrosshair(chart);
            break;
        default:
            handled = false;
    }
    if (handled) {
        event.preventDefault();
    }
};

export { handleKeyboardNavigation };
